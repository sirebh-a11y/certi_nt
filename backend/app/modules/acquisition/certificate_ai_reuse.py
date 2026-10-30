"""Reuse document readings, not Incoming rows and never match decisions.

The supplier readers, prompts, normalizers and matching thresholds remain in
service.py. Incoming values, even confirmed ones, are never reconstructed as a
document-wide reading: they can contain interpretation or shipment-specific
corrections. No business rows are changed by this module.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import json
import logging
import threading
import time
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from .ai_usage import independent_writer, usage_scope, write_independent
from .models import AcquisitionRow, DocumentAiExtraction, DocumentEvidence
from .document_type_guard import DocumentTypeReviewRequired
from .manual_document_protection import automatic_ai_disabled, require_ai_allowed

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 1
_refresh = ContextVar("certificate_ai_explicit_refresh", default=None)
_locks_guard = threading.Lock()
_locks = {}
_connection_engines = WeakKeyDictionary()


@contextmanager
def explicit_refresh(document_id):
    """One fresh reading per explicit action, shared by core/chemistry/notes."""
    token = _refresh.set({document_id: False} if document_id is not None else {})
    try:
        yield
    finally:
        _refresh.reset(token)


def _identity(document, reader_key):
    file_hash = document.hash_file
    if document.tipo_documento != "certificato" or not isinstance(file_hash, str) or len(file_hash) < 16:
        return None
    parts = {
        "hash": file_hash, "supplier": document.fornitore_id, "reader": reader_key,
        "type": document.tipo_documento, "schema": SCHEMA_VERSION,
        "pages": sorted((p.id, p.numero_pagina) for p in document.pages),
        "expected_pages":document.numero_pagine or len(document.pages),
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


@contextmanager
def _document_lock(db, document_id, timeout=240.0):
    # The lock belongs to the document, not the fingerprint: changing metadata
    # must not permit two concurrent extractions of the same document.
    key = int.from_bytes(hashlib.sha256(f"certi-ai-certificate:{document_id}".encode()).digest()[:8], "big", signed=True)
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        with _locks_guard:
            lock = _locks.setdefault((str(bind.url), document_id), threading.Lock())
        if not lock.acquire(timeout=timeout):
            raise HTTPException(409, "Lettura AI del documento gia in corso; nessuna lettura duplicata avviata.")
        try:
            yield
        finally:
            lock.release()
        return
    # A dedicated session advisory lock spans network work, without holding a
    # row lock or an open SQL transaction on business tables.
    # Do not exhaust the business pool: otherwise N workers could each hold
    # their business connection and wait forever for an extra lock/writer slot.
    with _locks_guard:
        connection_engine = _connection_engines.get(bind)
        if connection_engine is None:
            connection_engine = create_engine(bind.url, poolclass=NullPool, connect_args={"connect_timeout":5})
            _connection_engines[bind] = connection_engine
    search_path = db.execute(text("SHOW search_path")).scalar()
    with connection_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("SELECT set_config('search_path', :path, false)"), {"path":search_path})
        deadline = time.monotonic() + timeout
        while not connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar():
            if time.monotonic() >= deadline:
                raise HTTPException(409, "Lettura AI del documento gia in corso; nessuna lettura duplicata avviata.")
            time.sleep(0.2)
        try:
            with independent_writer(connection):
                yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def _valid_payload(payload, document):
    expected = document.numero_pagine or len(document.pages)
    if not expected or len(document.pages) != expected or {p.numero_pagina for p in document.pages} != set(range(1,expected+1)):
        return False
    if not isinstance(payload, dict) or not isinstance(payload.get("match_values"), dict):
        return False
    if not any(payload["match_values"].values()):
        return False  # no-images/empty/error is not a successfully read document
    if any(value is not None and not isinstance(value, str) for value in payload["match_values"].values()):
        return False
    page_ids = {p.id for p in document.pages}
    for block in ("chemistry", "properties", "notes", "mechanical_requirement"):
        values = payload.get(block) or {}
        if not isinstance(values, dict):
            return False
        for value in values.values():
            if isinstance(value, dict) and value.get("page_id"):
                try:
                    if int(value["page_id"]) not in page_ids:
                        return False
                except (TypeError, ValueError):
                    return False
    return True


def _latest_type_failure(db, document_id):
    check = (db.query(DocumentEvidence).filter_by(document_id=document_id,
             tipo_evidenza="leichtmetall_document_type_check").order_by(DocumentEvidence.id.desc()).first())
    if check is None:
        return False
    try:
        return json.loads(check.testo_grezzo or "{}").get("decision") == "da_verificare"
    except (TypeError, ValueError):
        return True


def _record_verified_type_after_reread(db, document, reader_key, payload):
    if reader_key != "leichtmetall" or not _latest_type_failure(db, document.id):
        return
    raw = json.loads(payload.get("debug_raw_output") or "{}")
    check = raw.get("document_check") or {}
    if check.get("detected_type") == "certificato" and check.get("matches_assigned") is True:
        def verified(writer):
            writer.add(DocumentEvidence(document_id=document.id, blocco="documento",
                tipo_evidenza="leichtmetall_document_type_check", metodo_estrazione="chatgpt",
                mascherato=True, testo_grezzo=json.dumps({"initial_type":"certificato",
                "final_type":"certificato", "decision":"confermato", "checks":[check]})))
        write_independent(db, verified)


def _normalizer_payload(document, reader_key, raw):
    from . import service as s
    # All existing supplier selectors send one image per physical page. Only
    # page identity is needed to replay their pure normalizers, not image bytes.
    pages = sorted(document.pages, key=lambda p: p.numero_pagina)
    images = {}
    for i,p in enumerate(pages):
        suffix = ("core_context" if reader_key == "aluminium_bozen" else "core_page") if i == 0 else "continuation_page"
        if reader_key == "zalco":
            suffix = "core_page"  # its selector prefers core context on every page
        images[f"page{p.numero_pagina}_{suffix}"] = {
            "page_id":p.id, "page_number":p.numero_pagina,
            "source_text":"\n".join(filter(None,[p.testo_estratto,p.ocr_text])),
        }
    normalizer = getattr(s, f"_normalize_{reader_key}_certificate_ai_payload", None)
    if normalizer is None or not images:
        return None
    payload = normalizer(images, raw)
    if reader_key == "aww":
        payload = s._enrich_aww_certificate_ai_payload_from_pages(payload, pages)
    return payload


def _type_reusable(db, document, reader_key, payload):
    if reader_key != "leichtmetall":
        return True
    if _latest_type_failure(db, document.id):
        return False
    try:
        check = json.loads(payload.get("debug_raw_output") or "{}").get("document_check") or {}
        if check.get("detected_type") == "certificato" and check.get("matches_assigned") is True:
            return True
    except (TypeError, ValueError):
        return False
    # Legacy documents already finally validated by a human are not new uploads
    # to retype. Their original reading stays usable without weakening the guard
    # for new, uncertain, mixed or rejected documents.
    return db.query(AcquisitionRow.id).filter_by(document_certificato_id=document.id, validata_finale=True).first() is not None


def remember_checked_payload(db, document, reader_key, payload):
    """Persist a successful type-rerouted read only after the final type commit."""
    fingerprint = _identity(document, reader_key)
    if fingerprint and _valid_payload(payload, document):
        if payload.get("_reuse_fingerprint") != fingerprint:
            with _document_lock(db, document.id):
                _save(db, document, reader_key, fingerprint, payload, "ai")
        payload["_reuse_fingerprint"] = fingerprint
        payload["_reuse_source"] = "ai"


def _save(db, document, reader_key, fingerprint, payload, source, evidence_id=None):
    # Do not persist view/row corrections or metadata added while applying a row.
    serializable = {k:v for k,v in payload.items() if not k.startswith("_reuse_")}
    encoded = json.dumps(serializable, ensure_ascii=False)
    def write(writer):
        cached = writer.query(DocumentAiExtraction).filter_by(document_id=document.id, fingerprint=fingerprint).first()
        if cached is None:
            cached = DocumentAiExtraction(document_id=document.id, fingerprint=fingerprint,
                file_hash=document.hash_file, reader_key=reader_key, schema_version=SCHEMA_VERSION,
                supplier_id=document.fornitore_id, payload_json=encoded, source=source)
            writer.add(cached)
        else:
            cached.payload_json = encoded
            cached.source = source
        cached.file_hash = document.hash_file
        cached.reader_key = reader_key
        cached.supplier_id = document.fornitore_id
        cached.schema_version = SCHEMA_VERSION
        cached.source_evidence_id = evidence_id
    write_independent(db, write)


def _recover_saved_metalba_alloy(payload, reader_key):
    """Recover the two formerly discarded spellings from the SAME saved read.

    Pure, field-only compatibility fix: no schema/fingerprint invalidation,
    new AI, cache writes, chemistry re-normalization or Incoming backfill.
    Never replace a populated value, even when the old raw JSON differs.
    """
    if reader_key != "metalba" or not isinstance(payload, dict):
        return payload
    match_values = payload.get("match_values") or {}
    core_fields = payload.get("core_fields") or {}
    if not isinstance(match_values, dict) or not isinstance(core_fields, dict):
        return payload
    if not isinstance(core_fields.get("lega_certificato") or {}, dict):
        return payload
    if match_values.get("lega_certificato") or (core_fields.get("lega_certificato") or {}).get("value"):
        return payload
    try:
        raw = json.loads(payload.get("debug_raw_output") or "{}")
        core = raw.get("core") or {}
        alloy = core.get("lega")
        if not isinstance(alloy, str) or alloy.strip().upper() not in {"6082F", "6082FF"}:
            return payload
    except (TypeError, ValueError, AttributeError):
        return payload
    from . import service as s
    field = s._sanitize_metalba_vision_certificate_fields({"lega": alloy}, None)["lega_certificato"]
    if not field.get("value"):
        return payload
    result = deepcopy(payload)
    result["match_values"] = {**match_values, "lega_certificato": field["value"]}
    existing_field = deepcopy(core_fields.get("lega_certificato") or {})
    existing_field.update(value=field["value"], evidence=field["evidence"])
    result["core_fields"] = {**core_fields, "lega_certificato": existing_field}
    return result


def cached_payload(db, document, reader_key, *, persist_legacy=False, cache_table_available=True):
    """No images, no AI and no changes to Incoming. Used also by type preflight."""
    if automatic_ai_disabled(db, document):
        return None
    fingerprint = _identity(document, reader_key)
    if fingerprint is None:
        return None
    expected = document.numero_pagine or len(document.pages)
    if not expected or len(document.pages) != expected or {p.numero_pagina for p in document.pages} != set(range(1,expected+1)):
        return None
    if reader_key == "leichtmetall" and _latest_type_failure(db, document.id):
        return None
    cached = (db.query(DocumentAiExtraction).filter_by(document_id=document.id, fingerprint=fingerprint).first()
              if cache_table_available else None)
    if cached is not None and (cached.file_hash,cached.reader_key,cached.supplier_id,cached.schema_version) == (
            document.hash_file,reader_key,document.fornitore_id,SCHEMA_VERSION):
        try:
            payload = json.loads(cached.payload_json)
        except (TypeError, ValueError):
            payload = None
        if _valid_payload(payload, document) and _type_reusable(db, document, reader_key, payload):
            payload = _recover_saved_metalba_alloy(payload, reader_key)
            payload["_reuse_fingerprint"] = fingerprint
            payload["_reuse_source"] = cached.source
            payload["_reuse_persisted"] = True
            return payload
    # Legacy evidence has no file hash. Once a different content hash is known,
    # never reinterpret that old evidence as a reading of the replacement PDF.
    known = db.query(DocumentAiExtraction.file_hash,DocumentAiExtraction.reader_key,DocumentAiExtraction.supplier_id).filter_by(document_id=document.id).all() if cache_table_available else []
    if known and any(h != document.hash_file or key != reader_key or supplier != document.fornitore_id for h,key,supplier in known):
        return None
    evidence = (db.query(DocumentEvidence).filter_by(document_id=document.id, tipo_evidenza="ai_payload")
                .order_by(DocumentEvidence.id.desc()).all())
    for item in evidence:
        if item.document_page_id and item.document_page_id not in {p.id for p in document.pages}:
            continue
        try:
            raw = json.loads(item.testo_grezzo or "null")
            if not isinstance(raw, dict) or not isinstance(raw.get("core"), dict):
                continue
            payload = _normalizer_payload(document, reader_key, raw)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        if not _valid_payload(payload, document) or not _type_reusable(db, document, reader_key, payload):
            continue
        if persist_legacy and cache_table_available:
            _save(db, document, reader_key, fingerprint, payload, "legacy_evidence", item.id)
        payload["_reuse_fingerprint"] = fingerprint
        payload["_reuse_source"] = "legacy_evidence"
        return payload
    return None


def reuse_certificate_payload(reader_key):
    def decorate(reader):
        @wraps(reader)
        def read(db, *, certificate_document, openai_api_key, certificate_ai_cache=None):
            document = certificate_document
            require_ai_allowed(db, document)
            if isinstance(db, Session) and reader_key == "leichtmetall" and document.id in db.info.get("leichtmetall_type_blocked", set()):
                raise DocumentTypeReviewRequired("documento gia fermato in questo run; verificare il tipo.")
            if not isinstance(db, Session) or _identity(document, reader_key) is None:
                if isinstance(db, Session):
                    with usage_scope(db, document):
                        return reader(db, certificate_document=document, openai_api_key=openai_api_key,
                                      certificate_ai_cache=certificate_ai_cache)
                return reader(db, certificate_document=document, openai_api_key=openai_api_key,
                              certificate_ai_cache=certificate_ai_cache)
            refresh = _refresh.get()
            force = refresh is not None and document.id in refresh and not refresh[document.id]
            fingerprint = _identity(document, reader_key)
            memory = certificate_ai_cache.get(document.id) if certificate_ai_cache is not None else None
            type_failed = reader_key == "leichtmetall" and _latest_type_failure(db, document.id)
            if not force and not type_failed and memory is not None and memory.get("_reuse_fingerprint", fingerprint) == fingerprint:
                if not memory.get("_reuse_persistence_pending"):
                    return deepcopy(_recover_saved_metalba_alloy(memory, reader_key))
            if not force and not (memory or {}).get("_reuse_persistence_pending"):
                existing = cached_payload(db, document, reader_key)
                if existing is not None and existing.get("_reuse_persisted"):
                    if certificate_ai_cache is not None:
                        certificate_ai_cache[document.id] = deepcopy(existing)
                    return deepcopy(existing)
            with _document_lock(db, document.id):
                pending = (_recover_saved_metalba_alloy(memory, reader_key)
                           if memory and memory.get("_reuse_persistence_pending") else None)
                payload = deepcopy(pending) if pending else (None if force else cached_payload(db, document, reader_key,persist_legacy=True))
                needs_save = pending is not None
                if payload is None:
                    with usage_scope(db, document):
                        try:
                            payload = reader(db, certificate_document=document, openai_api_key=openai_api_key,
                                             certificate_ai_cache={})
                        except DocumentTypeReviewRequired as exc:
                            # A failed explicit type reread must not silently
                            # resurrect an older accepted reading on the next run.
                            check = exc.check
                            def failed_guard(writer):
                                writer.add(DocumentEvidence(document_id=document.id,blocco="documento",
                                    tipo_evidenza="leichtmetall_document_type_check",metodo_estrazione="chatgpt",
                                    mascherato=True,testo_grezzo=json.dumps({"initial_type":document.tipo_documento,
                                    "final_type":document.tipo_documento,"decision":"da_verificare",
                                    "checks":[check] if check else [],"reason":"Controllo tipo non superato."})))
                            try:
                                write_independent(db,failed_guard)
                            except Exception:
                                logger.error("Unable to record failed type check for document %s",document.id)
                            raise
                    fingerprint = _identity(document, reader_key)
                    payload = deepcopy(payload)
                    payload["_reuse_source"] = "ai"
                    payload["_reuse_fingerprint"] = fingerprint
                    needs_save = bool(fingerprint and _valid_payload(payload, document))
                if force:
                    refresh[document.id] = True
                if needs_save:
                    # Retain an already paid response before attempting to save.
                    # Recovery attempts repeat only this write, never the API.
                    payload["_reuse_persistence_pending"] = True
                    if certificate_ai_cache is not None:
                        certificate_ai_cache[document.id] = deepcopy(payload)
                    for attempt in range(2):
                        try:
                            _save(db, document, reader_key, fingerprint, payload, "ai")
                            _record_verified_type_after_reread(db,document,reader_key,payload)
                            break
                        except Exception:
                            if attempt == 1:
                                logger.error("AI reading available but cache save failed for document %s",document.id)
                                raise HTTPException(409,"Lettura AI completata ma salvataggio non riuscito. Il risultato resta nell'elaborazione corrente; non dichiarare il documento completato.") from None
                    payload.pop("_reuse_persistence_pending",None)
                if certificate_ai_cache is not None:
                    certificate_ai_cache[document.id] = deepcopy(payload)
                return deepcopy(payload)
        return read
    return decorate
