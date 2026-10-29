"""Preview/backfill existing readings. Never calls AI, changes matches or files.

Default: read-only preview. Apply requires its exact current SHA256, no active
run, NOWAIT locks and an external verified backup as described in the runbook.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text
from sqlalchemy.orm import selectinload

# Register the existing tables/relationships, but DO NOT initialize/seed the app.
from app.startup import bootstrap  # noqa: F401
from app.core.database import SessionLocal
from app.modules.acquisition.certificate_ai_reuse import cached_payload
from app.modules.acquisition.manual_document_protection import manual_document_reason, mark_manual_entry, MANUAL_ENTRY_EVIDENCE
from app.modules.acquisition.models import (
    AcquisitionHistoryEvent, AcquisitionRow, AutonomousProcessingRun, Document, DocumentAiExtraction,
    DocumentAiUsage, DocumentEvidence, DocumentPage, ReadValue,
)
from app.modules.document_reader.registry import resolve_supplier_template


def source_digest(db, *, new_manual_marker_ids=()):
    snapshot = {}
    for model in (Document, DocumentPage, DocumentEvidence, AcquisitionRow, ReadValue, AutonomousProcessingRun, AcquisitionHistoryEvent):
        query = db.query(model)
        if model is DocumentEvidence and new_manual_marker_ids:
            query = query.filter(DocumentEvidence.id.notin_(new_manual_marker_ids))
        records = query.order_by(model.id).all()
        snapshot[model.__tablename__] = [{column.name:getattr(record,column.name)
                                        for column in model.__table__.columns} for record in records]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def preview(db):
    has_cache = inspect(db.connection()).has_table(DocumentAiExtraction.__tablename__)
    counts = Counter()
    documents = []
    for doc in (db.query(Document).options(selectinload(Document.pages), selectinload(Document.supplier))
                .filter_by(tipo_documento="certificato").order_by(Document.id)):
        template = resolve_supplier_template(doc.supplier.ragione_sociale if doc.supplier else None,
                                             doc.nome_file_originale)
        if manual_document_reason(db, doc):
            status = "manual_no_automatic_ai"
        elif template is None:
            status = "unsupported"
        else:
            payload = cached_payload(db, doc, template.supplier_key, persist_legacy=False,
                                     cache_table_available=has_cache)
            status = payload.get("_reuse_source", "stored") if payload is not None else "needs_read_or_review"
        counts[status] += 1
        documents.append({"document_id":doc.id,"status":status})
    active = [r.id for r in db.query(AutonomousProcessingRun).filter(
        AutonomousProcessingRun.stato.in_(("in_coda","in_esecuzione"))).all()]
    manual_ddt = [{"document_id":d.id,"reason":reason} for d in db.query(Document).filter_by(tipo_documento="ddt")
                  if (reason := manual_document_reason(db,d))]
    return {"digest":source_digest(db),"schema_present":has_cache,"active_runs":active,"manual_ddt":manual_ddt,
            "counts":dict(counts),"documents":documents}


def apply(db, expected_digest):
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Apply is restricted to PostgreSQL; use isolated tests for development.")
    db.execute(text("SET LOCAL lock_timeout='2s'"))
    db.execute(text("SET LOCAL statement_timeout='60s'"))
    db.execute(text("LOCK TABLE documenti_fornitore, documenti_fornitore_pagine, documenti_evidenze, "
                    "datimaterialeincoming, valori_letti_acquisition, acquisition_processing_runs, storico_eventi_acquisition "
                    "IN SHARE ROW EXCLUSIVE MODE NOWAIT"))
    plan = preview(db)
    if plan["active_runs"]:
        raise RuntimeError("Active AI runs: apply refused without interrupting them.")
    if plan["digest"] != expected_digest:
        raise RuntimeError("Source data changed: obtain a new read-only preview and approval.")
    DocumentAiExtraction.__table__.create(db.connection(), checkfirst=True)
    DocumentAiUsage.__table__.create(db.connection(), checkfirst=True)
    # Add only document policy markers approved by this exact preview. They
    # preserve manual provenance even if fields are cleared or rows merged later.
    manual_ids = [item['document_id'] for item in plan['documents'] if item['status']=='manual_no_automatic_ai']
    manual_ids += [item['document_id'] for item in plan['manual_ddt']]
    previous_marker_ids = {i for (i,) in db.query(DocumentEvidence.id).filter_by(tipo_evidenza=MANUAL_ENTRY_EVIDENCE)}
    for document_id in manual_ids:
        mark_manual_entry(db, db.get(Document, document_id), actor_id=None)
    new_marker_ids = sorted({i for (i,) in db.query(DocumentEvidence.id).filter_by(tipo_evidenza=MANUAL_ENTRY_EVIDENCE)} - previous_marker_ids)
    new_manual_document_ids = [i for (i,) in db.query(DocumentEvidence.document_id).filter(DocumentEvidence.id.in_(new_marker_ids))]
    db.info["ai_extraction_cache_transactional"] = True
    try:
        for doc in (db.query(Document).options(selectinload(Document.pages),selectinload(Document.supplier))
                    .filter_by(tipo_documento="certificato").order_by(Document.id)):
            template = resolve_supplier_template(doc.supplier.ragione_sociale if doc.supplier else None,
                                                 doc.nome_file_originale)
            if template is not None:
                cached_payload(db,doc,template.supplier_key,persist_legacy=True)
        if source_digest(db, new_manual_marker_ids=new_marker_ids) != expected_digest:
            raise RuntimeError("Business data changed unexpectedly: the whole transaction will roll back.")
        records = db.query(DocumentAiExtraction).count()
        db.commit()
        return {"applied":True,"cached_readings":records,"business_data_unchanged":True,
                "added_manual_policy_document_ids":new_manual_document_ids,
                "added_manual_policy_evidence_ids":new_marker_ids,"source_digest":expected_digest}
    finally:
        db.info.pop("ai_extraction_cache_transactional",None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--expected-digest")
    parser.add_argument("--maintenance-confirmed",action="store_true")
    parser.add_argument("--backup",type=Path)
    args = parser.parse_args()
    if args.apply and not args.expected_digest:
        parser.error("--apply requires --expected-digest from a current preview")
    backup_hash = None
    if args.apply:
        if not args.maintenance_confirmed or args.backup is None:
            parser.error("--apply also requires --maintenance-confirmed and a verified --backup")
        if not args.backup.is_file() or args.backup.stat().st_size < 1024:
            parser.error("backup is missing or too small")
        with args.backup.open("rb") as source:
            prefix = source.read(4096)
            if not (prefix.startswith(b"PGDMP") or prefix.startswith(b"\x1f\x8b") or b"PostgreSQL database dump" in prefix):
                parser.error("backup is not a recognized PostgreSQL dump or compressed archive")
            source.seek(0)
            backup_hash = hashlib.file_digest(source,"sha256").hexdigest()
    with SessionLocal() as db:
        try:
            if not args.apply and db.get_bind().dialect.name == "postgresql":
                db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            result = apply(db,args.expected_digest) if args.apply else preview(db)
            if backup_hash:
                result["backup_sha256"] = backup_hash
            print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            db.rollback()


if __name__ == "__main__":
    main()
