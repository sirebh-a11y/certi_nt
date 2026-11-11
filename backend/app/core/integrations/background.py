"""Durable, owner-scoped responses for slow integration operations.

There is deliberately no execution-age timeout. HTTP requests only submit or
poll. Two globally bounded PG slots prevent slow sources exhausting the app's
connection pool. Session advisory locks and the business session use the SAME
physical connection: losing ownership also fences subsequent business writes.
Running work is never replayed automatically after a process failure.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from functools import lru_cache, wraps
import hashlib
import hmac
import inspect
import json
from pathlib import Path
import re
import threading
from typing import get_type_hints
from uuid import uuid4

from fastapi import HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile as StarletteUploadFile

from app.core.config import settings
from app.core.database import engine
from app.core.integrations.models import IntegrationBackgroundJob as Job, IntegrationBackgroundReceipt as Receipt
from app.core.security.crypto import decrypt_secret, encrypt_secret
from app.core.users.models import User


OPERATIONS = {}
_manager = None
_manager_lock = threading.Lock()
_NAMESPACE = 14619041
_MAX_UPLOAD = 200 * 1024 * 1024
_TOKEN = re.compile(r"^[a-f0-9]{32}$")
_sqlite_guard = threading.Lock()
_sqlite_locks = set()
_source_guards = {}


@contextmanager
def serialized_background_source(db, name):
    """Protect a shared cache across commits on the worker-owned connection.

    Ordinary sessions can release/reassign their connection at commit, so a
    session advisory lock is only safe on the explicitly bound worker session.
    No lock is expired merely because its owner/source is slow.
    """
    if not db.info.get("integration_background"):
        yield
        return
    connection = db.connection()
    key = int(hashlib.sha256(name.encode()).hexdigest()[:7], 16) + 100
    if connection.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_lock(:ns, :key)"), {"ns": _NAMESPACE + 1, "key": key})
        db.commit()
        try:
            yield
        finally:
            db.rollback()
            if not connection.invalidated:
                db.execute(text("SELECT pg_advisory_unlock(:ns, :key)"), {"ns": _NAMESPACE + 1, "key": key})
                db.commit()
    else:
        identity = (str(connection.engine.url), name)
        with _sqlite_guard:
            guard = _source_guards.setdefault(identity, threading.Lock())
        with guard:
            yield


def _now():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def application_revision():
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value):
    return hmac.new(settings.app_secret_key.encode(), _dump(value).encode(), hashlib.sha256).hexdigest()


def _actor_snapshot(actor):
    return {"role": actor.role, "department_id": actor.department_id,
            "department_name": actor.department.name if actor.department is not None else None} if actor is not None else {}


def register_operation(fn):
    name = fn.__module__ + ":" + fn.__qualname__
    OPERATIONS[name] = fn
    return name


class BackgroundManager:
    def __init__(self, bind, *, root=None, revision=None):
        self.engine = bind
        self.root = Path(root or (Path(settings.document_storage_root).parent / "integration_jobs")).resolve()
        self.revision = revision or application_revision()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.threads = []

    def _path(self, key):
        if not re.fullmatch(r"[a-f0-9]{32}/(?:input_[a-f0-9]{32}|result)", key):
            raise ValueError("Invalid private job key")
        path = self.root / key
        if not path.resolve().is_relative_to(self.root) or path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Invalid private job path")
        return path

    def encode_arguments(self, arguments):
        encoded, uploads = {}, []
        try:
            for name, value in arguments.items():
                if isinstance(value, Session) or name == "db":
                    encoded[name] = {"kind": "db"}
                elif isinstance(value, User):
                    encoded[name] = {"kind": "actor"}
                elif isinstance(value, StarletteUploadFile):
                    key = uuid4().hex + "/input_" + uuid4().hex
                    path = self._path(key)
                    path.parent.mkdir(parents=True, exist_ok=False)
                    uploads.append(key)
                    digest, size = hashlib.sha256(), 0
                    position = value.file.tell()
                    try:
                        value.file.seek(0)
                        with path.open("xb") as target:
                            while chunk := value.file.read(1024 * 1024):
                                size += len(chunk)
                                if size > _MAX_UPLOAD:
                                    raise HTTPException(413, "File troppo grande")
                                digest.update(chunk)
                                target.write(chunk)
                    finally:
                        value.file.seek(position)
                    encoded[name] = {"kind": "upload", "key": key, "sha256": digest.hexdigest(),
                                     "size": size, "filename": value.filename,
                                     "content_type": value.content_type}
                elif isinstance(value, BaseModel):
                    # Preserve fields_set: PATCH omission must not become an
                    # explicit null/default when reconstructed in the worker.
                    encoded[name] = {"kind": "value", "value": value.model_dump(mode="json", exclude_unset=True)}
                else:
                    encoded[name] = {"kind": "value", "value": jsonable_encoder(value)}
            return encoded, uploads
        except BaseException:
            self._remove_inputs(uploads)
            raise

    def _remove_inputs(self, keys):
        for key in keys:
            path = self._path(key)
            path.unlink(missing_ok=True)
            if path.parent.exists() and not any(path.parent.iterdir()):
                path.parent.rmdir()

    def enqueue(self, db, operation, arguments, actor=None, request_id=None):
        if operation not in OPERATIONS:
            raise HTTPException(503, "Operazione non disponibile")
        encoded, uploads = self.encode_arguments(arguments)
        canonical = {k: {f: v for f, v in value.items() if f != "key"}
                     if value["kind"] == "upload" else value for k, value in encoded.items()}
        owner = actor.id if actor is not None else None
        fingerprint = _hash([operation, owner, _actor_snapshot(actor), canonical])
        request_key = _hash([owner, request_id]) if request_id else None
        try:
            for _ in range(3):
                receipt = db.get(Receipt, request_key) if request_key else None
                previous = db.get(Job, receipt.job_id) if receipt is not None else None
                if previous is not None:
                    if previous.fingerprint != fingerprint:
                        raise HTTPException(409, "La richiesta è già associata a dati diversi: aggiorna e riprova.")
                    return previous
                previous = db.scalar(select(Job).where(Job.active_key == fingerprint))
                if previous is not None:
                    if request_key:
                        db.add(Receipt(id=request_key, job_id=previous.id))
                        try:
                            db.commit()
                        except IntegrityError:
                            db.rollback()
                            continue
                    return previous
                job = Job(id=uuid4().hex, operation=operation, actor_id=owner,
                          actor_snapshot=_actor_snapshot(actor), revision=self.revision,
                          fingerprint=fingerprint, active_key=fingerprint, request_key=request_key,
                          request_data=encrypt_secret(_dump(encoded)), status="queued")
                db.add(job)
                try:
                    db.flush()
                    if request_key:
                        db.add(Receipt(id=request_key, job_id=job.id))
                    db.commit()
                    db.refresh(job)
                    uploads = []  # ownership transferred to the durable job
                    self.wake_event.set()
                    return job
                except IntegrityError:
                    db.rollback()  # a simultaneous click won the unique key
            raise HTTPException(503, "Aggiornamento già in avvio: riprova.")
        finally:
            self._remove_inputs(uploads)

    @contextmanager
    def _lock(self, connection, key):
        if connection.dialect.name == "postgresql":
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:ns, :key)"),
                                               {"ns": _NAMESPACE, "key": key}))
            connection.commit()
            try:
                yield acquired
            finally:
                if acquired and not connection.invalidated:
                    connection.rollback()
                    connection.execute(text("SELECT pg_advisory_unlock(:ns, :key)"),
                                       {"ns": _NAMESPACE, "key": key})
                    connection.commit()
        elif connection.dialect.name == "sqlite":
            lock_key = (str(connection.engine.url), key)
            with _sqlite_guard:
                acquired = lock_key not in _sqlite_locks
                if acquired:
                    _sqlite_locks.add(lock_key)
            try:
                yield acquired
            finally:
                if acquired:
                    with _sqlite_guard:
                        _sqlite_locks.discard(lock_key)
        else:
            raise RuntimeError("Unsupported background job database")

    @staticmethod
    def _job_key(job_id):
        return int(hashlib.sha256(job_id.encode()).hexdigest()[:7], 16) + 100

    @contextmanager
    def _physical_connection_fence(self, connection):
        # SQLAlchemy can reconnect an invalidated Connection after rollback.
        # That new socket no longer owns our PG session locks: it MUST NOT
        # continue business writes, even if a service catches a DB error.
        driver_connection = connection.connection.dbapi_connection
        def verify_owner(current, cursor, statement, parameters, context, executemany):
            if current.connection.dbapi_connection is not driver_connection:
                raise RuntimeError("Integration worker lost its owned database connection")
        event.listen(connection, 'before_cursor_execute', verify_owner)
        try:
            yield
        finally:
            event.remove(connection, 'before_cursor_execute', verify_owner)

    def _finish(self, connection, job_id, token, status, code, data):
        with Session(bind=connection, expire_on_commit=False) as db:
            job = db.get(Job, job_id)
            if job is None or job.status != "running" or job.worker_token != token:
                return False
            job.status, job.response_status = status, code
            job.response_data = encrypt_secret(_dump(data))
            job.finished_at, job.active_key = _now(), None
            db.commit()
            return True

    def _restore_arguments(self, fn, encoded, db, actor, stack):
        hints = get_type_hints(fn, include_extras=True)
        arguments = {}
        for name, item in encoded.items():
            if item["kind"] == "db":
                arguments[name] = db
            elif item["kind"] == "actor":
                arguments[name] = actor
            elif item["kind"] == "upload":
                path = self._path(item["key"])
                content = stack.enter_context(path.open("rb"))
                digest = hashlib.file_digest(content, "sha256").hexdigest()
                if digest != item["sha256"]:
                    raise HTTPException(409, "Il file in attesa non è più integro: ricaricalo.")
                content.seek(0)
                arguments[name] = UploadFile(file=content, filename=item["filename"],
                    headers=Headers({"content-type": item["content_type"] or "application/octet-stream"}))
            else:
                value = item["value"]
                arguments[name] = TypeAdapter(hints[name]).validate_python(value) if name in hints else value
        return arguments

    def _serialize_result(self, fn, result, job_id):
        if isinstance(result, FileResponse):
            source = Path(result.path)
            if not source.is_file() or source.is_symlink():
                raise HTTPException(404, "File non disponibile")
            key = job_id + "/result"
            target = self._path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with source.open("rb") as origin, target.open("xb") as output:
                while chunk := origin.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            return result.status_code, {"kind": "file", "key": key, "sha256": digest.hexdigest(),
                "filename": result.filename or source.name, "media_type": result.media_type}
        if isinstance(result, Response):
            if result.status_code == 204:
                return 204, {"kind": "json", "value": None}
            return result.status_code, {"kind": "json", "value": json.loads(result.body)}
        hint = get_type_hints(fn).get("return")
        value = TypeAdapter(hint).validate_python(result) if hint is not None else result
        return 200, {"kind": "json", "value": jsonable_encoder(value)}

    def run_one(self):
        with Session(self.engine) as db:
            candidates = list(db.execute(select(Job.id, Job.status).where(Job.status.in_(["queued", "running"]))
                .order_by(Job.created_at, Job.id).limit(50)))
        for job_id, observed in candidates:
            with self.engine.connect() as connection, self._lock(connection, self._job_key(job_id)) as locked:
                if not locked:
                    continue
                with Session(bind=connection, expire_on_commit=False) as db:
                    job = db.get(Job, job_id)
                    if job is None or job.status not in {"queued", "running"}:
                        continue
                    if job.status == "running":
                        # No owner lock means an actual stopped worker, not an
                        # old/slow operation. Never replay a possible write.
                        job.status, job.active_key, job.finished_at = "interrupted", None, _now()
                        job.response_status = 503
                        job.response_data = encrypt_secret(_dump({"detail":
                            "Operazione interrotta dal riavvio: controlla lo stato prima di riprovare."}))
                        db.commit()
                        return True
                for slot in (1, 2):
                    with self._lock(connection, slot) as available:
                        if not available:
                            continue
                        with self._physical_connection_fence(connection):
                            self._execute(connection, job_id)
                        return True
        return False

    def _execute(self, connection, job_id):
        token = uuid4().hex
        with Session(bind=connection, expire_on_commit=False) as db:
            job = db.get(Job, job_id)
            if job is None or job.status != "queued":
                return
            job.status, job.worker_token, job.started_at = "running", token, _now()
            db.commit()
            operation, owner, snapshot, revision = job.operation, job.actor_id, job.actor_snapshot, job.revision
            encoded = json.loads(decrypt_secret(job.request_data))
        uploads = [v["key"] for v in encoded.values() if v["kind"] == "upload"]
        try:
            fn = OPERATIONS.get(operation)
            if revision != self.revision or fn is None:
                raise HTTPException(503, "Applicazione aggiornata: controlla lo stato e ripeti l'operazione.")
            with Session(bind=connection, autoflush=False, expire_on_commit=False) as db, ExitStack() as stack:
                db.info["integration_background"] = True
                actor = db.get(User, owner) if owner is not None else None
                if owner is not None and (actor is None or not actor.active or _actor_snapshot(actor) != snapshot):
                    raise HTTPException(403, "Utente o permessi modificati: aggiorna e riprova.")
                arguments = self._restore_arguments(fn, encoded, db, actor, stack)
                result = fn(**arguments)
                code, data = self._serialize_result(fn, result, job_id)
                # Match get_db() request semantics: do not accidentally commit
                # incidental ORM changes merely to save the job's response.
                db.rollback()
            saved = self._finish(connection, job_id, token, "succeeded", code, data)
        except Exception as exc:
            connection.rollback()
            code = exc.status_code if isinstance(exc, HTTPException) else 500
            detail = exc.detail if isinstance(exc, HTTPException) else "Operazione non riuscita: aggiorna e riprova."
            saved = self._finish(connection, job_id, token, "failed", code, {"detail": detail})
        if saved:
            self._remove_inputs(uploads)

    def start(self):
        if self.threads and not self.stop_event.is_set():
            return
        self.stop_event = threading.Event()
        stop_event = self.stop_event
        def loop():
            while not stop_event.is_set():
                try:
                    worked = self.run_one()
                except Exception:
                    worked = False  # ownership/recovery is checked on next iteration
                if not worked:
                    self.wake_event.wait(1)
                    self.wake_event.clear()
        self.threads = []
        for index in range(2):
            thread = threading.Thread(target=loop, name=f"certi-integration-{index}", daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self):
        # No join of an indefinitely waiting SQL call and no cancellation of
        # live business work. Deployment must check pending/running jobs first.
        self.stop_event.set()
        self.wake_event.set()


def manager():
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = BackgroundManager(engine)
        return _manager


def ticket(job):
    return {"kind": "integration_wait", "job_id": job.id, "status": job.status,
            "poll_url": "/integration-jobs/" + job.id,
            "message": "Operazione in corso: attendo eSolver/Quarta."}


def background_response(fn):
    operation = register_operation(fn)
    signature = inspect.signature(fn)
    request_name = "_integration_request"
    @wraps(fn)
    def wrapped(*args, **kwargs):
        request = kwargs.pop(request_name, None)
        if request is None or "respond-async" not in request.headers.get("prefer", ""):
            return fn(*args, **kwargs)  # legacy clients retain the original API
        arguments = dict(signature.bind(*args, **kwargs).arguments)
        db = arguments.get("db")
        actor = next((v for v in arguments.values() if isinstance(v, User)), None)
        if actor is None and isinstance(db, Session):
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                from app.core.security.jwt import decode_token
                claims = decode_token(authorization[7:], expected_token_type="access")
                actor = db.get(User, int(claims["sub"]))
        if actor is None or not actor.active or not isinstance(db, Session):
            # Public closed PDF/export routes are deliberately not decorated.
            # Token-based legacy Word links preserve their existing behavior.
            return fn(*args, **kwargs)
        request_id = request.headers.get("x-certi-request-id")
        if request_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", request_id):
            raise HTTPException(422, "Identificativo richiesta non valido")
        job = manager().enqueue(db, operation, arguments, actor, request_id)
        return JSONResponse(ticket(job), status_code=202)
    wrapped.__signature__ = signature.replace(parameters=[*signature.parameters.values(),
        inspect.Parameter(request_name, inspect.Parameter.KEYWORD_ONLY, annotation=Request)])
    return wrapped
