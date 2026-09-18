"""Run preflight for Leichtmetall, before creating any incoming rows.

Only unused temporary documents explicitly submitted in this run can be retyped.
Both reads must succeed before the type is committed. Other suppliers bypass it.
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import or_

from app.core.config import settings
from .document_type_guard import DocumentTypeReviewRequired, require_complete_pages
from .models import AcquisitionRow, CertificateMatch, CertificateMatchCandidate, Document, DocumentEvidence, ManualMatchBlock

DDT_CACHE_KEY = "leichtmetall_ddt_checked"
BLOCKED_KEY = "leichtmetall_type_blocked"
CHECKED_KEY = "leichtmetall_type_checked"
EVIDENCE_TYPE = "leichtmetall_document_type_check"


def is_leichtmetall(document):
    from . import service as s
    template = s.resolve_supplier_template(
        document.supplier.ragione_sociale if document.supplier is not None else None,
        document.nome_file_originale,
    )
    return template is not None and template.supplier_key == "leichtmetall"


def can_retype(db, document):
    if document.stato_upload != "temporaneo" or document.documento_padre_id is not None:
        return False
    references = (
        (AcquisitionRow, or_(AcquisitionRow.document_ddt_id == document.id, AcquisitionRow.document_certificato_id == document.id)),
        (CertificateMatch, CertificateMatch.document_certificato_id == document.id),
        (CertificateMatchCandidate, CertificateMatchCandidate.document_certificato_id == document.id),
        (ManualMatchBlock, or_(ManualMatchBlock.document_ddt_id == document.id, ManualMatchBlock.document_certificato_id == document.id)),
        (DocumentEvidence, (DocumentEvidence.document_id == document.id) & DocumentEvidence.acquisition_row_id.is_not(None)),
        (Document, Document.documento_padre_id == document.id),
    )
    return not any(db.query(model.id).filter(condition).first() is not None for model, condition in references)


def record_check(db, document, *, initial_type, decision, checks, actor_id, reason=None):
    db.add(DocumentEvidence(
        document_id=document.id, blocco="documento", tipo_evidenza=EVIDENCE_TYPE,
        metodo_estrazione="chatgpt", mascherato=True, utente_creazione_id=actor_id,
        testo_grezzo=json.dumps({
            "initial_type": initial_type, "final_type": document.tipo_documento,
            "decision": decision, "checks": checks, "reason": reason,
            "model": settings.document_vision_model,
        }, ensure_ascii=False),
    ))
    db.commit()


def read_document(db, document, assigned, api_key):
    from . import service as s
    processing_state = document.stato_elaborazione
    if not document.pages:
        document = s._index_document_from_path(db, document)
    document = s._ensure_document_page_images(db, document)
    if processing_state == "in_lavorazione" and document.stato_elaborazione != processing_state:
        document.stato_elaborazione = processing_state
        db.add(document)
        db.commit()
    pages = document.pages
    require_complete_pages(document)
    if assigned == "ddt":
        crops = s._build_leichtmetall_ddt_group_crops(pages)
        number, rows, raw = s._extract_leichtmetall_ddt_row_groups_from_openai(crops, openai_api_key=api_key)
        check = s._parse_openai_json_payload_for_certificate_bundle(raw)["document_check"]
        if not rows:
            raise DocumentTypeReviewRequired("DDT riconosciuto ma senza righe leggibili.", check=check)
        if not number:
            matches = s.reader_detect_ddt_core_matches(pages, supplier_key="leichtmetall")
            number = s._split_plan_match_value(matches, "ddt")
        payload = s._sanitize_leichtmetall_ai_row_groups(ddt_number_raw=number, raw_rows=rows, ai_document_payload_raw=raw)
        payload = s._reconcile_leichtmetall_ai_candidates_with_document(ddt_document=document, ai_candidates=payload)
        if not payload:
            raise DocumentTypeReviewRequired("nessuna riga DDT utilizzabile.", check=check)
    else:
        crops = s._select_leichtmetall_certificate_document_images(s._build_leichtmetall_certificate_safe_crops(pages))
        raw = s._extract_leichtmetall_certificate_payload_from_openai(crops, openai_api_key=api_key)
        check = raw["document_check"]
        payload = s._normalize_leichtmetall_certificate_ai_payload(crops, raw)
        if not any(payload.get("match_values", {}).values()):
            raise DocumentTypeReviewRequired("certificato riconosciuto ma privo di dati identificativi leggibili.", check=check)
    return payload, check


def preflight_documents(db, documents, *, explicit_ids, certificate_ai_cache, api_key, actor_id, actor_email):
    from . import service as s
    accepted = []
    failed = []
    checked = db.info.setdefault(CHECKED_KEY, set())
    blocked = db.info.setdefault(BLOCKED_KEY, set())
    for document in documents:
        if document.id in blocked:
            continue
        if not is_leichtmetall(document) or document.id in checked:
            accepted.append(document)
            continue
        initial = document.tipo_documento
        checks = []
        try:
            try:
                payload, check = read_document(db, document, initial, api_key)
                target = initial
            except DocumentTypeReviewRequired as mismatch:
                if mismatch.check:
                    checks.append(mismatch.check)
                target = mismatch.check.get("detected_type") if mismatch.check else None
                if target not in {"ddt", "certificato"} or target == initial:
                    raise
                if document.id not in explicit_ids or not can_retype(db, document):
                    raise DocumentTypeReviewRequired(
                        "il tipo rilevato non coincide, ma il documento e' gia utilizzato o persistente: "
                        "nessun collegamento o dato esistente viene modificato.", check=mismatch.check,
                    ) from mismatch
                # One reroute only. A second disagreement propagates to review.
                payload, check = read_document(db, document, target, api_key)
            checks.append(check)
            if target != initial:
                locked = db.query(Document).filter(Document.id == document.id).with_for_update().populate_existing().one()
                if locked.tipo_documento != initial or not can_retype(db, locked):
                    raise DocumentTypeReviewRequired("documento modificato o collegato durante la lettura; serve verifica.")
                locked.tipo_documento = target
                db.add(locked)
            record_check(db, document, initial_type=initial, decision="corretto" if target != initial else "confermato", checks=checks, actor_id=actor_id)
            if target == "ddt":
                db.info.setdefault(DDT_CACHE_KEY, {})[document.id] = payload
            else:
                certificate_ai_cache[document.id] = payload
            checked.add(document.id)
            accepted.append(document)
            s.log_service.record("acquisition", f"Leichtmetall document {document.id}: {initial} -> {target}; type checked", actor_email)
        except HTTPException as exc:
            if isinstance(exc, DocumentTypeReviewRequired) and exc.check and exc.check not in checks:
                checks.append(exc.check)
            reason = str(exc.detail)
            # No extraction/cache fallback and no automatic retries for this preflight.
            blocked.add(document.id)
            db.info.setdefault(DDT_CACHE_KEY, {}).pop(document.id, None)
            certificate_ai_cache.pop(document.id, None)
            if document.id in explicit_ids:
                document.stato_elaborazione = "errore"
                db.add(document)
            record_check(db, document, initial_type=initial, decision="da_verificare", checks=checks, actor_id=actor_id, reason=reason)
            failed.append({"file_name": document.nome_file_originale, "reason": reason})
    return accepted, failed


def blocked_row_ids(db):
    ids = db.info.get(BLOCKED_KEY, set())
    if not ids:
        return set()
    return {row_id for (row_id,) in db.query(AcquisitionRow.id).filter(or_(
        AcquisitionRow.document_ddt_id.in_(ids), AcquisitionRow.document_certificato_id.in_(ids),
    )).all()}
