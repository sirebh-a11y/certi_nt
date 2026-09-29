"""Reviewable Alpha recovery plans; application is always a separate operation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.database import Base
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.ddt_legacy_audit import classify_legacy_cache, table_exists
from app.modules.quarta_taglio.ddt_legacy_import import import_legacy_cache
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _fetch_complete_snapshot, _LOCK_ID, _LOCK_NAMESPACE
from app.modules.quarta_taglio.models import (
    QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem,
    QuartaTaglioEsolverLink, QuartaTaglioFinalCertificate, QuartaTaglioRow,
)

PLAN_VERSION = 1
PLAN_MAX_AGE = timedelta(hours=1)
ALPHA_HOST = "certi-test.forgialluminio.it"
INPUT_MODELS = (QuartaTaglioEsolverLink, QuartaTaglioRow, QuartaTaglioFinalCertificate,
                QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtWorkItem, QuartaTaglioDdtSyncRun)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def validate_alpha_settings(settings):
    url = make_url(settings.database_url)
    if (url.get_backend_name() != "postgresql" or url.host != "postgres"
            or url.database != "certi_nt" or url.port not in (None, 5432)
            or settings.app_env.lower() not in {"alpha", "production"}
            or urlsplit(settings.certi_public_base_url).hostname != ALPHA_HOST):
        raise SnapshotError("alpha_environment_mismatch")
    if settings.ddt_snapshot_enabled:
        raise SnapshotError("disable_snapshot_before_recovery")


def alpha_database_identity(db, settings):
    validate_alpha_settings(settings)
    identity = db.execute(text("SELECT current_database() AS database, system_identifier::text AS cluster "
                               "FROM pg_control_system()" )).mappings().one()
    if identity["database"] != "certi_nt":
        raise SnapshotError("alpha_database_mismatch")
    return dict(environment="alpha", public_host=ALPHA_HOST,
                database_id=_digest(dict(identity)), storage_root=str(Path(settings.document_storage_root).resolve()))


def _file_fact(key):
    if not key:
        return None
    try:
        path = service._certificate_storage_path(key)
        stat = path.stat()
        return [str(key), path.is_file(), stat.st_size, stat.st_mtime_ns]
    except Exception:
        return [str(key), "unavailable"]


def build_recovery_plan(db, *, current_rows, target, now=None):
    """No writes and no credentials in the report. Hash all decision inputs."""
    now = now or datetime.now(timezone.utc)
    audit, candidates = classify_legacy_cache(db, current_rows=current_rows)
    inputs, file_facts = {}, []
    for model in INPUT_MODELS:
        records = list(db.execute(select(model.__table__)).mappings()) if table_exists(db, model) else []
        # An absent queue table and an empty queue have the same data semantics.
        inputs[model.__tablename__] = sorted(_json(dict(row)) for row in records)
        if model is QuartaTaglioFinalCertificate:
            for row in records:
                file_facts.extend([_file_fact(row["storage_key_pdf"]), _file_fact(row["storage_key_docx"])])
    code_files = ("ddt_recovery.py", "ddt_legacy_audit.py", "ddt_legacy_import.py", "ddt_snapshot.py",
                  "ddt_context.py", "ddt_queue.py", "service.py")
    algorithm = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in code_files}
    facts = dict(target=target, source=sorted(_json(row) for row in current_rows), database=inputs,
                 files=sorted(_json(fact) for fact in file_facts), algorithm=algorithm, audit=audit)
    return dict(version=PLAN_VERSION, generated_at=now.isoformat(), target=target,
                plan_id=_digest(facts), audit=audit,
                historical_candidates=[{field: str(getattr(item, field)) if getattr(item, field) is not None else None
                    for field in ("source_key", "id_documento", "id_riga_doc", "cod_odp", "ddt_raw", "quantita")}
                    for item in sorted(candidates, key=lambda i: i.source_key)])


def validate_approved_plan(approved, current, *, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        generated = datetime.fromisoformat(approved["generated_at"])
        age = now - generated
    except (KeyError, TypeError, ValueError):
        raise SnapshotError("invalid_approved_report") from None
    if generated.tzinfo is None or age < timedelta(0) or age > PLAN_MAX_AGE:
        raise SnapshotError("approved_report_expired")
    if approved.get("version") != PLAN_VERSION or approved.get("target") != current["target"]:
        raise SnapshotError("approved_report_wrong_target")
    if approved.get("plan_id") != current["plan_id"]:
        raise SnapshotError("recovery_data_changed_repeat_audit")
    if current["audit"]["status"] != "classified":
        raise SnapshotError("legacy_source_baseline_required")


def lock_recovery_inputs(db):
    """Same advisory lock as the job; table locks protect against old-cache UI refreshes.

    Caller must use READ COMMITTED so reads AFTER the locks see latest commits.
    NOWAIT refuses an active writer instead of waiting/interfering with users.
    """
    if db.get_bind().dialect.name != "postgresql":
        raise SnapshotError("alpha_requires_postgresql")
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:n, :k)"), {"n": _LOCK_NAMESPACE, "k": _LOCK_ID}):
        raise SnapshotError("snapshot_busy")
    for model in INPUT_MODELS:
        if table_exists(db, model):
            table = db.get_bind().dialect.identifier_preparer.format_table(model.__table__)
            schema_map = db.connection().get_execution_options().get("schema_translate_map", {})
            if None in schema_map:  # Isolated PostgreSQL test schemas.
                table = db.get_bind().dialect.identifier_preparer.quote_schema(schema_map[None]) + "." + table
            mode = "SHARE ROW EXCLUSIVE" if model in (QuartaTaglioDdtWorkItem, QuartaTaglioDdtSyncRun) else "SHARE"
            try:
                db.execute(text(f"LOCK TABLE {table} IN {mode} MODE NOWAIT"))
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) == "55P03":
                    raise SnapshotError("recovery_inputs_busy") from None
                raise


def apply_approved_recovery(db, *, approved, target, fetch_source=_fetch_complete_snapshot, now=None):
    """Caller owns a READ COMMITTED transaction. Any failure rolls back all writes."""
    lock_recovery_inputs(db)
    rows = fetch_source(db)
    current = build_recovery_plan(db, current_rows=rows, target=target, now=now)
    validate_approved_plan(approved, current, now=now)
    Base.metadata.create_all(db.connection(), tables=[QuartaTaglioDdtWorkItem.__table__, QuartaTaglioDdtSyncRun.__table__])
    return import_legacy_cache(db, current_rows=rows, now=now)
