from __future__ import annotations

import base64
import hashlib
import json
import re
import pytesseract
from pathlib import Path
from typing import cast
from uuid import uuid4
from datetime import UTC, datetime

import fitz
from fastapi import UploadFile
from fastapi import HTTPException, status
from openai import OpenAI
from PIL import Image, ImageDraw
from pypdf import PdfReader
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logs.service import log_service
from app.modules.acquisition.models import (
    AcquisitionHistoryEvent,
    AcquisitionRow,
    AcquisitionValueHistory,
    AutonomousProcessingRun,
    CertificateMatch,
    CertificateMatchCandidate,
    Document,
    DocumentEvidence,
    DocumentPage,
    ReadValue,
)
from app.modules.acquisition.schemas import (
    AcquisitionHistoryEventResponse,
    AutonomousRunResponse,
    AutonomousRunStartRequest,
    AcquisitionRowCreateRequest,
    AcquisitionRowDetailResponse,
    AcquisitionRowListItemResponse,
    AcquisitionValueHistoryResponse,
    DocumentSplitRowsCreateResponse,
    DocumentBatchErrorResponse,
    DocumentBatchUploadResponse,
    CurrentUploadBatchResponse,
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentEvidenceCreateRequest,
    DocumentEvidenceResponse,
    DocumentPageCreateRequest,
    DocumentPageResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    MatchCandidateRequest,
    MatchCandidateResponse,
    MatchUpsertRequest,
    MatchResponse,
    ReadValueResponse,
    ReadValueUpsertRequest,
)
from app.modules.document_reader.registry import resolve_supplier_template
from app.modules.document_reader.matching import (
    detect_ddt_core_matches as reader_detect_ddt_core_matches,
    detect_certificate_core_matches as reader_detect_certificate_core_matches,
    document_contains_token as reader_document_contains_token,
    extract_supplier_match_fields as reader_extract_supplier_match_fields,
    extract_row_supplier_match_fields as reader_extract_row_supplier_match_fields,
    merge_row_supplier_fields as reader_merge_row_supplier_fields,
    normalize_impol_packing_list_root,
    normalize_match_token as reader_normalize_match_token,
    score_supplier_field_matches as reader_score_supplier_field_matches,
    same_token as reader_same_token,
    weights_are_compatible as reader_weights_are_compatible,
)
from app.modules.document_reader.schemas import ReaderRowSplitCandidateResponse
from app.modules.document_reader.service import build_document_row_split_plan
from app.modules.document_reader.table_analysis import choose_measured_lines
from app.modules.suppliers.models import Supplier, SupplierAlias


def serialize_document_page(page: DocumentPage) -> DocumentPageResponse:
    return DocumentPageResponse(
        id=page.id,
        document_id=page.document_id,
        numero_pagina=page.numero_pagina,
        larghezza=page.larghezza,
        altezza=page.altezza,
        rotazione=page.rotazione,
        testo_estratto=page.testo_estratto,
        ocr_text=page.ocr_text,
        immagine_pagina_storage_key=page.immagine_pagina_storage_key,
        image_url=_document_page_image_url(page) if page.immagine_pagina_storage_key else None,
        stato_estrazione=page.stato_estrazione,
        hash_render=page.hash_render,
    )


def serialize_document(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        tipo_documento=document.tipo_documento,
        stato_upload=document.stato_upload,
        upload_batch_id=document.upload_batch_id,
        scadenza_batch=document.scadenza_batch,
        fornitore_id=document.fornitore_id,
        fornitore_nome=document.supplier.ragione_sociale if document.supplier is not None else None,
        nome_file_originale=document.nome_file_originale,
        storage_key=document.storage_key,
        file_url=_document_file_url(document),
        hash_file=document.hash_file,
        mime_type=document.mime_type,
        numero_pagine=document.numero_pagine,
        data_upload=document.data_upload,
        utente_upload_id=document.utente_upload_id,
        stato_elaborazione=document.stato_elaborazione,
        origine_upload=document.origine_upload,
        documento_padre_id=document.documento_padre_id,
    )


def serialize_document_detail(document: Document) -> DocumentDetailResponse:
    base = serialize_document(document)
    return DocumentDetailResponse(**base.model_dump(), pages=[serialize_document_page(page) for page in document.pages])


def serialize_document_summary(document: Document) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        id=document.id,
        tipo_documento=document.tipo_documento,
        nome_file_originale=document.nome_file_originale,
        storage_key=document.storage_key,
        file_url=_document_file_url(document),
    )


def serialize_evidence(evidence: DocumentEvidence) -> DocumentEvidenceResponse:
    return DocumentEvidenceResponse(
        id=evidence.id,
        document_id=evidence.document_id,
        document_page_id=evidence.document_page_id,
        acquisition_row_id=evidence.acquisition_row_id,
        blocco=evidence.blocco,
        tipo_evidenza=evidence.tipo_evidenza,
        bbox=evidence.bbox,
        testo_grezzo=evidence.testo_grezzo,
        storage_key_derivato=evidence.storage_key_derivato,
        metodo_estrazione=evidence.metodo_estrazione,
        mascherato=evidence.mascherato,
        confidenza=evidence.confidenza,
        data_creazione=evidence.data_creazione,
        utente_creazione_id=evidence.utente_creazione_id,
    )


def serialize_read_value(value: ReadValue) -> ReadValueResponse:
    return ReadValueResponse(
        id=value.id,
        acquisition_row_id=value.acquisition_row_id,
        blocco=value.blocco,
        campo=value.campo,
        valore_grezzo=value.valore_grezzo,
        valore_standardizzato=_normalize_value_for_field(value.blocco, value.campo, value.valore_standardizzato),
        valore_finale=_normalize_value_for_field(value.blocco, value.campo, value.valore_finale),
        stato=value.stato,
        document_evidence_id=value.document_evidence_id,
        metodo_lettura=value.metodo_lettura,
        fonte_documentale=value.fonte_documentale,
        confidenza=value.confidenza,
        utente_ultima_modifica_id=value.utente_ultima_modifica_id,
        timestamp_ultima_modifica=value.timestamp_ultima_modifica,
    )


def serialize_match_candidate(candidate: CertificateMatchCandidate) -> MatchCandidateResponse:
    return MatchCandidateResponse(
        id=candidate.id,
        match_certificato_id=candidate.match_certificato_id,
        document_certificato_id=candidate.document_certificato_id,
        rank=candidate.rank,
        motivo_breve=candidate.motivo_breve,
        fonte_proposta=candidate.fonte_proposta,
        stato=candidate.stato,
    )


def serialize_match(match: CertificateMatch) -> MatchResponse:
    return MatchResponse(
        id=match.id,
        acquisition_row_id=match.acquisition_row_id,
        document_certificato_id=match.document_certificato_id,
        stato=match.stato,
        motivo_breve=match.motivo_breve,
        fonte_proposta=match.fonte_proposta,
        utente_conferma_id=match.utente_conferma_id,
        timestamp=match.timestamp,
        candidates=[serialize_match_candidate(candidate) for candidate in match.candidates],
    )


def serialize_history_event(event: AcquisitionHistoryEvent) -> AcquisitionHistoryEventResponse:
    return AcquisitionHistoryEventResponse(
        id=event.id,
        acquisition_row_id=event.acquisition_row_id,
        blocco=event.blocco,
        azione=event.azione,
        utente_id=event.utente_id,
        timestamp=event.timestamp,
        nota_breve=event.nota_breve,
    )


def serialize_value_history(entry: AcquisitionValueHistory) -> AcquisitionValueHistoryResponse:
    return AcquisitionValueHistoryResponse(
        id=entry.id,
        acquisition_row_id=entry.acquisition_row_id,
        value_id=entry.value_id,
        blocco=entry.blocco,
        campo=entry.campo,
        valore_prima=entry.valore_prima,
        valore_dopo=entry.valore_dopo,
        utente_id=entry.utente_id,
        timestamp=entry.timestamp,
    )


def serialize_autonomous_run(run: AutonomousProcessingRun) -> AutonomousRunResponse:
    return AutonomousRunResponse(
        id=run.id,
        stato=run.stato,
        fase_corrente=run.fase_corrente,
        messaggio_corrente=run.messaggio_corrente,
        totale_documenti_ddt=run.totale_documenti_ddt,
        totale_documenti_certificato=run.totale_documenti_certificato,
        totale_righe_target=run.totale_righe_target,
        righe_create=run.righe_create,
        righe_processate=run.righe_processate,
        match_proposti=run.match_proposti,
        chimica_rilevata=run.chimica_rilevata,
        proprieta_rilevate=run.proprieta_rilevate,
        note_rilevate=run.note_rilevate,
        usa_ddt_vision=run.usa_ddt_vision,
        current_row_id=run.current_row_id,
        current_document_name=run.current_document_name,
        ultimo_errore=run.ultimo_errore,
        triggered_by_user_id=run.triggered_by_user_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        updated_at=run.updated_at,
    )


def serialize_acquisition_row_list_item(row: AcquisitionRow) -> AcquisitionRowListItemResponse:
    ddt_summary = _compute_ddt_field_summary(row)
    return AcquisitionRowListItemResponse(
        id=row.id,
        document_ddt_id=row.document_ddt_id,
        document_certificato_id=row.document_certificato_id,
        cdq=row.cdq,
        fornitore_id=row.fornitore_id,
        fornitore_nome=row.supplier.ragione_sociale if row.supplier is not None else None,
        fornitore_raw=row.fornitore_raw,
        lega_base=row.lega_base,
        lega_designazione=row.lega_designazione,
        variante_lega=row.variante_lega,
        diametro=_normalize_value_for_field("ddt", "diametro", row.diametro),
        colata=row.colata,
        ddt=row.ddt,
        peso=_normalize_value_for_field("ddt", "peso", row.peso),
        ordine=row.ordine,
        data_documento=row.data_documento,
        ddt_data_upload=row.ddt_document.data_upload if row.ddt_document is not None else None,
        note_documento=row.note_documento,
        stato_tecnico=row.stato_tecnico,
        stato_workflow=row.stato_workflow,
        priorita_operativa=row.priorita_operativa,
        validata_finale=row.validata_finale,
        block_states=_compute_block_states(row),
        match_state=row.certificate_match.stato if row.certificate_match is not None else ("proposto" if row.document_certificato_id is not None else "mancante"),
        certificate_file_name=row.certificate_document.nome_file_originale if row.certificate_document else None,
        ddt_confirmed_fields=ddt_summary["confirmed"],
        ddt_pending_fields=ddt_summary["pending"],
        ddt_missing_fields=ddt_summary["missing"],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_acquisition_row_detail(row: AcquisitionRow) -> AcquisitionRowDetailResponse:
    base = serialize_acquisition_row_list_item(row)
    return AcquisitionRowDetailResponse(
        **base.model_dump(),
        ddt_document=serialize_document_summary(row.ddt_document) if row.ddt_document is not None else None,
        certificate_document=serialize_document_summary(row.certificate_document) if row.certificate_document else None,
        evidences=[serialize_evidence(evidence) for evidence in row.evidences],
        values=[serialize_read_value(value) for value in row.values],
        certificate_match=serialize_match(row.certificate_match) if row.certificate_match else None,
        history_events=[serialize_history_event(event) for event in row.history_events],
        value_history=[serialize_value_history(entry) for entry in row.value_history],
    )


def list_documents(
    db: Session,
    tipo_documento: str | None = None,
    fornitore_id: int | None = None,
    upload_batch_id: str | None = None,
    actor_id: int | None = None,
) -> list[DocumentResponse]:
    query = db.query(Document).options(joinedload(Document.supplier)).order_by(Document.data_upload.desc(), Document.id.desc())
    if upload_batch_id is None:
        query = query.filter(Document.stato_upload == "persistente")
    else:
        query = query.filter((Document.stato_upload == "temporaneo") & (Document.upload_batch_id == upload_batch_id))
        if actor_id is not None:
            query = query.filter(Document.utente_upload_id == actor_id)
    if tipo_documento is not None:
        query = query.filter(Document.tipo_documento == tipo_documento)
    if fornitore_id is not None:
        query = query.filter(Document.fornitore_id == fornitore_id)
    return [serialize_document(document) for document in query.all()]


def get_current_upload_batch(db: Session, *, actor_id: int) -> CurrentUploadBatchResponse:
    upload_batch_id = _get_latest_temporary_upload_batch_id(db, actor_id=actor_id)
    if upload_batch_id is None:
        return CurrentUploadBatchResponse(upload_batch_id=None, items=[])
    items = list_documents(db, upload_batch_id=upload_batch_id, actor_id=actor_id)
    return CurrentUploadBatchResponse(upload_batch_id=upload_batch_id, items=items)


def discard_current_upload_batch(db: Session, *, actor_id: int) -> CurrentUploadBatchResponse:
    upload_batch_id = _get_latest_temporary_upload_batch_id(db, actor_id=actor_id)
    if upload_batch_id is None:
        return CurrentUploadBatchResponse(upload_batch_id=None, items=[])
    _delete_temporary_upload_batch(db, actor_id=actor_id, upload_batch_id=upload_batch_id)
    return CurrentUploadBatchResponse(upload_batch_id=None, items=[])


def get_document(db: Session, document_id: int) -> Document:
    document = (
        db.query(Document)
        .options(joinedload(Document.pages))
        .filter(Document.id == document_id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def get_document_page(db: Session, page_id: int) -> DocumentPage:
    page = db.get(DocumentPage, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document page not found")
    return page


def get_document_file_path(document: Document) -> Path:
    return _resolve_storage_path(document.storage_key)


def get_document_page_image_path(page: DocumentPage) -> Path:
    if not page.immagine_pagina_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document page image not available")
    return _resolve_storage_path(page.immagine_pagina_storage_key)


def create_document(db: Session, payload: DocumentCreateRequest, actor_id: int, actor_email: str) -> DocumentResponse:
    if payload.fornitore_id is not None:
        _get_supplier(db, payload.fornitore_id)
    if payload.documento_padre_id is not None:
        get_document(db, payload.documento_padre_id)

    existing = db.query(Document).filter(Document.storage_key == payload.storage_key).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document storage_key already exists")

    document = Document(
        tipo_documento=payload.tipo_documento,
        stato_upload=payload.stato_upload,
        upload_batch_id=payload.upload_batch_id,
        scadenza_batch=payload.scadenza_batch,
        fornitore_id=payload.fornitore_id,
        nome_file_originale=payload.nome_file_originale,
        storage_key=payload.storage_key,
        hash_file=payload.hash_file,
        mime_type=payload.mime_type,
        numero_pagine=payload.numero_pagine,
        utente_upload_id=actor_id,
        stato_elaborazione=payload.stato_elaborazione,
        origine_upload=payload.origine_upload,
        documento_padre_id=payload.documento_padre_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    log_service.record("acquisition", f"Document created: {document.nome_file_originale}", actor_email)
    return serialize_document(document)


def upload_document(
    db: Session,
    *,
    tipo_documento: str,
    uploaded_file: UploadFile,
    actor_id: int,
    actor_email: str,
    fornitore_id: int | None = None,
    documento_padre_id: int | None = None,
    origine_upload: str = "utente",
    upload_batch_id: str | None = None,
) -> DocumentResponse:
    if uploaded_file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a filename")
    if fornitore_id is not None:
        _get_supplier(db, fornitore_id)
    if documento_padre_id is not None:
        get_document(db, documento_padre_id)

    file_bytes = uploaded_file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    original_name = Path(uploaded_file.filename).name or f"{tipo_documento}.bin"
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    persistent_duplicate = _find_persistent_duplicate_document(db, file_hash=file_hash)
    if persistent_duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File duplicato: contenuto gia presente come documento persistente #{persistent_duplicate.id}",
        )

    temporary_duplicate = _find_temporary_duplicate_document_for_user(db, actor_id=actor_id, file_hash=file_hash)
    if temporary_duplicate is not None:
        if (temporary_duplicate.stato_elaborazione or "").lower() == "errore":
            _delete_temporary_documents_by_ids(db, actor_id=actor_id, document_ids=[temporary_duplicate.id])
        else:
            return serialize_document(temporary_duplicate)

    extension = Path(original_name).suffix.lower()
    now = datetime.now(UTC)
    resolved_upload_batch_id = _normalize_upload_batch_id(upload_batch_id) or _get_latest_temporary_upload_batch_id(db, actor_id=actor_id) or uuid4().hex
    relative_storage_key = f"{tipo_documento}/{now:%Y/%m/%d}/{uuid4().hex}{extension}"
    storage_path = _document_storage_root() / relative_storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(file_bytes)

    document = Document(
        tipo_documento=tipo_documento,
        stato_upload="temporaneo",
        upload_batch_id=resolved_upload_batch_id,
        scadenza_batch=None,
        fornitore_id=fornitore_id,
        nome_file_originale=original_name,
        storage_key=relative_storage_key.replace("\\", "/"),
        hash_file=file_hash,
        mime_type=uploaded_file.content_type,
        numero_pagine=None,
        utente_upload_id=actor_id,
        stato_elaborazione="caricato",
        origine_upload=origine_upload,
        documento_padre_id=documento_padre_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    if _is_pdf_document(document, uploaded_file.content_type):
        document = prepare_document_for_reader(db, document)
    document = _apply_document_identity_detection(db, document)
    log_service.record("acquisition", f"Document uploaded: {document.nome_file_originale}", actor_email)
    return serialize_document(document)


def upload_documents_batch(
    db: Session,
    *,
    tipo_documento: str,
    uploaded_files: list[UploadFile],
    actor_id: int,
    actor_email: str,
    fornitore_id: int | None = None,
    documento_padre_id: int | None = None,
    origine_upload: str = "utente",
    upload_batch_id: str | None = None,
) -> DocumentBatchUploadResponse:
    if not uploaded_files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided for batch upload")

    resolved_upload_batch_id = _normalize_upload_batch_id(upload_batch_id) or _get_latest_temporary_upload_batch_id(db, actor_id=actor_id) or uuid4().hex
    uploaded: list[DocumentResponse] = []
    failed: list[DocumentBatchErrorResponse] = []
    uploaded_ids: set[int] = set()

    for uploaded_file in uploaded_files:
        file_name = Path(uploaded_file.filename or "").name or f"{tipo_documento}.bin"
        try:
            uploaded_document = upload_document(
                db=db,
                tipo_documento=tipo_documento,
                uploaded_file=uploaded_file,
                actor_id=actor_id,
                actor_email=actor_email,
                fornitore_id=fornitore_id,
                documento_padre_id=documento_padre_id,
                origine_upload=origine_upload,
                upload_batch_id=resolved_upload_batch_id,
            )
            if uploaded_document.id in uploaded_ids:
                failed.append(
                    DocumentBatchErrorResponse(
                        file_name=file_name,
                        detail="File duplicato: gia presente nel batch temporaneo aperto",
                    )
                )
                continue
            uploaded_ids.add(uploaded_document.id)
            uploaded.append(uploaded_document)
        except HTTPException as exc:
            failed.append(DocumentBatchErrorResponse(file_name=file_name, detail=str(exc.detail)))
        except Exception as exc:  # pragma: no cover - defensive fallback
            failed.append(DocumentBatchErrorResponse(file_name=file_name, detail=str(exc)))

    return DocumentBatchUploadResponse(
        requested_count=len(uploaded_files),
        uploaded_count=len(uploaded),
        failed_count=len(failed),
        upload_batch_id=resolved_upload_batch_id,
        uploaded=uploaded,
        failed=failed,
    )


def _apply_document_identity_detection(db: Session, document: Document) -> Document:
    probable_type = _detect_document_type(document)
    probable_supplier_id = _detect_document_supplier_id(db, document)

    changed = False
    if probable_type and probable_type != document.tipo_documento:
        document.tipo_documento = probable_type
        changed = True

    if document.fornitore_id is None and probable_supplier_id is not None:
        document.fornitore_id = probable_supplier_id
        changed = True

    if changed:
        db.add(document)
        db.commit()
        return get_document(db, document.id)
    return document


def _detect_document_type(document: Document) -> str | None:
    search_text = _document_identity_text(document)
    if not search_text:
        return None

    file_name = document.nome_file_originale.lower()
    impol_type = _detect_impol_document_type(search_text, file_name)
    if impol_type is not None:
        return impol_type

    certificate_score = 0
    ddt_score = 0

    certificate_markers = {
        "inspection certificate": 5,
        "certificato di collaudo": 5,
        "abnahmepruefzeugnis": 5,
        "certificat de reception": 5,
        "en 10204": 4,
        "chemical composition": 4,
        "composizione chimica": 4,
        "mechanical properties": 4,
        "caratteristiche meccaniche": 4,
        "cert.no": 3,
        "cqf": 4,
        "cdq_": 4,
        "inspection": 2,
    }
    ddt_markers = {
        "documento di trasporto": 6,
        " ddt ": 5,
        "d.d.t": 5,
        "delivery note": 5,
        "packing list": 4,
        "document no": 2,
        "spedizione": 2,
        "destinatario": 2,
        "colli": 2,
        "peso netto": 1,
    }

    if re.fullmatch(r"\d[\d_-]{1,}\.pdf", file_name):
        ddt_score += 3
    if file_name.startswith("cqf_") or file_name.startswith("cdq_"):
        certificate_score += 5

    for marker, weight in certificate_markers.items():
        if marker in search_text:
            certificate_score += weight
    for marker, weight in ddt_markers.items():
        if marker in search_text:
            ddt_score += weight

    if _looks_like_impol_identity_text(search_text):
        if "packing list" in search_text:
            ddt_score += 8
        if any(marker in search_text for marker in ("inspection certificate", "en 10204", "chemical composition", "mechanical properties")):
            certificate_score += 8

    if certificate_score >= ddt_score + 3:
        return "certificato"
    if ddt_score >= certificate_score + 3:
        return "ddt"
    return None


def _detect_document_supplier_id(db: Session, document: Document) -> int | None:
    raw_identity_text = _document_identity_text(document)
    search_variants = _build_identity_search_variants(raw_identity_text)
    if not search_variants:
        return None

    looks_like_impol = any(_looks_like_impol_identity_text(search_text) for search_text in search_variants)

    suppliers = db.query(Supplier).options(joinedload(Supplier.aliases)).filter(Supplier.attivo.is_(True)).all()
    best_supplier_id = None
    best_score = 0
    second_score = 0

    for supplier in suppliers:
        aliases = [supplier.ragione_sociale] + [alias.nome_alias for alias in supplier.aliases if alias.attivo]
        if looks_like_impol and _is_impol_customer_composite_supplier(supplier.ragione_sociale, aliases):
            continue
        score = 0
        for alias in aliases:
            normalized_alias = _normalize_identity_text(alias)
            if not normalized_alias or len(normalized_alias) < 4:
                continue
            for search_text in search_variants:
                if normalized_alias in search_text:
                    score = max(score, min(80, 12 + len(normalized_alias)))
        if _supplier_aliases_look_like_impol(aliases):
            score = max(score, _score_impol_supplier_identity(search_variants))
        if score > best_score:
            second_score = best_score
            best_score = score
            best_supplier_id = supplier.id
        elif score > second_score:
            second_score = score

    if best_supplier_id is None:
        return None
    if best_score < 16:
        return None
    if second_score and best_score - second_score < 4:
        return None
    return best_supplier_id


def _document_identity_text(document: Document) -> str:
    chunks = [document.nome_file_originale]
    for page in document.pages[:2]:
        page_text = _best_page_text(page)
        if page_text:
            chunks.append(page_text[:4000])
            mojibake_normalized = _normalize_mojibake_numeric_text(page_text)
            if mojibake_normalized != page_text:
                chunks.append(mojibake_normalized[:4000])
    return "\n".join(chunk for chunk in chunks if chunk)


def _normalize_identity_text(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("_", " ").replace("-", " ").replace("/", " ")
    normalized = re.sub(r"[^a-z0-9àèéìòóùüöäßç.\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


def _build_identity_search_variants(value: str | None) -> list[str]:
    raw_text = _string_or_none(value)
    if raw_text is None:
        return []

    variants = [
        _normalize_identity_text(raw_text),
        _normalize_identity_text(_normalize_mojibake_numeric_text(raw_text)),
    ]
    deduped: list[str] = []
    for variant in variants:
        if variant.strip() and variant not in deduped:
            deduped.append(variant)
    return deduped


def _looks_like_impol_identity_text(search_text: str) -> bool:
    return any(
        marker in search_text
        for marker in (
            " impol d.o.o ",
            " impol d.o.0 ",
            " impol group ",
            " info@impol.si ",
            " www.impol.si ",
            " slovenska bistrica ",
        )
    )


def _detect_impol_document_type(search_text: str, file_name: str) -> str | None:
    if not _looks_like_impol_identity_text(search_text):
        return None

    if file_name.startswith("cqf_") or file_name.startswith("cdq_"):
        return "certificato"
    if re.fullmatch(r"\d{1,6}-\d{1,2}\.pdf", file_name):
        return "ddt"

    has_certificate_signals = any(
        marker in search_text
        for marker in (
            "inspection certificate",
            "en 10204",
            "chemical composition",
            "mechanical properties",
            "customer order no",
            "packing list no.",
            "issue date",
        )
    )
    has_ddt_signals = any(
        marker in search_text
        for marker in (
            "packing list",
            "receiver",
            "delivery terms",
            "truck / container",
            "your order no",
            "product description",
            "order date",
        )
    )

    if has_certificate_signals and not has_ddt_signals:
        return "certificato"
    if has_ddt_signals and not has_certificate_signals:
        return "ddt"
    if has_certificate_signals and "inspection certificate" in search_text:
        return "certificato"
    if has_ddt_signals and "packing list" in search_text:
        return "ddt"
    return None


def _supplier_aliases_look_like_impol(aliases: list[str]) -> bool:
    return any("impol" in (alias or "").casefold() for alias in aliases)


def _is_impol_customer_composite_supplier(supplier_name: str | None, aliases: list[str]) -> bool:
    candidates = [supplier_name or "", *aliases]
    normalized = " | ".join((candidate or "").casefold() for candidate in candidates)
    return "ralcom" in normalized and "impol" in normalized and "impol d.o.o" not in normalized


def _score_impol_supplier_identity(search_variants: list[str]) -> int:
    best_score = 0
    for search_text in search_variants:
        if not _looks_like_impol_identity_text(search_text):
            continue
        score = 20
        if "packing list" in search_text:
            score += 12
        if "inspection certificate" in search_text:
            score += 12
        if "customer order no" in search_text or "supplier order no" in search_text:
            score += 8
        if "receiver" in search_text or "delivery terms" in search_text:
            score += 8
        best_score = max(best_score, score)
    return best_score


def _find_supplier_from_text(db: Session, raw_text: str | None) -> Supplier | None:
    normalized_text = _normalize_identity_text(_string_or_none(raw_text) or "")
    if not normalized_text.strip():
        return None

    suppliers = db.query(Supplier).options(joinedload(Supplier.aliases)).filter(Supplier.attivo.is_(True)).all()
    best_supplier: Supplier | None = None
    best_score = 0
    second_score = 0

    for supplier in suppliers:
        aliases = [supplier.ragione_sociale] + [alias.nome_alias for alias in supplier.aliases if alias.attivo]
        score = 0
        for alias in aliases:
            normalized_alias = _normalize_identity_text(alias)
            if not normalized_alias or len(normalized_alias) < 4:
                continue
            if normalized_alias == normalized_text:
                score = max(score, 100)
            elif normalized_alias in normalized_text or normalized_text in normalized_alias:
                score = max(score, min(80, 12 + len(normalized_alias)))
        if score > best_score:
            second_score = best_score
            best_score = score
            best_supplier = supplier
        elif score > second_score:
            second_score = score

    if best_supplier is None:
        return None
    if best_score < 16:
        return None
    if second_score and best_score - second_score < 4:
        return None
    return best_supplier


def _ensure_row_supplier_link(db: Session, row: AcquisitionRow) -> None:
    if row.supplier is not None and row.fornitore_id is not None:
        return

    resolved_supplier = None
    if row.ddt_document is not None and row.ddt_document.supplier is not None:
        resolved_supplier = row.ddt_document.supplier
    elif row.certificate_document is not None and row.certificate_document.supplier is not None:
        resolved_supplier = row.certificate_document.supplier
    elif row.fornitore_raw:
        resolved_supplier = _find_supplier_from_text(db, row.fornitore_raw)

    if resolved_supplier is None:
        return

    row.fornitore_id = resolved_supplier.id
    row.supplier = resolved_supplier


def index_document(db: Session, document: Document, actor_email: str | None = None) -> DocumentDetailResponse:
    document = _index_document_from_path(db, document)
    log_service.record("acquisition", f"Document indexed: {document.nome_file_originale}", actor_email)
    return serialize_document_detail(document)


def prepare_document_for_reader(db: Session, document: Document) -> Document:
    if not document.pages:
        document = _index_document_from_path(db, document)

    document = _ensure_document_page_images(db, document)
    document = _ensure_document_page_ocr(db, document)
    return get_document(db, document.id)


def create_rows_from_document_split_plan(
    db: Session,
    *,
    document: Document,
    actor_id: int,
    actor_email: str,
) -> DocumentSplitRowsCreateResponse:
    document = prepare_document_for_reader(db, document)

    plan = build_document_row_split_plan(document)
    if not plan.row_split_candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No split candidates available for this document",
        )

    template = resolve_supplier_template(
        document.supplier.ragione_sociale if document.supplier is not None else None,
        document.nome_file_originale,
    )
    supplier_key = template.supplier_key if template is not None else None
    shared_matches = reader_detect_ddt_core_matches(document.pages, supplier_key=supplier_key)
    existing_rows = (
        db.query(AcquisitionRow)
        .filter(
            AcquisitionRow.fornitore_id == document.fornitore_id,
        )
        .order_by(AcquisitionRow.id.asc())
        .all()
    )
    existing_signatures = {
        _split_candidate_signature_from_row(row): row
        for row in existing_rows
        if row.document_ddt_id is not None
    }

    created_rows: list[AcquisitionRowDetailResponse] = []
    for candidate in plan.row_split_candidates:
        candidate_signature = _split_candidate_signature_from_candidate(
            document=document,
            candidate=candidate,
            fallback_ddt=_split_plan_match_value(shared_matches, "ddt"),
        )
        existing_row = existing_signatures.get(candidate_signature)
        if existing_row is not None:
            continue
        certificate_first_row = _find_existing_certificate_first_row_for_split_candidate(
            rows=existing_rows,
            document=document,
            candidate=candidate,
            fallback_ddt=_split_plan_match_value(shared_matches, "ddt"),
            supplier_key=supplier_key,
        )
        if certificate_first_row is not None:
            certificate_first_row.document_ddt_id = document.id
            certificate_first_row.fornitore_id = document.fornitore_id
            certificate_first_row.fornitore_raw = document.supplier.ragione_sociale if document.supplier is not None else None
            certificate_first_row.ddt = candidate.ddt_number or _split_plan_match_value(shared_matches, "ddt")
            certificate_first_row.ordine = candidate.customer_order_no
            certificate_first_row.lega_base = candidate.lega or certificate_first_row.lega_base
            certificate_first_row.diametro = candidate.diametro or certificate_first_row.diametro or _split_plan_match_value(shared_matches, "diametro")
            certificate_first_row.colata = candidate.colata or certificate_first_row.colata or _split_plan_match_value(shared_matches, "colata")
            certificate_first_row.peso = candidate.peso_netto or certificate_first_row.peso or _split_plan_match_value(shared_matches, "peso")
            if candidate.cdq:
                certificate_first_row.cdq = candidate.cdq
            db.add(certificate_first_row)
            db.commit()
            db.refresh(certificate_first_row)
            _persist_split_candidate_values(db=db, row=certificate_first_row, candidate=candidate, actor_id=actor_id)
            existing_signatures[candidate_signature] = certificate_first_row
            created_rows.append(serialize_acquisition_row_detail(get_acquisition_row(db, certificate_first_row.id)))
            continue
        created_row = create_acquisition_row(
            db=db,
            payload=AcquisitionRowCreateRequest(
                document_ddt_id=document.id,
                fornitore_id=document.fornitore_id,
                fornitore_raw=document.supplier.ragione_sociale if document.supplier is not None else None,
                cdq=candidate.cdq or _split_plan_match_value(shared_matches, "cdq"),
                lega_base=candidate.lega,
                diametro=candidate.diametro or _split_plan_match_value(shared_matches, "diametro"),
                colata=candidate.colata or _split_plan_match_value(shared_matches, "colata"),
                ddt=candidate.ddt_number or _split_plan_match_value(shared_matches, "ddt"),
                peso=candidate.peso_netto or _split_plan_match_value(shared_matches, "peso"),
                ordine=candidate.customer_order_no,
                stato_tecnico="rosso",
                stato_workflow="nuova",
                priorita_operativa="media",
            ),
            actor_id=actor_id,
            actor_email=actor_email,
        )
        row = get_acquisition_row(db, created_row.id)
        _persist_split_candidate_values(db=db, row=row, candidate=candidate, actor_id=actor_id)
        existing_signatures[candidate_signature] = row
        created_rows.append(serialize_acquisition_row_detail(get_acquisition_row(db, row.id)))

    log_service.record(
        "acquisition",
        f"Split rows created from document {document.id}: {len(created_rows)}",
        actor_email,
    )
    return DocumentSplitRowsCreateResponse(
        document_id=document.id,
        created_count=len(created_rows),
        created_rows=created_rows,
    )


def _split_plan_match_value(matches: dict[str, dict[str, object]], field_name: str) -> str | None:
    field_match = matches.get(field_name) or {}
    final_value = field_match.get("final")
    if not isinstance(final_value, str):
        return None
    return _string_or_none(final_value)


def _normalize_row_signature_token(value: str | None) -> str:
    normalized = _string_or_none(value)
    if normalized is None:
        return ""
    return reader_normalize_match_token(normalized) or normalized.upper().strip()


def _split_candidate_signature_from_row(row: AcquisitionRow) -> tuple[str, str, str, str, str, str, str]:
    return (
        str(row.fornitore_id or ""),
        _normalize_row_signature_token(row.ddt),
        _normalize_row_signature_token(row.ordine),
        _normalize_row_signature_token(row.lega_base),
        _normalize_row_signature_token(row.diametro),
        _normalize_row_signature_token(row.colata),
        _normalize_row_signature_token(row.peso),
    )


def _split_candidate_signature_from_candidate(
    *,
    document: Document,
    candidate,
    fallback_ddt: str | None,
) -> tuple[str, str, str, str, str, str, str]:
    return (
        str(document.fornitore_id or ""),
        _normalize_row_signature_token(candidate.ddt_number or fallback_ddt),
        _normalize_row_signature_token(candidate.customer_order_no),
        _normalize_row_signature_token(candidate.lega),
        _normalize_row_signature_token(candidate.diametro),
        _normalize_row_signature_token(candidate.colata),
        _normalize_row_signature_token(candidate.peso_netto),
    )


def _persist_split_candidate_values(
    db: Session,
    *,
    row: AcquisitionRow,
    candidate,
    actor_id: int,
) -> None:
    candidate_values = {
        "cdq": candidate.cdq,
        "customer_code": candidate.customer_code,
        "article_code": candidate.article_code,
        "customer_order_no": candidate.customer_order_no,
        "lot_batch_no": candidate.lot_batch_no,
        "heat_no": candidate.heat_no,
        "supplier_order_no": candidate.supplier_order_no,
        "product_code": candidate.product_code,
    }
    for field_name, field_value in candidate_values.items():
        normalized_value = _string_or_none(field_value)
        if normalized_value is None:
            continue
        upsert_read_value(
            db=db,
            row=row,
            payload=ReadValueUpsertRequest(
                blocco="ddt",
                campo=field_name,
                valore_grezzo=normalized_value,
                valore_standardizzato=normalized_value,
                valore_finale=normalized_value,
                stato="proposto",
                metodo_lettura="sistema",
                fonte_documentale="ddt",
                confidenza=0.78,
            ),
            actor_id=actor_id,
        )


def _find_existing_certificate_first_row_for_split_candidate(
    db: Session,
    *,
    rows: list[AcquisitionRow],
    document: Document,
    candidate,
    fallback_ddt: str | None,
    supplier_key: str | None,
) -> AcquisitionRow | None:
    if supplier_key == "impol":
        candidate_packing_list = normalize_impol_packing_list_root(candidate.ddt_number or fallback_ddt)
        normalized_customer_order = _normalize_row_signature_token(candidate.customer_order_no)
        normalized_supplier_order = _normalize_row_signature_token(candidate.supplier_order_no)
        normalized_product_code = _normalize_row_signature_token(candidate.product_code)
        normalized_lega = _normalize_row_signature_token(candidate.lega)
        normalized_diameter = _normalize_row_signature_token(candidate.diametro)
        normalized_colata = _normalize_row_signature_token(candidate.colata)
        normalized_peso = _normalize_row_signature_token(candidate.peso_netto)

        best_row: AcquisitionRow | None = None
        best_score = 0
        for row in rows:
            if row.document_ddt_id is not None:
                continue
            if row.fornitore_id != document.fornitore_id:
                continue
            if row.document_certificato_id is None:
                continue

            certificate_document = row.certificate_document or get_document(db, row.document_certificato_id)
            if not certificate_document.pages:
                certificate_document = _index_document_from_path(db, certificate_document)
            supplier_fields = reader_extract_supplier_match_fields(
                certificate_document.pages,
                "impol",
                "certificato",
            )

            score = 0
            row_packing = _normalize_row_signature_token(supplier_fields.get("packing_list_no"))
            if candidate_packing_list:
                if row_packing and row_packing != _normalize_row_signature_token(candidate_packing_list):
                    continue
                if row_packing == _normalize_row_signature_token(candidate_packing_list):
                    score += 120
            row_customer_order = _normalize_row_signature_token(_certificate_first_row_identity_fields(row).get("customer_order"))
            if normalized_customer_order:
                if row_customer_order and row_customer_order != normalized_customer_order:
                    continue
                if row_customer_order == normalized_customer_order:
                    score += 100
            row_supplier_order = _normalize_row_signature_token(supplier_fields.get("supplier_order_no"))
            if normalized_supplier_order:
                if row_supplier_order and row_supplier_order != normalized_supplier_order:
                    continue
                if row_supplier_order == normalized_supplier_order:
                    score += 95
            row_product_code = _normalize_row_signature_token(supplier_fields.get("product_code"))
            if normalized_product_code:
                if row_product_code and row_product_code != normalized_product_code:
                    continue
                if row_product_code == normalized_product_code:
                    score += 100
            row_alloy = _normalize_row_signature_token(row.lega_base)
            if normalized_lega and row_alloy and row_alloy == normalized_lega:
                score += 40
            row_diameter = _normalize_row_signature_token(row.diametro)
            if normalized_diameter and row_diameter and row_diameter == normalized_diameter:
                score += 40
            row_cast = _normalize_row_signature_token(row.colata)
            if normalized_colata and row_cast and row_cast == normalized_colata:
                score += 110
            row_weight = _normalize_row_signature_token(row.peso)
            if normalized_peso and row_weight and reader_weights_are_compatible(row.peso, candidate.peso_netto):
                score += 20

            if score > best_score:
                best_score = score
                best_row = row

        if best_score >= 180:
            return best_row
        return None

    if supplier_key != "aluminium_bozen":
        return None

    normalized_cdq = _normalize_row_signature_token(candidate.cdq)
    if not normalized_cdq:
        return None

    normalized_lega = _normalize_row_signature_token(candidate.lega)
    normalized_diameter = _normalize_row_signature_token(candidate.diametro)
    normalized_colata = _normalize_row_signature_token(candidate.colata)
    normalized_peso = _normalize_row_signature_token(candidate.peso_netto)
    normalized_customer_order = _normalize_row_signature_token(candidate.customer_order_no)

    for row in rows:
        if row.document_ddt_id is not None:
            continue
        if row.fornitore_id != document.fornitore_id:
            continue
        if _normalize_row_signature_token(row.cdq) != normalized_cdq:
            continue
        if normalized_lega and _normalize_row_signature_token(row.lega_base) and _normalize_row_signature_token(row.lega_base) != normalized_lega:
            continue
        if normalized_diameter and _normalize_row_signature_token(row.diametro) and _normalize_row_signature_token(row.diametro) != normalized_diameter:
            continue
        if normalized_colata and _normalize_row_signature_token(row.colata) and _normalize_row_signature_token(row.colata) != normalized_colata:
            continue
        if normalized_peso and _normalize_row_signature_token(row.peso) and _normalize_row_signature_token(row.peso) != normalized_peso:
            continue
        row_identity_fields = _certificate_first_row_identity_fields(row)
        row_customer_order = _normalize_row_signature_token(row_identity_fields.get("customer_order"))
        if normalized_customer_order and row_customer_order and row_customer_order != normalized_customer_order:
            continue
        return row

    return None


def create_document_page(db: Session, document: Document, payload: DocumentPageCreateRequest) -> DocumentPageResponse:
    existing = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document.id, DocumentPage.numero_pagina == payload.numero_pagina)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document page already exists")

    page = DocumentPage(document_id=document.id, **payload.model_dump())
    db.add(page)
    db.commit()
    db.refresh(page)
    return serialize_document_page(page)


def get_autonomous_run(db: Session, run_id: int) -> AutonomousProcessingRun:
    run = db.get(AutonomousProcessingRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation run not found")
    return run


def get_active_autonomous_run(db: Session, *, actor_id: int) -> AutonomousProcessingRun | None:
    return (
        db.query(AutonomousProcessingRun)
        .filter(
            AutonomousProcessingRun.triggered_by_user_id == actor_id,
            AutonomousProcessingRun.stato.in_(("in_coda", "in_esecuzione")),
        )
        .order_by(AutonomousProcessingRun.created_at.desc(), AutonomousProcessingRun.id.desc())
        .first()
    )


def start_autonomous_run(
    db: Session,
    *,
    payload: AutonomousRunStartRequest,
    actor_id: int,
) -> AutonomousRunResponse:
    ddt_document_ids = _normalize_document_id_list(payload.ddt_document_ids)
    certificate_document_ids = _normalize_document_id_list(payload.certificate_document_ids)
    if not ddt_document_ids and not certificate_document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one DDT or certificate document")

    _ensure_documents_type(db, ddt_document_ids, "ddt")
    _ensure_documents_type(db, certificate_document_ids, "certificato")

    active_run = get_active_autonomous_run(db, actor_id=actor_id)
    if active_run is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is already an autonomous processing run in progress",
        )

    _set_documents_processing_state(
        db,
        [*ddt_document_ids, *certificate_document_ids],
        stato_elaborazione="in_lavorazione",
    )

    run = AutonomousProcessingRun(
        stato="in_coda",
        fase_corrente="in_attesa",
        messaggio_corrente="In attesa di avvio della presa in carico automatica",
        totale_documenti_ddt=len(ddt_document_ids),
        totale_documenti_certificato=len(certificate_document_ids),
        totale_righe_target=len(ddt_document_ids) + len(certificate_document_ids),
        usa_ddt_vision=payload.usa_ddt_vision,
        triggered_by_user_id=actor_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return serialize_autonomous_run(run)


def run_autonomous_processing(
    *,
    run_id: int,
    ddt_document_ids: list[int],
    certificate_document_ids: list[int],
    actor_id: int,
    actor_email: str,
    openai_api_key: str | None,
    use_ddt_vision: bool,
    use_ai_intervention: bool,
) -> None:
    db = SessionLocal()
    try:
        run = get_autonomous_run(db, run_id)
        _save_run(
            db,
            run,
            stato="in_esecuzione",
            fase_corrente="preparazione",
            messaggio_corrente="Preparazione dei documenti caricati",
            started_at=datetime.now(UTC),
            ultimo_errore=None,
        )

        ddt_documents = [_get_document_of_type(db, document_id, "ddt") for document_id in ddt_document_ids]
        certificate_documents = _resolve_certificate_documents_for_automation(
            db,
            ddt_documents=ddt_documents,
            explicit_certificate_document_ids=certificate_document_ids,
        )
        explicit_certificate_documents = [
            document for document in certificate_documents if document.id in set(certificate_document_ids)
        ]
        certificate_ai_cache: dict[int, dict[str, object]] = {}
        if use_ai_intervention and openai_api_key:
            for certificate_document in certificate_documents:
                template = resolve_supplier_template(
                    certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
                    certificate_document.nome_file_originale,
                )
                if template is None or not _supplier_supports_ai_vision_pipeline(template.supplier_key):
                    continue
                try:
                    _get_supplier_certificate_ai_payload(
                        db=db,
                        supplier_key=template.supplier_key,
                        certificate_document=certificate_document,
                        openai_api_key=openai_api_key,
                        certificate_ai_cache=certificate_ai_cache,
                    )
                except HTTPException as exc:
                    _save_run(
                        db,
                        run,
                        ultimo_errore=str(exc.detail),
                        messaggio_corrente=(
                            f"Lettura AI certificato non riuscita su {certificate_document.nome_file_originale}, continuo"
                        ),
                    )
        total_target_rows = 0
        for ddt_document in ddt_documents:
            plan = build_document_row_split_plan(prepare_document_for_reader(db, ddt_document))
            candidate_count = len(plan.row_split_candidates)
            total_target_rows += candidate_count if candidate_count else 1
        total_target_rows += len(explicit_certificate_documents)
        _save_run(db, run, totale_documenti_certificato=len(certificate_documents), totale_righe_target=total_target_rows)

        for index, ddt_document in enumerate(ddt_documents, start=1):
            _save_run(
                db,
                run,
                fase_corrente="riga_ddt",
                current_document_name=ddt_document.nome_file_originale,
                messaggio_corrente=f"Creo o recupero le righe {index}/{len(ddt_document_ids)} da {ddt_document.nome_file_originale}",
            )

            ddt_template = resolve_supplier_template(
                ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None,
                ddt_document.nome_file_originale,
            )
            ddt_supplier_key = ddt_template.supplier_key if ddt_template is not None else None
            if use_ai_intervention and openai_api_key and _supplier_supports_ai_vision_pipeline(ddt_supplier_key):
                _save_run(
                    db,
                    run,
                    fase_corrente="intervento_ai",
                    messaggio_corrente=f"Creo le righe DDT con AI per {ddt_document.nome_file_originale}",
                )
                try:
                    rows, created_count = _ensure_autonomous_rows_with_ai(
                        db=db,
                        ddt_document=ddt_document,
                        actor_id=actor_id,
                        actor_email=actor_email,
                        openai_api_key=openai_api_key,
                    )
                    if created_count:
                        _save_run(db, run, righe_create=run.righe_create + created_count)
                except HTTPException as exc:
                    _save_run(
                        db,
                        run,
                        ultimo_errore=str(exc.detail),
                        messaggio_corrente=(
                            f"Intervento AI DDT non riuscito su {ddt_document.nome_file_originale}"
                        ),
                    )
                    rows = []
            else:
                rows, created_count = _ensure_autonomous_rows(
                    db=db,
                    ddt_document=ddt_document,
                    actor_id=actor_id,
                    actor_email=actor_email,
                )
                if created_count:
                    _save_run(db, run, righe_create=run.righe_create + created_count)

            for row in rows:
                row = get_acquisition_row(db, row.id)
                _save_run(db, run, current_row_id=row.id)

                try:
                    if not (use_ai_intervention and _supplier_supports_ai_vision_pipeline(ddt_supplier_key)):
                        _save_run(
                            db,
                            run,
                            fase_corrente="lettura_ddt",
                            messaggio_corrente=f"Leggo i campi DDT della riga #{row.id}",
                        )
                        extract_core_fields(db=db, row=row, actor_id=actor_id)
                        row = get_acquisition_row(db, row.id)

                    if use_ddt_vision and (not use_ai_intervention) and openai_api_key and _row_needs_ddt_vision(db, row):
                        _save_run(
                            db,
                            run,
                            fase_corrente="vision_ddt",
                            messaggio_corrente=f"Uso Vision DDT sulla riga #{row.id}",
                        )
                        try:
                            extract_ddt_fields_with_vision(
                                db=db,
                                row=row,
                                actor_id=actor_id,
                                openai_api_key=openai_api_key,
                            )
                            row = get_acquisition_row(db, row.id)
                        except HTTPException as exc:
                            _save_run(
                                db,
                                run,
                                ultimo_errore=str(exc.detail),
                                messaggio_corrente=f"Vision DDT non riuscita su riga #{row.id}, continuo con il resto",
                            )

                    _save_run(
                        db,
                        run,
                        fase_corrente="match_certificato",
                        messaggio_corrente=f"Cerco il certificato piu coerente per la riga #{row.id}",
                    )
                    matched = _auto_propose_certificate_match(
                        db=db,
                        row=row,
                        certificate_documents=certificate_documents,
                        actor_id=actor_id,
                        openai_api_key=openai_api_key if use_ai_intervention else None,
                        certificate_ai_cache=certificate_ai_cache,
                        ai_only_mode=bool(use_ai_intervention and _supplier_supports_ai_vision_pipeline(ddt_supplier_key)),
                    )
                    if matched:
                        _save_run(db, run, match_proposti=run.match_proposti + 1)
                        row = get_acquisition_row(db, row.id)

                    if row.document_certificato_id is not None:
                        if not _block_has_confirmed_values(db, row.id, "chimica"):
                            _save_run(
                                db,
                                run,
                                fase_corrente="chimica",
                                messaggio_corrente=f"Leggo la chimica del certificato per la riga #{row.id}",
                            )
                        if not _block_has_confirmed_values(db, row.id, "proprieta"):
                            _save_run(
                                db,
                                run,
                                fase_corrente="proprieta",
                                messaggio_corrente=f"Leggo le proprieta del certificato per la riga #{row.id}",
                            )
                        if not _block_has_confirmed_values(db, row.id, "note"):
                            _save_run(
                                db,
                                run,
                                fase_corrente="note",
                                messaggio_corrente=f"Leggo le note standard del certificato per la riga #{row.id}",
                            )

                        had_chemistry = _block_has_values(db, row.id, "chimica")
                        had_properties = _block_has_values(db, row.id, "proprieta")
                        had_notes = _block_has_values(db, row.id, "note")
                        row = _process_certificate_side_blocks(
                            db=db,
                            row=row,
                            actor_id=actor_id,
                            openai_api_key=openai_api_key,
                            use_ai_intervention=use_ai_intervention,
                            certificate_ai_cache=certificate_ai_cache,
                        )
                        if not had_chemistry and _block_has_values(db, row.id, "chimica"):
                            _save_run(db, run, chimica_rilevata=run.chimica_rilevata + 1)
                        if not had_properties and _block_has_values(db, row.id, "proprieta"):
                            _save_run(db, run, proprieta_rilevate=run.proprieta_rilevate + 1)
                        if not had_notes and _block_has_values(db, row.id, "note"):
                            _save_run(db, run, note_rilevate=run.note_rilevate + 1)
                except Exception as exc:  # pragma: no cover - defensive safeguard for batch loop
                    db.rollback()
                    _save_run(
                        db,
                        run,
                        ultimo_errore=str(exc),
                        messaggio_corrente=f"Errore sulla riga #{row.id}: continuo con il resto",
                    )
                finally:
                    _save_run(
                        db,
                        run,
                        righe_processate=run.righe_processate + 1,
                        current_row_id=row.id,
                    )

        if explicit_certificate_documents:
            _save_run(
                db,
                run,
                fase_corrente="certificate_first",
                messaggio_corrente="Creo righe certificate-first per i certificati non matchati",
            )
            created_certificate_rows = _ensure_certificate_first_rows(
                db=db,
                certificate_documents=explicit_certificate_documents,
                actor_id=actor_id,
                actor_email=actor_email,
                openai_api_key=openai_api_key,
                use_ai_intervention=use_ai_intervention,
                certificate_ai_cache=certificate_ai_cache,
            )
            if created_certificate_rows:
                _save_run(
                    db,
                    run,
                    righe_create=run.righe_create + created_certificate_rows,
                    righe_processate=run.righe_processate + created_certificate_rows,
                )

        _save_run(
            db,
            run,
            stato="completato",
            fase_corrente="completato",
            messaggio_corrente="Compilazione automatica completata. Ora puo intervenire quality.",
            totale_righe_target=max(run.righe_processate, run.righe_create),
            current_row_id=None,
            finished_at=datetime.now(UTC),
        )
        _set_documents_processing_state(
            db,
            [*ddt_document_ids, *certificate_document_ids],
            stato_elaborazione="indicizzato",
        )
        _promote_documents_to_persistent(db, [*ddt_document_ids, *certificate_document_ids])
        log_service.record("acquisition", f"Autonomous processing completed: run {run.id}", actor_email)
    except Exception as exc:  # pragma: no cover - defensive safeguard for background task
        db.rollback()
        run = db.get(AutonomousProcessingRun, run_id)
        _set_documents_processing_state(
            db,
            [*ddt_document_ids, *certificate_document_ids],
            stato_elaborazione="errore",
        )
        if run is not None:
            _save_run(
                db,
                run,
                stato="errore",
                fase_corrente="errore",
                messaggio_corrente="La presa in carico automatica si e interrotta",
                ultimo_errore=str(exc),
                finished_at=datetime.now(UTC),
            )
        log_service.record("acquisition", f"Autonomous processing failed: run {run_id}", actor_email)
    finally:
        db.close()


def list_acquisition_rows(
    db: Session,
    stato_tecnico: str | None = None,
    stato_workflow: str | None = None,
    priorita_operativa: str | None = None,
    fornitore_id: int | None = None,
    has_certificate: bool | None = None,
) -> list[AcquisitionRowListItemResponse]:
    query = (
        db.query(AcquisitionRow)
        .options(
            selectinload(AcquisitionRow.values),
            joinedload(AcquisitionRow.supplier),
            joinedload(AcquisitionRow.ddt_document).joinedload(Document.supplier),
            joinedload(AcquisitionRow.certificate_match),
            joinedload(AcquisitionRow.certificate_document).joinedload(Document.supplier),
        )
        .order_by(AcquisitionRow.updated_at.desc(), AcquisitionRow.id.desc())
    )
    if stato_tecnico is not None:
        query = query.filter(AcquisitionRow.stato_tecnico == stato_tecnico)
    if stato_workflow is not None:
        query = query.filter(AcquisitionRow.stato_workflow == stato_workflow)
    if priorita_operativa is not None:
        query = query.filter(AcquisitionRow.priorita_operativa == priorita_operativa)
    if fornitore_id is not None:
        query = query.filter(AcquisitionRow.fornitore_id == fornitore_id)
    if has_certificate is True:
        query = query.filter(AcquisitionRow.document_certificato_id.is_not(None))
    if has_certificate is False:
        query = query.filter(AcquisitionRow.document_certificato_id.is_(None))
    rows = query.all()
    for row in rows:
        _ensure_row_supplier_link(db, row)
    return [serialize_acquisition_row_list_item(row) for row in rows]


def get_acquisition_row(db: Session, row_id: int) -> AcquisitionRow:
    row = (
        db.query(AcquisitionRow)
        .options(
            joinedload(AcquisitionRow.supplier),
            joinedload(AcquisitionRow.ddt_document).joinedload(Document.supplier),
            joinedload(AcquisitionRow.certificate_document).joinedload(Document.supplier),
            selectinload(AcquisitionRow.evidences),
            selectinload(AcquisitionRow.values),
            selectinload(AcquisitionRow.certificate_match).selectinload(CertificateMatch.candidates),
            selectinload(AcquisitionRow.history_events),
            selectinload(AcquisitionRow.value_history),
        )
        .filter(AcquisitionRow.id == row_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition row not found")
    _ensure_row_supplier_link(db, row)
    return row


def create_acquisition_row(
    db: Session,
    payload: AcquisitionRowCreateRequest,
    actor_id: int,
    actor_email: str,
) -> AcquisitionRowDetailResponse:
    ddt_document = _get_document_of_type(db, payload.document_ddt_id, "ddt") if payload.document_ddt_id is not None else None
    certificate_document = None
    if payload.document_certificato_id is not None:
        certificate_document = _get_document_of_type(db, payload.document_certificato_id, "certificato")

    supplier_id = _resolve_supplier_id(
        db=db,
        explicit_supplier_id=payload.fornitore_id,
        ddt_document=ddt_document,
        certificate_document=certificate_document,
    )

    row = AcquisitionRow(
        document_ddt_id=ddt_document.id if ddt_document is not None else None,
        document_certificato_id=certificate_document.id if certificate_document else None,
        cdq=payload.cdq,
        fornitore_id=supplier_id,
        fornitore_raw=payload.fornitore_raw,
        lega_base=payload.lega_base,
        lega_designazione=payload.lega_designazione,
        variante_lega=payload.variante_lega,
        diametro=payload.diametro,
        colata=payload.colata,
        ddt=payload.ddt,
        peso=payload.peso,
        ordine=payload.ordine,
        data_documento=payload.data_documento,
        note_documento=payload.note_documento,
        stato_tecnico=payload.stato_tecnico,
        stato_workflow=payload.stato_workflow,
        priorita_operativa=payload.priorita_operativa,
        validata_finale=payload.validata_finale,
    )
    db.add(row)
    db.flush()
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="riga_creata",
        user_id=actor_id,
        nota_breve=(
            f"DDT document {ddt_document.id}"
            if ddt_document is not None
            else f"Certificato document {certificate_document.id}" if certificate_document is not None else "Riga creata"
        ),
    )
    _sync_row_statuses(db, row)
    db.commit()
    created_row = get_acquisition_row(db, row.id)
    log_service.record("acquisition", f"Acquisition row created: {created_row.id}", actor_email)
    return serialize_acquisition_row_detail(created_row)


def update_acquisition_row(
    db: Session,
    row: AcquisitionRow,
    payload: AcquisitionRowUpdateRequest,
    actor_id: int,
    actor_email: str,
) -> AcquisitionRowDetailResponse:
    updates = payload.model_dump(exclude_unset=True)
    if "document_certificato_id" in updates and updates["document_certificato_id"] is not None:
        certificate_document = _get_document_of_type(db, updates["document_certificato_id"], "certificato")
        updates["document_certificato_id"] = certificate_document.id
    if "fornitore_id" in updates and updates["fornitore_id"] is not None:
        _get_supplier(db, updates["fornitore_id"])

    for field, value in updates.items():
        setattr(row, field, value)

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="riga_aggiornata")
    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="riga_aggiornata",
        user_id=actor_id,
    )
    db.commit()
    updated_row = get_acquisition_row(db, row.id)
    log_service.record("acquisition", f"Acquisition row updated: {updated_row.id}", actor_email)
    return serialize_acquisition_row_detail(updated_row)


def create_evidence(
    db: Session,
    row: AcquisitionRow,
    payload: DocumentEvidenceCreateRequest,
    actor_id: int,
) -> DocumentEvidenceResponse:
    document = get_document(db, payload.document_id)
    if payload.document_page_id is not None:
        page = (
            db.query(DocumentPage)
            .filter(DocumentPage.id == payload.document_page_id, DocumentPage.document_id == document.id)
            .one_or_none()
        )
        if page is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document page does not belong to document")

    evidence = DocumentEvidence(
        document_id=document.id,
        document_page_id=payload.document_page_id,
        acquisition_row_id=row.id,
        blocco=payload.blocco,
        tipo_evidenza=payload.tipo_evidenza,
        bbox=payload.bbox,
        testo_grezzo=payload.testo_grezzo,
        storage_key_derivato=payload.storage_key_derivato,
        metodo_estrazione=payload.metodo_estrazione,
        mascherato=payload.mascherato,
        confidenza=payload.confidenza,
        utente_creazione_id=actor_id,
    )
    db.add(evidence)
    db.flush()
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco=payload.blocco,
        azione="evidenza_creata",
        user_id=actor_id,
    )
    db.commit()
    db.refresh(evidence)
    return serialize_evidence(evidence)


def upsert_read_value(
    db: Session,
    row: AcquisitionRow,
    payload: ReadValueUpsertRequest,
    actor_id: int,
) -> ReadValueResponse:
    if payload.document_evidence_id is not None:
        evidence = db.get(DocumentEvidence, payload.document_evidence_id)
        if evidence is None or evidence.acquisition_row_id != row.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Evidence not available for row")

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason=f"{payload.blocco}:{payload.campo}")
    read_value = _upsert_read_value_model(
        db=db,
        acquisition_row_id=row.id,
        blocco=payload.blocco,
        campo=payload.campo,
        valore_grezzo=payload.valore_grezzo,
        valore_standardizzato=payload.valore_standardizzato,
        valore_finale=payload.valore_finale,
        stato=payload.stato,
        document_evidence_id=payload.document_evidence_id,
        metodo_lettura=payload.metodo_lettura,
        fonte_documentale=payload.fonte_documentale,
        confidenza=payload.confidenza,
        actor_id=actor_id,
    )
    if payload.blocco == "ddt":
        _sync_row_from_ddt_values(db, row)
        db.add(row)
    _sync_row_statuses(db, row)
    db.commit()
    db.refresh(read_value)
    return serialize_read_value(read_value)


def upsert_match(
    db: Session,
    row: AcquisitionRow,
    payload: MatchUpsertRequest,
    actor_id: int,
) -> MatchResponse:
    certificate_document = _get_document_of_type(db, payload.document_certificato_id, "certificato")
    if row.fornitore_id is not None and certificate_document.fornitore_id is not None:
        if row.fornitore_id != certificate_document.fornitore_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Certificate supplier mismatch for row")

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="match")
    match = (
        db.query(CertificateMatch)
        .options(selectinload(CertificateMatch.candidates))
        .filter(CertificateMatch.acquisition_row_id == row.id)
        .one_or_none()
    )
    previous_document_id = row.document_certificato_id
    action = "match_creato"

    if match is None:
        match = CertificateMatch(acquisition_row_id=row.id)
        db.add(match)
    else:
        action = "match_aggiornato"

    match.document_certificato_id = certificate_document.id
    match.stato = payload.stato
    match.motivo_breve = payload.motivo_breve
    match.fonte_proposta = payload.fonte_proposta
    match.timestamp = datetime.now(UTC)
    match.utente_conferma_id = actor_id if payload.stato in {"confermato", "cambiato"} else None
    row.document_certificato_id = certificate_document.id
    if row.fornitore_id is None and certificate_document.fornitore_id is not None:
        row.fornitore_id = certificate_document.fornitore_id
    if not row.fornitore_raw and certificate_document.supplier is not None:
        row.fornitore_raw = certificate_document.supplier.ragione_sociale
    _sync_row_cdq_from_certificate_document(db, row, certificate_document)

    if previous_document_id != certificate_document.id:
        action = "match_cambiato" if previous_document_id is not None else action
        db.add(
            AcquisitionValueHistory(
                acquisition_row_id=row.id,
                blocco="match",
                campo="document_certificato_id",
                valore_prima=str(previous_document_id) if previous_document_id is not None else None,
                valore_dopo=str(certificate_document.id),
                utente_id=actor_id,
            )
        )

    db.flush()

    existing_candidates = {candidate.document_certificato_id: candidate for candidate in match.candidates}
    requested_candidate_ids = {candidate.document_certificato_id for candidate in payload.candidates}
    for candidate in list(match.candidates):
        if candidate.document_certificato_id not in requested_candidate_ids:
            db.delete(candidate)

    for candidate_payload in payload.candidates:
        _get_document_of_type(db, candidate_payload.document_certificato_id, "certificato")
        candidate = existing_candidates.get(candidate_payload.document_certificato_id)
        if candidate is None:
            candidate = CertificateMatchCandidate(
                match_certificato_id=match.id,
                document_certificato_id=candidate_payload.document_certificato_id,
            )
            db.add(candidate)
        candidate.rank = candidate_payload.rank
        candidate.motivo_breve = candidate_payload.motivo_breve
        candidate.fonte_proposta = candidate_payload.fonte_proposta
        candidate.stato = candidate_payload.stato

    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="match",
        azione=action,
        user_id=actor_id,
        nota_breve=payload.motivo_breve,
    )
    _sync_row_from_match_values(db, row)
    _sync_row_statuses(db, row)
    db.commit()
    updated_row = get_acquisition_row(db, row.id)
    if updated_row.certificate_match is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Match not available after update")
    return serialize_match(updated_row.certificate_match)


def detect_standard_notes(
    db: Session,
    row: AcquisitionRow,
    actor_id: int,
    openai_api_key: str | None = None,
) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="note")
    matches = _detect_note_matches(certificate_document.pages)
    if not matches and openai_api_key:
        certificate_document = _ensure_document_page_images(db, certificate_document)
        if _document_has_image_pages(certificate_document):
            template = resolve_supplier_template(
                row.supplier.ragione_sociale if row.supplier is not None else row.fornitore_raw
            )
            if template is not None and _supplier_supports_ai_vision_pipeline(template.supplier_key):
                payload = _get_supplier_certificate_ai_payload(
                    db=db,
                    supplier_key=template.supplier_key,
                    certificate_document=certificate_document,
                    openai_api_key=openai_api_key,
                    certificate_ai_cache=None,
                )
                vision_matches = cast(dict[str, dict[str, str | int]], payload.get("notes") or {})
            else:
                vision_matches = _detect_note_matches_with_vision(
                    certificate_document.pages,
                    openai_api_key=openai_api_key,
                    supplier_key=template.supplier_key if template is not None else None,
                )
            if vision_matches:
                matches = vision_matches
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="note",
            azione="note_non_rilevate",
            user_id=actor_id,
        )
        _sync_row_statuses(db, row)
        db.commit()
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    for field_name, match in matches.items():
        evidence = DocumentEvidence(
            document_id=certificate_document.id,
            document_page_id=match["page_id"],
            acquisition_row_id=row.id,
            blocco="note",
            tipo_evidenza="testo",
            bbox=None,
            testo_grezzo=match["snippet"],
            storage_key_derivato=None,
            metodo_estrazione="pdf_text",
            mascherato=False,
            confidenza=0.9,
            utente_creazione_id=actor_id,
        )
        db.add(evidence)
        db.flush()

        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="note",
            campo=field_name,
            valore_grezzo=match["snippet"],
            valore_standardizzato=match["standardized"],
            valore_finale=match["final"],
            stato="proposto",
            document_evidence_id=evidence.id,
            metodo_lettura="pdf_text",
            fonte_documentale="certificato",
            confidenza=0.9,
            actor_id=actor_id,
        )

    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="note",
        azione="note_rilevate",
        user_id=actor_id,
        nota_breve=", ".join(sorted(matches.keys())),
    )
    _sync_row_statuses(db, row)
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def detect_chemistry(
    db: Session,
    row: AcquisitionRow,
    actor_id: int,
    openai_api_key: str | None = None,
) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="chimica")
    supplier_name = row.supplier.ragione_sociale if row.supplier is not None else row.fornitore_raw
    matches = _detect_chemistry_matches(certificate_document.pages, supplier_name=supplier_name)
    if openai_api_key and len(matches) < 4:
        certificate_document = _ensure_document_page_images(db, certificate_document)
        if _document_has_image_pages(certificate_document):
            template = resolve_supplier_template(supplier_name) if supplier_name else None
            if template is not None and _supplier_supports_ai_vision_pipeline(template.supplier_key):
                payload = _get_supplier_certificate_ai_payload(
                    db=db,
                    supplier_key=template.supplier_key,
                    certificate_document=certificate_document,
                    openai_api_key=openai_api_key,
                    certificate_ai_cache=None,
                )
                vision_matches = cast(dict[str, dict[str, str | int]], payload.get("chemistry") or {})
            else:
                vision_matches = _detect_chemistry_matches_with_vision(
                    certificate_document.pages,
                    openai_api_key=openai_api_key,
                    supplier_key=template.supplier_key if template is not None else None,
                )
            if vision_matches:
                for field_name, match in vision_matches.items():
                    matches.setdefault(field_name, match)
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="chimica",
            azione="chimica_non_rilevata",
            user_id=actor_id,
        )
        _sync_row_statuses(db, row)
        db.commit()
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    _prune_unconfirmed_block_values(db=db, row_id=row.id, block="chimica", keep_fields=set(matches.keys()))

    for field_name, match in matches.items():
        extraction_method = str(match.get("method") or "pdf_text")
        confidence = 0.76 if extraction_method == "chatgpt" else 0.88
        evidence = _create_text_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=match["page_id"],
            blocco="chimica",
            snippet=match["snippet"],
            actor_id=actor_id,
            confidence=confidence,
        )
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="chimica",
            campo=field_name,
            valore_grezzo=match["raw"],
            valore_standardizzato=match["standardized"],
            valore_finale=match["final"],
            stato="proposto",
            document_evidence_id=evidence.id,
            metodo_lettura=extraction_method,
            fonte_documentale="certificato",
            confidenza=confidence,
            actor_id=actor_id,
        )

    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="chimica",
        azione="chimica_rilevata",
        user_id=actor_id,
        nota_breve=", ".join(sorted(matches.keys())),
    )
    _sync_row_statuses(db, row)
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def detect_properties(
    db: Session,
    row: AcquisitionRow,
    actor_id: int,
    openai_api_key: str | None = None,
) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="proprieta")
    supplier_name = row.supplier.ragione_sociale if row.supplier is not None else row.fornitore_raw
    matches = _detect_property_matches(certificate_document.pages, supplier_name=supplier_name)
    if openai_api_key and len(matches) < 3:
        certificate_document = _ensure_document_page_images(db, certificate_document)
        if _document_has_image_pages(certificate_document):
            template = resolve_supplier_template(supplier_name) if supplier_name else None
            if template is not None and _supplier_supports_ai_vision_pipeline(template.supplier_key):
                payload = _get_supplier_certificate_ai_payload(
                    db=db,
                    supplier_key=template.supplier_key,
                    certificate_document=certificate_document,
                    openai_api_key=openai_api_key,
                    certificate_ai_cache=None,
                )
                vision_matches = cast(dict[str, dict[str, str | int]], payload.get("properties") or {})
            else:
                vision_matches = _detect_property_matches_with_vision(
                    certificate_document.pages,
                    openai_api_key=openai_api_key,
                    supplier_key=template.supplier_key if template is not None else None,
                )
            if vision_matches:
                for field_name, match in vision_matches.items():
                    matches.setdefault(field_name, match)
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="proprieta",
            azione="proprieta_non_rilevate",
            user_id=actor_id,
        )
        _sync_row_statuses(db, row)
        db.commit()
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    _prune_unconfirmed_block_values(db=db, row_id=row.id, block="proprieta", keep_fields=set(matches.keys()))

    for field_name, match in matches.items():
        extraction_method = str(match.get("method") or "pdf_text")
        confidence = 0.74 if extraction_method == "chatgpt" else 0.86
        evidence = _create_text_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=match["page_id"],
            blocco="proprieta",
            snippet=match["snippet"],
            actor_id=actor_id,
            confidence=confidence,
        )
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="proprieta",
            campo=field_name,
            valore_grezzo=match["raw"],
            valore_standardizzato=match["standardized"],
            valore_finale=match["final"],
            stato="proposto",
            document_evidence_id=evidence.id,
            metodo_lettura=extraction_method,
            fonte_documentale="certificato",
            confidenza=confidence,
            actor_id=actor_id,
        )

    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="proprieta",
        azione="proprieta_rilevate",
        user_id=actor_id,
        nota_breve=", ".join(sorted(matches.keys())),
    )
    _sync_row_statuses(db, row)
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def validate_final_row(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    block_states = _compute_block_states_from_db(db, row)
    required_blocks = ("ddt", "match", "chimica", "proprieta", "note")
    not_ready = [block for block in required_blocks if block_states.get(block) != "verde"]
    if not_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Final validation requires all blocks green. Missing: {', '.join(not_ready)}",
        )

    row.validata_finale = True
    row.stato_workflow = "validata_quality"
    row.stato_tecnico = "verde"
    row.priorita_operativa = "bassa"
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="workflow",
        azione="validazione_finale_confermata",
        user_id=actor_id,
    )
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def extract_core_fields(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="campi_core")
    extracted_count = 0
    supplier_candidates = [
        row.supplier.ragione_sociale if row.supplier is not None else None,
        row.fornitore_raw,
    ]

    ddt_document: Document | None = None
    ddt_matches: dict[str, dict[str, object]] = {}
    if row.document_ddt_id is not None:
        ddt_document = get_document(db, row.document_ddt_id)
        if not ddt_document.pages:
            ddt_document = _index_document_from_path(db, ddt_document)
        ddt_document = _ensure_document_page_ocr(db, ddt_document)
        supplier_candidates.append(ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None)

    certificate_document: Document | None = None
    if row.document_certificato_id is not None:
        certificate_document = get_document(db, row.document_certificato_id)
        if not certificate_document.pages:
            certificate_document = _index_document_from_path(db, certificate_document)
        certificate_document = _ensure_document_page_ocr(db, certificate_document)
        supplier_candidates.append(
            certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None
        )

    template = resolve_supplier_template(*supplier_candidates)
    supplier_key = template.supplier_key if template is not None else None

    if ddt_document is not None:
        ddt_matches = reader_detect_ddt_core_matches(ddt_document.pages, supplier_key=supplier_key)
        for field_name, match in ddt_matches.items():
            existing_row_value = _row_ddt_core_field_value(row, field_name)
            if existing_row_value is not None:
                matched_value = _string_or_none(match.get("final"))
                if reader_normalize_match_token(existing_row_value) != reader_normalize_match_token(matched_value):
                    continue
            evidence = _create_text_evidence(
                db=db,
                row_id=row.id,
                document_id=ddt_document.id,
                document_page_id=match["page_id"],
                blocco="ddt",
                snippet=match["snippet"],
                actor_id=actor_id,
                confidence=0.85,
            )
            _upsert_read_value_model(
                db=db,
                acquisition_row_id=row.id,
                blocco="ddt",
                campo=field_name,
                valore_grezzo=match["snippet"],
                valore_standardizzato=match["standardized"],
                valore_finale=match["final"],
                stato="proposto",
                document_evidence_id=evidence.id,
                metodo_lettura="regex",
                fonte_documentale="ddt",
                confidenza=0.85,
                actor_id=actor_id,
                )
            extracted_count += 1

        _sync_ddt_values_from_row_fields(db, row, actor_id=actor_id)
        _sync_row_from_ddt_values(db, row)

        if row.cdq is None and "cdq" in ddt_matches:
            row.cdq = _string_or_none(ddt_matches["cdq"]["final"])
        if row.cdq is None and "numero_certificato_ddt" in ddt_matches:
            row.cdq = _string_or_none(ddt_matches["numero_certificato_ddt"]["final"])
        if row.colata is None and "colata" in ddt_matches:
            row.colata = _string_or_none(ddt_matches["colata"]["final"])
        if row.diametro is None and "diametro" in ddt_matches:
            row.diametro = _string_or_none(ddt_matches["diametro"]["final"])
        if row.ddt is None and "ddt" in ddt_matches:
            row.ddt = _string_or_none(ddt_matches["ddt"]["final"])
        if row.peso is None and "peso" in ddt_matches:
            row.peso = _string_or_none(ddt_matches["peso"]["final"])
        if row.ordine is None and supplier_key != "aluminium_bozen" and "ordine" in ddt_matches:
            row.ordine = _string_or_none(ddt_matches["ordine"]["final"])

    if certificate_document is not None:
        certificate_template = resolve_supplier_template(
            row.supplier.ragione_sociale if row.supplier is not None else None,
            row.fornitore_raw,
            ddt_document.supplier.ragione_sociale if ddt_document and ddt_document.supplier else None,
            certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
        )
        certificate_matches = reader_detect_certificate_core_matches(
            certificate_document.pages,
            supplier_key=certificate_template.supplier_key if certificate_template is not None else None,
        )
        for field_name, match in certificate_matches.items():
            evidence = _create_text_evidence(
                db=db,
                row_id=row.id,
                document_id=certificate_document.id,
                document_page_id=match["page_id"],
                blocco="match",
                snippet=match["snippet"],
                actor_id=actor_id,
                confidence=0.82,
            )
            _upsert_read_value_model(
                db=db,
                acquisition_row_id=row.id,
                blocco="match",
                campo=field_name,
                valore_grezzo=match["snippet"],
                valore_standardizzato=match["standardized"],
                valore_finale=match["final"],
                stato="proposto",
                document_evidence_id=evidence.id,
                metodo_lettura="regex",
                fonte_documentale="certificato",
                confidenza=0.82,
                actor_id=actor_id,
            )
            extracted_count += 1
        _sync_row_from_match_values(db, row)

    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="campi_core_rilevati" if extracted_count else "campi_core_non_rilevati",
        user_id=actor_id,
        nota_breve=str(extracted_count) if extracted_count else None,
    )
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def process_row_minimal(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    extract_core_fields(db=db, row=row, actor_id=actor_id)
    refreshed_row = get_acquisition_row(db, row.id)
    if refreshed_row.document_certificato_id is not None:
        detect_chemistry(db=db, row=refreshed_row, actor_id=actor_id)
        refreshed_row = get_acquisition_row(db, row.id)
        detect_properties(db=db, row=refreshed_row, actor_id=actor_id)
        refreshed_row = get_acquisition_row(db, row.id)
        detect_standard_notes(db=db, row=refreshed_row, actor_id=actor_id, openai_api_key=None)
        refreshed_row = get_acquisition_row(db, row.id)
    return serialize_acquisition_row_detail(refreshed_row)


def _extract_aluminium_bozen_ddt_row_groups_with_vision(
    db: Session,
    *,
    ddt_document: Document,
    openai_api_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if not ddt_document.pages:
        ddt_document = _index_document_from_path(db, ddt_document)
    ddt_document = _ensure_document_page_images(db, ddt_document)

    image_pages = [page for page in ddt_document.pages if page.immagine_pagina_storage_key]
    if not image_pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DDT has no image pages available for AI")

    crop_definitions = _build_aluminium_bozen_ddt_group_crops(image_pages)
    if not crop_definitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to prepare DDT row-group crops for AI",
        )

    local_plan = build_document_row_split_plan(prepare_document_for_reader(db, ddt_document))
    fallback_ddt = next(
        (_string_or_none(candidate.ddt_number) for candidate in local_plan.row_split_candidates if candidate.ddt_number),
        None,
    )
    if fallback_ddt is None:
        local_matches = reader_detect_ddt_core_matches(ddt_document.pages, supplier_key="aluminium_bozen")
        fallback_ddt = _split_plan_match_value(local_matches, "ddt")

    ddt_number_raw, raw_rows, ai_document_payload_raw = _extract_aluminium_bozen_ddt_row_groups_from_openai(
        crop_definitions,
        openai_api_key=openai_api_key,
    )
    return _sanitize_aluminium_bozen_ai_row_groups(
        ddt_number_raw=ddt_number_raw or fallback_ddt,
        raw_rows=raw_rows,
        ai_document_payload_raw=ai_document_payload_raw,
    )


def _extract_impol_ddt_row_groups_with_vision(
    db: Session,
    *,
    ddt_document: Document,
    openai_api_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if not ddt_document.pages:
        ddt_document = _index_document_from_path(db, ddt_document)
    ddt_document = _ensure_document_page_images(db, ddt_document)

    image_pages = [page for page in ddt_document.pages if page.immagine_pagina_storage_key]
    if not image_pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DDT has no image pages available for AI")

    crop_definitions = _build_impol_ddt_group_crops(image_pages)
    if not crop_definitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to prepare Impol DDT row-group crops for AI",
        )

    local_plan = build_document_row_split_plan(prepare_document_for_reader(db, ddt_document))
    fallback_ddt = next(
        (_string_or_none(candidate.ddt_number) for candidate in local_plan.row_split_candidates if candidate.ddt_number),
        None,
    )
    if fallback_ddt is None:
        local_matches = reader_detect_ddt_core_matches(ddt_document.pages, supplier_key="impol")
        fallback_ddt = _split_plan_match_value(local_matches, "ddt")

    ddt_number_raw, packing_list_no_raw, raw_rows, ai_document_payload_raw = _extract_impol_ddt_row_groups_from_openai(
        crop_definitions,
        openai_api_key=openai_api_key,
    )
    return _sanitize_impol_ai_row_groups(
        ddt_number_raw=ddt_number_raw or fallback_ddt,
        packing_list_no_raw=packing_list_no_raw,
        raw_rows=raw_rows,
        ai_document_payload_raw=ai_document_payload_raw,
    )


def _build_aluminium_bozen_ddt_group_crops(
    pages: list[DocumentPage],
) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    if not pages:
        return crops

    sorted_pages = sorted(pages, key=lambda item: item.numero_pagina)
    first_page = sorted_pages[0]

    crop_specs: list[tuple[DocumentPage, str, str, float, float, float, float]] = [
        (first_page, "group_header_num", "header_num", 0.04, 0.18, 0.05, 0.95),
        (first_page, "group_rows_overview", "row_groups_overview", 0.16, 0.92, 0.03, 0.97),
        (first_page, "group_material_rows", "material_rows", 0.18, 0.76, 0.03, 0.97),
        (first_page, "group_packing_rows", "packing_rows", 0.52, 0.96, 0.02, 0.98),
    ]

    for page in sorted_pages[1:]:
        crop_specs.append(
            (
                page,
                f"group_packing_rows_p{page.numero_pagina}",
                "packing_rows",
                0.12,
                0.96,
                0.02,
                0.98,
            )
        )

    for page, suffix, role, top_ratio, bottom_ratio, left_ratio, right_ratio in crop_specs:
        crop_definition = _create_dynamic_page_crop(
            page,
            suffix=suffix,
            role=role,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
            left_ratio=left_ratio,
            right_ratio=right_ratio,
            save_crop=_save_ddt_crop,
        )
        if crop_definition is not None:
            crops[str(crop_definition["label"])] = crop_definition

    return crops


def _build_impol_ddt_group_crops(
    pages: list[DocumentPage],
) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    image_pages = [page for page in sorted(pages, key=lambda item: item.numero_pagina) if page.immagine_pagina_storage_key]
    if not image_pages:
        return crops

    for index, page in enumerate(image_pages):
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            masked_page = _build_impol_ddt_masked_page(image)
            storage_key = _save_ddt_crop(page, masked_page, f"impol_masked_page_{page.numero_pagina}")
            width, height = masked_page.size
            role_specs = [("row_groups_page", "row_groups_page")]
            if index == 0:
                role_specs.insert(0, ("header_page", "header_page"))
            else:
                role_specs.insert(0, ("continuation_page", "continuation_page"))
            for suffix, role in role_specs:
                label = f"page{page.numero_pagina}_{suffix}"
                crops[label] = {
                    "label": label,
                    "role": role,
                    "page_id": page.id,
                    "page_number": page.numero_pagina,
                    "storage_key": storage_key,
                    "bbox": f"0,0,{width},{height}",
                }
    return crops


def _build_impol_ddt_masked_page(image: Image.Image) -> Image.Image:
    masked = image.convert("RGB")
    _mask_impol_receiver_block(masked)
    return masked


def _mask_impol_receiver_block(image: Image.Image) -> None:
    _mask_ocr_block_between_anchors(
        image,
        start_terms=("RECEIVER",),
        stop_terms=("DELIVERY TERMS", "TRUCK", "CONTAINER", "PRODUCT CODE", "PRODUCT DESCRIPTION"),
        max_following_lines=8,
        right_limit_ratio=0.56,
    )


def _extract_aluminium_bozen_ddt_row_groups_from_openai(
    crops: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> tuple[str | None, list[dict[str, object]], str]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi queste immagini di un documento tecnico di trasporto e ricostruisci tutte le righe logiche materiale presenti. "
                "Una riga logica puo essere distribuita tra il blocco materiale della prima pagina e uno o piu blocchi packing nelle pagine successive. "
                "Se il documento contiene 3 righe logiche, restituisci 3 elementi; se ne contiene 5, restituisci 5 elementi. "
                "Non unire dati di righe diverse e non inventare valori mancanti. "
                "Non fare il match con nessun certificato e non normalizzare i valori. "
                "Per l'ordine cliente usa solo il valore associato a Vs. Odv o Rif. ordine cliente. "
                "Non usare mai Rif. ordine AB o Rif. ns. Odv N. come ordine cliente. "
                "Lo stesso ordine cliente puo comparire su piu righe diverse dello stesso DDT: se e chiaramente riferito a piu righe, riportalo in ogni riga interessata. "
                "customer_order_raw deve contenere il testo raw completo del campo ordine cliente della riga, con numero e data; se manca la data, restituisci null. "
                "certificate_no_raw deve essere il valore del Cert. N. della stessa riga logica, quando visibile nel packing group collegato. "
                "Non saltare certificate_no_raw se e presente; non usare numeri di norme come EN 10204 3.1 o simili. "
                "Se la stessa riga logica appare tra material_rows e packing_rows, unisci quei dati nello stesso elemento rows. "
                "Restituisci solo JSON con questa struttura: "
                "{\"ddt_number_raw\":\"string|null\",\"rows\":[{\"row_index\":1,"
                "\"customer_order_raw\":\"string|null\",\"article_code_raw\":\"string|null\","
                "\"customer_code_raw\":\"string|null\",\"alloy_raw\":\"string|null\","
                "\"diameter_raw\":\"string|null\",\"cast_raw\":\"string|null\","
                "\"certificate_no_raw\":\"string|null\",\"net_weight_raw\":\"string|null\","
                "\"source_crops\":[\"label\"]}]}"
            ),
        }
    ]

    for crop_label, crop in crops.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Crop label: {crop_label}; "
                    f"role: {crop.get('role') or 'unknown'}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{encoded}",
                "detail": "high",
            }
        )

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="DDT row-group AI request failed") from exc

    return (*_parse_openai_json_payload_for_row_groups(response.output_text), response.output_text)


def _extract_impol_ddt_row_groups_from_openai(
    crops: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> tuple[str | None, str | None, list[dict[str, object]], str]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi queste immagini di un documento tecnico di trasporto e ricostruisci tutte le righe logiche materiale presenti. "
                "Una riga logica puo essere distribuita tra il blocco posizione prodotto e uno o piu blocchi packing della stessa posizione. "
                "Se il documento contiene 3 righe logiche, restituisci 3 elementi; se ne contiene 5, restituisci 5 elementi. "
                "Non unire dati di righe diverse e non inventare valori mancanti. "
                "Non fare il match con nessun certificato e non normalizzare i valori. "
                "Per l'ordine cliente usa solo il valore associato a Your order No. "
                "Non usare Customer No. o Supplier No. come ordine cliente. "
                "Lo stesso ordine cliente puo comparire su piu righe diverse dello stesso DDT: se e chiaramente riferito a piu righe, riportalo in ogni riga interessata. "
                "Una stessa riga logica puo comparire tra intestazione della posizione prodotto, descrizione prodotto, righe packing unit e riga Pos.total. "
                "Se la stessa riga logica appare tra questi blocchi, unisci quei dati nello stesso elemento rows. "
                "ddt_number_raw deve essere il numero del documento letto dal titolo PACKING LIST, come appare nel documento. "
                "packing_list_no_raw deve essere il riferimento packing list utile al collegamento con i certificati. "
                "customer_order_raw deve essere il valore raw completo del campo ordine cliente della riga, letto da Your order No. "
                "supplier_order_no_raw deve essere il valore raw del codice di ordine fornitore della stessa riga, quando visibile sotto Product code. "
                "product_code_raw deve essere il codice prodotto principale della riga, letto dalla prima riga sotto Product code. "
                "product_description_raw deve essere il testo raw completo del blocco Product description della stessa riga. "
                "alloy_raw deve essere la lega o stato letto dalla Product description della stessa riga. "
                "diameter_raw deve essere il valore di diametro della stessa riga, se compare come DIA nella Product description. "
                "cast_raw deve essere la Charge della stessa riga logica, quando visibile nelle packing unit collegate. "
                "net_weight_raw deve essere il peso netto totale della posizione, letto dal Pos.total della stessa posizione. "
                "Non usare i pesi delle singole packing unit come net_weight_raw finale. "
                "Usa solo testo realmente visibile. Non inventare. Non inferire. Non normalizzare. "
                "Se un campo non e chiaramente leggibile, restituisci null. "
                "Restituisci solo JSON con questa struttura: "
                "{\"ddt_number_raw\":\"string|null\",\"packing_list_no_raw\":\"string|null\",\"rows\":[{\"row_index\":1,"
                "\"customer_order_raw\":\"string|null\",\"supplier_order_no_raw\":\"string|null\",\"product_code_raw\":\"string|null\","
                "\"product_description_raw\":\"string|null\",\"alloy_raw\":\"string|null\",\"diameter_raw\":\"string|null\","
                "\"cast_raw\":\"string|null\",\"net_weight_raw\":\"string|null\",\"source_crops\":[\"label\"]}]}"
            ),
        }
    ]

    for crop_label, crop in crops.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Crop label: {crop_label}; "
                    f"role: {crop.get('role') or 'unknown'}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{encoded}",
                "detail": "high",
            }
        )

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Impol DDT row-group AI request failed") from exc

    return (*_parse_openai_json_payload_for_impol_row_groups(response.output_text), response.output_text)


def _parse_openai_json_payload_for_row_groups(payload: str) -> tuple[str | None, list[dict[str, object]]]:
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from DDT row-group AI")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from DDT row-group AI") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected DDT row-group AI payload")

    rows_payload = data.get("rows")
    if not isinstance(rows_payload, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Missing rows in DDT row-group AI payload")

    normalized_rows: list[dict[str, object]] = []
    for index, raw_row in enumerate(rows_payload, start=1):
        if not isinstance(raw_row, dict):
            continue
        raw_row_index = raw_row.get("row_index")
        try:
            normalized_row_index = int(raw_row_index) if raw_row_index is not None else index
        except (TypeError, ValueError):
            normalized_row_index = index
        source_crops = raw_row.get("source_crops")
        normalized_sources = [
            item
            for item in (
                _string_or_none(source_crop) for source_crop in (source_crops if isinstance(source_crops, list) else [])
            )
            if item is not None
        ]
        normalized_rows.append(
            {
                "row_index": normalized_row_index,
                "customer_order_raw": _string_or_none(raw_row.get("customer_order_raw")),
                "article_code_raw": _string_or_none(raw_row.get("article_code_raw")),
                "customer_code_raw": _string_or_none(raw_row.get("customer_code_raw")),
                "alloy_raw": _string_or_none(raw_row.get("alloy_raw")),
                "diameter_raw": _string_or_none(raw_row.get("diameter_raw")),
                "cast_raw": _string_or_none(raw_row.get("cast_raw")),
                "certificate_no_raw": _string_or_none(raw_row.get("certificate_no_raw")),
                "net_weight_raw": _string_or_none(raw_row.get("net_weight_raw")),
                "source_crops": normalized_sources,
            }
        )

    return _string_or_none(data.get("ddt_number_raw")), normalized_rows


def _parse_openai_json_payload_for_impol_row_groups(
    payload: str,
) -> tuple[str | None, str | None, list[dict[str, object]]]:
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from Impol DDT row-group AI")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from Impol DDT row-group AI") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected Impol DDT row-group AI payload")

    rows_payload = data.get("rows")
    if not isinstance(rows_payload, list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Missing rows in Impol DDT row-group AI payload")

    normalized_rows: list[dict[str, object]] = []
    for index, raw_row in enumerate(rows_payload, start=1):
        if not isinstance(raw_row, dict):
            continue
        raw_row_index = raw_row.get("row_index")
        try:
            normalized_row_index = int(raw_row_index) if raw_row_index is not None else index
        except (TypeError, ValueError):
            normalized_row_index = index
        source_crops = raw_row.get("source_crops")
        normalized_sources = [
            item
            for item in (
                _string_or_none(source_crop) for source_crop in (source_crops if isinstance(source_crops, list) else [])
            )
            if item is not None
        ]
        normalized_rows.append(
            {
                "row_index": normalized_row_index,
                "customer_order_raw": _string_or_none(raw_row.get("customer_order_raw")),
                "supplier_order_no_raw": _string_or_none(raw_row.get("supplier_order_no_raw")),
                "product_code_raw": _string_or_none(raw_row.get("product_code_raw")),
                "product_description_raw": _string_or_none(raw_row.get("product_description_raw")),
                "alloy_raw": _string_or_none(raw_row.get("alloy_raw")),
                "diameter_raw": _string_or_none(raw_row.get("diameter_raw")),
                "cast_raw": _string_or_none(raw_row.get("cast_raw")),
                "net_weight_raw": _string_or_none(raw_row.get("net_weight_raw")),
                "source_crops": normalized_sources,
            }
        )

    return _string_or_none(data.get("ddt_number_raw")), _string_or_none(data.get("packing_list_no_raw")), normalized_rows


def _sanitize_aluminium_bozen_ai_row_groups(
    *,
    ddt_number_raw: str | None,
    raw_rows: list[dict[str, object]],
    ai_document_payload_raw: str | None = None,
) -> list[ReaderRowSplitCandidateResponse]:
    sanitized_rows: list[ReaderRowSplitCandidateResponse] = []
    normalized_ddt = _sanitize_ddt_number_candidate(ddt_number_raw, None)

    for index, raw_row in enumerate(raw_rows, start=1):
        customer_order_raw = _string_or_none(raw_row.get("customer_order_raw"))
        article_code_raw = _string_or_none(raw_row.get("article_code_raw"))
        customer_code_raw = _string_or_none(raw_row.get("customer_code_raw"))
        alloy_raw = _string_or_none(raw_row.get("alloy_raw"))
        diameter_raw = _string_or_none(raw_row.get("diameter_raw"))
        cast_raw = _string_or_none(raw_row.get("cast_raw"))
        certificate_no_raw = _string_or_none(raw_row.get("certificate_no_raw"))
        net_weight_raw = _string_or_none(raw_row.get("net_weight_raw"))
        source_crops = cast(list[str], raw_row.get("source_crops") or [])

        certificate_no = _extract_token_from_value_or_evidence(
            certificate_no_raw,
            certificate_no_raw,
            r"\b\d{4,7}[A-Z]?\b",
            disallow={"10204"},
        )
        if certificate_no is not None and _looks_like_invalid_cdq(certificate_no, certificate_no_raw):
            certificate_no = None

        alloy_value = None
        if alloy_raw is not None:
            alloy_match = re.search(
                r"\b([0-9]{4}[A-Z]*)\s*(?:HF\s*/\s*F|H\s*/\s*F|G\s*/\s*F|GF\b|HF\b|/F\b|F\b)",
                alloy_raw.upper(),
            )
            if alloy_match is not None:
                alloy_value = f"{alloy_match.group(1)} F"

        diameter_value = _extract_token_from_value_or_evidence(
            diameter_raw,
            diameter_raw,
            r"\b\d{1,4}(?:[.,]\d+)?\b",
        )
        weight_value = _normalize_value_for_field("ddt", "peso", net_weight_raw)
        article_code = _extract_token_from_value_or_evidence(
            article_code_raw,
            article_code_raw,
            r"\b[0-9]{2}[A-Z]{2}[0-9A-Z-]{4,}\b",
        )
        customer_code = _extract_token_from_value_or_evidence(
            customer_code_raw,
            customer_code_raw,
            r"\bA[0-9A-Z]{5,}\b",
        )
        cast_value = _extract_token_from_value_or_evidence(
            cast_raw,
            cast_raw,
            r"\b[0-9]{4,}[A-Z0-9]*\b",
        )

        candidate = ReaderRowSplitCandidateResponse(
            candidate_index=index,
            supplier_key="aluminium_bozen",
            ddt_number=normalized_ddt,
            cdq=certificate_no,
            customer_code=customer_code,
            article_code=article_code,
            lega=alloy_value,
            diametro=_normalize_value_for_field("ddt", "diametro", diameter_value),
            peso_netto=weight_value,
            colata=cast_value,
            customer_order_no=_normalize_customer_order_tokens(customer_order_raw),
            snippets=source_crops[:6],
            ai_row_payload_raw=json.dumps(raw_row, ensure_ascii=False),
            ai_document_payload_raw=ai_document_payload_raw,
        )

        if any(
            getattr(candidate, field_name) is not None
            for field_name in (
                "ddt_number",
                "cdq",
                "customer_code",
                "article_code",
                "lega",
                "diametro",
                "peso_netto",
                "colata",
                "customer_order_no",
            )
        ):
            sanitized_rows.append(candidate)

    return sanitized_rows


def _sanitize_impol_ai_row_groups(
    *,
    ddt_number_raw: str | None,
    packing_list_no_raw: str | None,
    raw_rows: list[dict[str, object]],
    ai_document_payload_raw: str | None = None,
) -> list[ReaderRowSplitCandidateResponse]:
    sanitized_rows: list[ReaderRowSplitCandidateResponse] = []
    normalized_ddt = _sanitize_impol_ddt_number_candidate(ddt_number_raw, None)
    normalized_packing_root = normalize_impol_packing_list_root(packing_list_no_raw or normalized_ddt)

    for index, raw_row in enumerate(raw_rows, start=1):
        customer_order_raw = _string_or_none(raw_row.get("customer_order_raw"))
        supplier_order_no_raw = _string_or_none(raw_row.get("supplier_order_no_raw"))
        product_code_raw = _string_or_none(raw_row.get("product_code_raw"))
        product_description_raw = _string_or_none(raw_row.get("product_description_raw"))
        alloy_raw = _string_or_none(raw_row.get("alloy_raw")) or product_description_raw
        diameter_raw = _string_or_none(raw_row.get("diameter_raw")) or product_description_raw
        cast_raw = _string_or_none(raw_row.get("cast_raw"))
        net_weight_raw = _string_or_none(raw_row.get("net_weight_raw"))
        source_crops = cast(list[str], raw_row.get("source_crops") or [])

        customer_order = _extract_token_from_value_or_evidence(
            customer_order_raw,
            customer_order_raw,
            r"\b\d{1,6}\b",
        )
        supplier_order_no = _extract_token_from_value_or_evidence(
            supplier_order_no_raw,
            supplier_order_no_raw,
            r"\b\d{3,6}/\d{1,2}\b",
        )
        product_code_match = re.search(r"\b(\d{6})(?:/\d)?\b", (product_code_raw or "").upper())
        product_code = product_code_match.group(1) if product_code_match is not None else None
        alloy_value = _normalize_impol_alloy_from_text(alloy_raw)
        diameter_value = _normalize_impol_diameter_from_text(diameter_raw)
        cast_value = _extract_token_from_value_or_evidence(
            cast_raw,
            cast_raw,
            r"\b\d{6}\b",
            disallow={"10204"},
        )
        weight_value = _normalize_value_for_field("ddt", "peso", net_weight_raw)

        raw_payload = dict(raw_row)
        if normalized_packing_root is not None and _string_or_none(cast(dict[str, object], raw_payload).get("packing_list_no_raw")) is None:
            raw_payload["packing_list_no_raw"] = normalized_packing_root

        candidate = ReaderRowSplitCandidateResponse(
            candidate_index=index,
            supplier_key="impol",
            ddt_number=normalized_ddt,
            lega=alloy_value,
            diametro=diameter_value,
            peso_netto=weight_value,
            colata=cast_value,
            customer_order_no=customer_order,
            supplier_order_no=supplier_order_no,
            product_code=product_code,
            snippets=source_crops[:6],
            ai_row_payload_raw=json.dumps(raw_payload, ensure_ascii=False),
            ai_document_payload_raw=ai_document_payload_raw,
        )

        if any(
            getattr(candidate, field_name) is not None
            for field_name in (
                "ddt_number",
                "lega",
                "diametro",
                "peso_netto",
                "colata",
                "customer_order_no",
                "supplier_order_no",
                "product_code",
            )
        ):
            sanitized_rows.append(candidate)

    return sanitized_rows


def _normalize_impol_alloy_from_text(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(
        r"\bEN\s*AW\s*([0-9]{4}[A-Z]?)\s+([A-Z0-9/-]{1,10})\b",
        cleaned.upper(),
    )
    if match is None:
        return None
    return re.sub(r"\s+", " ", f"{match.group(1)} {match.group(2)}").strip()


def _normalize_impol_diameter_from_text(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\bDIA\s*([0-9]+(?:[.,][0-9]+)?)\b", cleaned.upper())
    if match is None:
        return None
    return _normalize_numeric_value(match.group(1))


def _apply_aluminium_bozen_ai_row_groups_to_rows(
    db: Session,
    *,
    ddt_document: Document,
    rows: list[AcquisitionRow],
    ai_candidates: list[ReaderRowSplitCandidateResponse],
    actor_id: int,
) -> int:
    if not rows or not ai_candidates:
        return 0

    row_models = [get_acquisition_row(db, row.id) for row in rows]
    assignments = _match_aluminium_bozen_ai_groups_to_rows(db=db, rows=row_models, ai_candidates=ai_candidates)
    applied_rows = 0

    for row_model in row_models:
        ai_candidate = assignments.get(row_model.id)
        if ai_candidate is None:
            continue
        if _apply_aluminium_bozen_ai_candidate_to_row(
            db=db,
            row=row_model,
            ai_candidate=ai_candidate,
            actor_id=actor_id,
            document_id=ddt_document.id,
        ):
            applied_rows += 1

    if applied_rows:
        db.commit()
    return applied_rows


def _match_aluminium_bozen_ai_groups_to_rows(
    db: Session,
    *,
    rows: list[AcquisitionRow],
    ai_candidates: list[ReaderRowSplitCandidateResponse],
) -> dict[int, ReaderRowSplitCandidateResponse]:
    pairs: list[tuple[int, int, int]] = []
    row_value_maps = {
        row.id: {
            value.campo: _final_value_for_row(value)
            for value in (
                db.query(ReadValue)
                .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt")
                .all()
            )
        }
        for row in rows
    }

    for row in rows:
        ddt_values = row_value_maps.get(row.id, {})
        for ai_candidate in ai_candidates:
            score = _score_aluminium_bozen_ai_group_against_row(
                row=row,
                ddt_values=ddt_values,
                ai_candidate=ai_candidate,
            )
            if score >= 70:
                pairs.append((score, row.id, ai_candidate.candidate_index))

    pairs.sort(reverse=True)
    assigned_rows: set[int] = set()
    assigned_candidates: set[int] = set()
    ai_by_index = {candidate.candidate_index: candidate for candidate in ai_candidates}
    assignments: dict[int, ReaderRowSplitCandidateResponse] = {}

    for score, row_id, candidate_index in pairs:
        if row_id in assigned_rows or candidate_index in assigned_candidates:
            continue
        assignments[row_id] = ai_by_index[candidate_index]
        assigned_rows.add(row_id)
        assigned_candidates.add(candidate_index)

    return assignments


def _score_aluminium_bozen_ai_group_against_row(
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
    ai_candidate: ReaderRowSplitCandidateResponse,
) -> int:
    score = 0
    anchor_matches = 0

    row_article = _string_or_none(ddt_values.get("article_code"))
    row_customer_code = _string_or_none(ddt_values.get("customer_code"))
    row_customer_order = _string_or_none(ddt_values.get("customer_order_no")) or _string_or_none(row.ordine)
    row_certificate_no = (
        _string_or_none(ddt_values.get("numero_certificato_ddt"))
        or _string_or_none(ddt_values.get("cdq"))
        or _string_or_none(row.cdq)
    )
    row_cast = _string_or_none(ddt_values.get("colata")) or _string_or_none(row.colata)
    row_diameter = _string_or_none(ddt_values.get("diametro")) or _string_or_none(row.diametro)
    row_alloy = _string_or_none(ddt_values.get("lega")) or _string_or_none(row.lega_base)
    row_weight = _string_or_none(ddt_values.get("peso")) or _string_or_none(row.peso)

    if row_article and ai_candidate.article_code and reader_same_token(row_article, ai_candidate.article_code):
        score += 120
        anchor_matches += 1
    if row_customer_code and ai_candidate.customer_code and reader_same_token(row_customer_code, ai_candidate.customer_code):
        score += 100
        anchor_matches += 1
    if row_customer_order and ai_candidate.customer_order_no and reader_same_token(row_customer_order, ai_candidate.customer_order_no):
        score += 90
        anchor_matches += 1
    if row_certificate_no and ai_candidate.cdq and reader_same_token(row_certificate_no, ai_candidate.cdq):
        score += 85
        anchor_matches += 1
    if row_cast and ai_candidate.colata and reader_same_token(row_cast, ai_candidate.colata):
        score += 75
        anchor_matches += 1
    if row_diameter and ai_candidate.diametro and reader_same_token(row_diameter, ai_candidate.diametro):
        score += 25
    if row_alloy and ai_candidate.lega and reader_same_token(row_alloy, ai_candidate.lega):
        score += 20
    if row_weight and ai_candidate.peso_netto and reader_weights_are_compatible(row_weight, ai_candidate.peso_netto):
        score += 15

    if anchor_matches == 0:
        return 0
    return score


def _apply_aluminium_bozen_ai_candidate_to_row(
    db: Session,
    *,
    row: AcquisitionRow,
    ai_candidate: ReaderRowSplitCandidateResponse,
    actor_id: int,
    document_id: int,
) -> bool:
    if ai_candidate.ai_row_payload_raw:
        _create_ai_payload_evidence(
            db=db,
            row_id=row.id,
            document_id=document_id,
            document_page_id=row.ddt_document.pages[0].id if row.ddt_document and row.ddt_document.pages else None,
            blocco="ddt",
            payload_text=ai_candidate.ai_row_payload_raw,
            actor_id=actor_id,
            confidence=0.72,
        )

    field_values = {
        "ddt": ai_candidate.ddt_number,
        "numero_certificato_ddt": ai_candidate.cdq,
        "customer_order_no": ai_candidate.customer_order_no,
        "customer_code": ai_candidate.customer_code,
        "article_code": ai_candidate.article_code,
        "lega": ai_candidate.lega,
        "diametro": ai_candidate.diametro,
        "colata": ai_candidate.colata,
        "peso": ai_candidate.peso_netto,
    }

    changed_fields = 0
    for field_name, field_value in field_values.items():
        normalized_value = _string_or_none(field_value)
        if normalized_value is None:
            continue
        if _has_stable_value_protected_from_ai(row, "ddt", field_name):
            continue
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="ddt",
            campo=field_name,
            valore_grezzo=normalized_value,
            valore_standardizzato=normalized_value,
            valore_finale=normalized_value,
            stato="proposto",
            document_evidence_id=None,
            metodo_lettura="chatgpt",
            fonte_documentale="ddt",
            confidenza=0.72,
            actor_id=actor_id,
        )
        changed_fields += 1

    if changed_fields == 0:
        return False

    _sync_row_from_ddt_values(db, row)
    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="gruppi_riga_ai_applicati",
        user_id=actor_id,
        nota_breve=str(changed_fields),
    )
    return True


def _apply_impol_ai_candidate_to_row(
    db: Session,
    *,
    row: AcquisitionRow,
    ai_candidate: ReaderRowSplitCandidateResponse,
    actor_id: int,
    document_id: int,
) -> bool:
    if ai_candidate.ai_row_payload_raw:
        _create_ai_payload_evidence(
            db=db,
            row_id=row.id,
            document_id=document_id,
            document_page_id=row.ddt_document.pages[0].id if row.ddt_document and row.ddt_document.pages else None,
            blocco="ddt",
            payload_text=ai_candidate.ai_row_payload_raw,
            actor_id=actor_id,
            confidence=0.72,
        )

    field_values = {
        "ddt": ai_candidate.ddt_number,
        "customer_order_no": ai_candidate.customer_order_no,
        "supplier_order_no": ai_candidate.supplier_order_no,
        "product_code": ai_candidate.product_code,
        "lega": ai_candidate.lega,
        "diametro": ai_candidate.diametro,
        "colata": ai_candidate.colata,
        "peso": ai_candidate.peso_netto,
    }

    changed_fields = 0
    for field_name, field_value in field_values.items():
        normalized_value = _string_or_none(field_value)
        if normalized_value is None:
            continue
        if _has_stable_value_protected_from_ai(row, "ddt", field_name):
            continue
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="ddt",
            campo=field_name,
            valore_grezzo=normalized_value,
            valore_standardizzato=normalized_value,
            valore_finale=normalized_value,
            stato="proposto",
            document_evidence_id=None,
            metodo_lettura="chatgpt",
            fonte_documentale="ddt",
            confidenza=0.72,
            actor_id=actor_id,
        )
        changed_fields += 1

    if changed_fields == 0:
        return False

    _sync_row_from_ddt_values(db, row)
    _sync_ddt_values_from_row_fields(db, row, actor_id=actor_id)
    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="gruppi_riga_ai_applicati",
        user_id=actor_id,
        nota_breve=str(changed_fields),
    )
    return True


def _apply_impol_ai_row_groups_to_rows(
    db: Session,
    *,
    ddt_document: Document,
    rows: list[AcquisitionRow],
    ai_candidates: list[ReaderRowSplitCandidateResponse],
    actor_id: int,
) -> int:
    if not rows or not ai_candidates:
        return 0

    pairs: list[tuple[int, int, int]] = []
    row_value_maps = {
        row.id: {
            value.campo: _final_value_for_row(value)
            for value in (
                db.query(ReadValue)
                .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt")
                .all()
            )
        }
        for row in rows
    }

    for row in rows:
        ddt_values = row_value_maps.get(row.id, {})
        for ai_candidate in ai_candidates:
            score = _score_impol_ai_group_against_row(
                row=row,
                ddt_values=ddt_values,
                ai_candidate=ai_candidate,
            )
            if score >= 70:
                pairs.append((score, row.id, ai_candidate.candidate_index))

    pairs.sort(reverse=True)
    assigned_rows: set[int] = set()
    assigned_candidates: set[int] = set()
    ai_by_index = {candidate.candidate_index: candidate for candidate in ai_candidates}
    applied_rows = 0

    for _, row_id, candidate_index in pairs:
        if row_id in assigned_rows or candidate_index in assigned_candidates:
            continue
        row_model = next((row for row in rows if row.id == row_id), None)
        ai_candidate = ai_by_index.get(candidate_index)
        if row_model is None or ai_candidate is None:
            continue
        if _apply_impol_ai_candidate_to_row(
            db=db,
            row=row_model,
            ai_candidate=ai_candidate,
            actor_id=actor_id,
            document_id=ddt_document.id,
        ):
            applied_rows += 1
        assigned_rows.add(row_id)
        assigned_candidates.add(candidate_index)

    if applied_rows:
        db.commit()
    return applied_rows


def _score_impol_ai_group_against_row(
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
    ai_candidate: ReaderRowSplitCandidateResponse,
) -> int:
    score = 0
    anchor_matches = 0

    row_customer_order = _string_or_none(ddt_values.get("customer_order_no")) or _string_or_none(row.ordine)
    row_supplier_order = _string_or_none(ddt_values.get("supplier_order_no"))
    row_product_code = _string_or_none(ddt_values.get("product_code"))
    row_cast = _string_or_none(ddt_values.get("colata")) or _string_or_none(row.colata)
    row_diameter = _string_or_none(ddt_values.get("diametro")) or _string_or_none(row.diametro)
    row_alloy = _string_or_none(ddt_values.get("lega")) or _string_or_none(row.lega_base)
    row_weight = _string_or_none(ddt_values.get("peso")) or _string_or_none(row.peso)

    if row_customer_order and ai_candidate.customer_order_no and reader_same_token(row_customer_order, ai_candidate.customer_order_no):
        score += 100
        anchor_matches += 1
    if row_supplier_order and ai_candidate.supplier_order_no and reader_same_token(row_supplier_order, ai_candidate.supplier_order_no):
        score += 95
        anchor_matches += 1
    if row_product_code and ai_candidate.product_code and reader_same_token(row_product_code, ai_candidate.product_code):
        score += 100
        anchor_matches += 1
    if row_cast and ai_candidate.colata and reader_same_token(row_cast, ai_candidate.colata):
        score += 110
        anchor_matches += 1
    if row_diameter and ai_candidate.diametro and reader_same_token(row_diameter, ai_candidate.diametro):
        score += 35
    if row_alloy and ai_candidate.lega and reader_same_token(row_alloy, ai_candidate.lega):
        score += 20
    if row_weight and ai_candidate.peso_netto and reader_weights_are_compatible(row_weight, ai_candidate.peso_netto):
        score += 15

    if anchor_matches == 0:
        return 0
    return score


def extract_ddt_fields_with_vision(
    db: Session,
    row: AcquisitionRow,
    *,
    actor_id: int,
    openai_api_key: str,
) -> AcquisitionRowDetailResponse:
    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="ddt_vision")
    ddt_document = get_document(db, row.document_ddt_id)
    if not ddt_document.pages:
        ddt_document = _index_document_from_path(db, ddt_document)
    ddt_document = _ensure_document_page_images(db, ddt_document)

    image_pages = [page for page in ddt_document.pages if page.immagine_pagina_storage_key]
    if not image_pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DDT has no image pages available for vision")

    supplier_key = _resolve_row_supplier_key(row)
    if supplier_key in {"aluminium_bozen", "impol"}:
        sibling_rows = (
            db.query(AcquisitionRow)
            .filter(AcquisitionRow.document_ddt_id == ddt_document.id)
            .order_by(AcquisitionRow.id.asc())
            .all()
        )
        ai_candidates = _extract_supplier_ddt_row_groups_with_vision(
            db=db,
            supplier_key=supplier_key,
            ddt_document=ddt_document,
            openai_api_key=openai_api_key,
        )
        if supplier_key == "aluminium_bozen":
            _apply_aluminium_bozen_ai_row_groups_to_rows(
                db=db,
                ddt_document=ddt_document,
                rows=sibling_rows,
                ai_candidates=ai_candidates,
                actor_id=actor_id,
            )
        else:
            _apply_impol_ai_row_groups_to_rows(
                db=db,
                ddt_document=ddt_document,
                rows=sibling_rows,
                ai_candidates=ai_candidates,
                actor_id=actor_id,
            )
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    ddt_values = {
        value.campo: _final_value_for_row(value)
        for value in (
            db.query(ReadValue)
            .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt")
            .all()
        )
    }

    crop_definitions = _build_ddt_safe_crops(
        image_pages,
        row=row,
        supplier_key=supplier_key,
        ddt_values=ddt_values,
    )
    if not crop_definitions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to prepare DDT image crops for vision")

    extracted = _sanitize_vision_ddt_fields(_extract_ddt_fields_from_openai(crop_definitions, openai_api_key=openai_api_key))
    extracted_count = 0

    for field_name, payload in extracted.items():
        field_value = _string_or_none(payload.get("value"))
        if field_value is None:
            if _is_revisable_chatgpt_ddt_value(row, field_name):
                _upsert_read_value_model(
                    db=db,
                    acquisition_row_id=row.id,
                    blocco="ddt",
                    campo=field_name,
                    valore_grezzo=None,
                    valore_standardizzato=None,
                    valore_finale=None,
                    stato="proposto",
                    document_evidence_id=None,
                    metodo_lettura="chatgpt",
                    fonte_documentale="ddt",
                    confidenza=None,
                    actor_id=actor_id,
                )
            continue
        if _has_stable_value_protected_from_ai(row, "ddt", field_name):
            continue
        source_crop = payload.get("source_crop")
        evidence_text = _string_or_none(payload.get("evidence")) or field_value
        crop_definition = crop_definitions.get(source_crop) if source_crop else None

        evidence = DocumentEvidence(
            document_id=ddt_document.id,
            document_page_id=crop_definition["page_id"] if crop_definition else None,
            acquisition_row_id=row.id,
            blocco="ddt",
            tipo_evidenza="crop",
            bbox=crop_definition["bbox"] if crop_definition else None,
            testo_grezzo=evidence_text,
            storage_key_derivato=crop_definition["storage_key"] if crop_definition else None,
            metodo_estrazione="chatgpt",
            mascherato=True,
            confidenza=0.72,
            utente_creazione_id=actor_id,
        )
        db.add(evidence)
        db.flush()

        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="ddt",
            campo=field_name,
            valore_grezzo=evidence_text,
            valore_standardizzato=field_value,
            valore_finale=field_value,
            stato="proposto",
            document_evidence_id=evidence.id,
            metodo_lettura="chatgpt",
            fonte_documentale="ddt",
            confidenza=0.72,
            actor_id=actor_id,
        )
        extracted_count += 1

    _sync_row_from_ddt_values(db, row)

    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="ddt",
        azione="campi_core_vision_rilevati" if extracted_count else "campi_core_vision_non_rilevati",
        user_id=actor_id,
        nota_breve=str(extracted_count) if extracted_count else None,
    )
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def run_ai_intervention(
    db: Session,
    row: AcquisitionRow,
    *,
    actor_id: int,
    openai_api_key: str,
) -> AcquisitionRowDetailResponse:
    supplier_key = _resolve_row_supplier_key(row)
    if not _supplier_supports_ai_vision_pipeline(supplier_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intervento AI disponibile solo per i fornitori con pipeline AI attiva in questa fase",
        )
    if row.document_ddt_id is None and row.document_certificato_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Acquisition row has no DDT or certificate document",
        )

    extract_core_fields(db=db, row=row, actor_id=actor_id)
    refreshed_row = get_acquisition_row(db, row.id)

    if refreshed_row.document_ddt_id is not None:
        extract_ddt_fields_with_vision(
            db=db,
            row=refreshed_row,
            actor_id=actor_id,
            openai_api_key=openai_api_key,
        )
        refreshed_row = get_acquisition_row(db, row.id)

    if refreshed_row.document_certificato_id is not None:
        _extract_certificate_core_fields_with_vision(
            db=db,
            row=refreshed_row,
            actor_id=actor_id,
            openai_api_key=openai_api_key,
        )
        refreshed_row = get_acquisition_row(db, row.id)
        detect_chemistry(
            db=db,
            row=refreshed_row,
            actor_id=actor_id,
            openai_api_key=openai_api_key,
        )
        refreshed_row = get_acquisition_row(db, row.id)
        detect_properties(
            db=db,
            row=refreshed_row,
            actor_id=actor_id,
            openai_api_key=openai_api_key,
        )
        refreshed_row = get_acquisition_row(db, row.id)
        detect_standard_notes(db=db, row=refreshed_row, actor_id=actor_id, openai_api_key=openai_api_key)
        refreshed_row = get_acquisition_row(db, row.id)

    _record_history_event(
        db=db,
        acquisition_row_id=refreshed_row.id,
        blocco="workflow",
        azione="intervento_ai_eseguito",
        user_id=actor_id,
    )
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def _resolve_row_supplier_key(row: AcquisitionRow) -> str | None:
    template = resolve_supplier_template(
        row.supplier.ragione_sociale if row.supplier is not None else None,
        row.fornitore_raw,
        row.ddt_document.supplier.ragione_sociale if row.ddt_document and row.ddt_document.supplier else None,
        row.certificate_document.supplier.ragione_sociale if row.certificate_document and row.certificate_document.supplier else None,
    )
    return template.supplier_key if template is not None else None


def _process_certificate_side_blocks(
    db: Session,
    *,
    row: AcquisitionRow,
    actor_id: int,
    openai_api_key: str | None,
    use_ai_intervention: bool,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
) -> AcquisitionRow:
    current_row = get_acquisition_row(db, row.id)
    if current_row.document_certificato_id is None:
        return current_row

    supplier_key = _resolve_row_supplier_key(current_row)
    if use_ai_intervention and openai_api_key and _supplier_supports_ai_vision_pipeline(supplier_key):
        payload = _get_supplier_certificate_ai_payload(
            db=db,
            supplier_key=supplier_key,
            certificate_document=get_document(db, current_row.document_certificato_id),
            openai_api_key=openai_api_key,
            certificate_ai_cache=certificate_ai_cache,
        )
        _apply_supplier_certificate_ai_payload(
            db=db,
            row=current_row,
            payload=payload,
            actor_id=actor_id,
        )
        current_row = get_acquisition_row(db, current_row.id)
        return current_row

    if not _block_has_confirmed_values(db, current_row.id, "chimica"):
        detect_chemistry(db=db, row=current_row, actor_id=actor_id, openai_api_key=openai_api_key)
        current_row = get_acquisition_row(db, row.id)

    if not _block_has_confirmed_values(db, current_row.id, "proprieta"):
        detect_properties(db=db, row=current_row, actor_id=actor_id, openai_api_key=openai_api_key)
        current_row = get_acquisition_row(db, row.id)

    if not _block_has_confirmed_values(db, current_row.id, "note"):
        detect_standard_notes(db=db, row=current_row, actor_id=actor_id, openai_api_key=openai_api_key)
        current_row = get_acquisition_row(db, row.id)

    return current_row


def _extract_certificate_core_fields_with_vision(
    db: Session,
    row: AcquisitionRow,
    *,
    actor_id: int,
    openai_api_key: str,
) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    _reopen_row_if_validated(db, row, actor_id=actor_id, reason="certificato_vision")
    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)
    certificate_document = _ensure_document_page_images(db, certificate_document)

    image_pages = [page for page in certificate_document.pages if page.immagine_pagina_storage_key]
    if not image_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate has no image pages available for vision",
        )

    supplier_key = _resolve_row_supplier_key(row)
    field_names = [
        "numero_certificato_certificato",
        "articolo_certificato",
        "codice_cliente_certificato",
        "ordine_cliente_certificato",
        "lega_certificato",
        "diametro_certificato",
        "colata_certificato",
        "peso_certificato",
    ]
    crop_definitions: dict[str, dict[str, str | int]]
    if _supplier_supports_ai_vision_pipeline(supplier_key):
        crop_definitions = _build_certificate_safe_crops(image_pages, supplier_key=supplier_key)
        payload = _get_supplier_certificate_ai_payload(
            db=db,
            supplier_key=supplier_key,
            certificate_document=certificate_document,
            openai_api_key=openai_api_key,
            certificate_ai_cache=None,
        )
        extracted = cast(dict[str, dict[str, str | None]], payload.get("core_fields") or {})
    else:
        crop_definitions = _build_certificate_safe_crops(image_pages, supplier_key=supplier_key)
        if not crop_definitions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to prepare certificate image crops for vision",
            )
        extracted = _extract_certificate_fields_from_openai(
            crop_definitions,
            openai_api_key=openai_api_key,
            field_names=field_names,
            instruction=(
                "Leggi i ritagli del blocco identita e dei blocchi tecnici vicini di un certificato materiale. "
                "Estrai solo i campi core chiaramente leggibili senza inventare. "
                "I codici articolo possono apparire come 14BT..., i codici cliente come token tecnici che iniziano con A, "
                "l'ordine cliente puo apparire come numero con data o data con numero."
            ),
        )
    extracted_count = 0

    for field_name, payload in extracted.items():
        field_value = _string_or_none(payload.get("value"))
        if field_value is None:
            if _is_revisable_chatgpt_match_value(row, field_name):
                _upsert_read_value_model(
                    db=db,
                    acquisition_row_id=row.id,
                    blocco="match",
                    campo=field_name,
                    valore_grezzo=None,
                    valore_standardizzato=None,
                    valore_finale=None,
                    stato="proposto",
                    document_evidence_id=None,
                    metodo_lettura="chatgpt",
                    fonte_documentale="certificato",
                    confidenza=None,
                    actor_id=actor_id,
                )
            continue
        if _has_stable_value_protected_from_ai(row, "match", field_name):
            continue
        source_crop = payload.get("source_crop")
        evidence_text = _string_or_none(payload.get("evidence")) or field_value
        crop_definition = crop_definitions.get(source_crop) if source_crop else None

        evidence = DocumentEvidence(
            document_id=certificate_document.id,
            document_page_id=crop_definition["page_id"] if crop_definition else None,
            acquisition_row_id=row.id,
            blocco="match",
            tipo_evidenza="crop",
            bbox=crop_definition["bbox"] if crop_definition else None,
            testo_grezzo=evidence_text,
            storage_key_derivato=crop_definition["storage_key"] if crop_definition else None,
            metodo_estrazione="chatgpt",
            mascherato=True,
            confidenza=0.72,
            utente_creazione_id=actor_id,
        )
        db.add(evidence)
        db.flush()

        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="match",
            campo=field_name,
            valore_grezzo=evidence_text,
            valore_standardizzato=field_value,
            valore_finale=field_value,
            stato="proposto",
            document_evidence_id=evidence.id,
            metodo_lettura="chatgpt",
            fonte_documentale="certificato",
            confidenza=0.72,
            actor_id=actor_id,
        )
        extracted_count += 1

    _sync_row_from_match_values(db, row)
    _sync_row_statuses(db, row)
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="match",
        azione="campi_core_certificato_vision_rilevati" if extracted_count else "campi_core_certificato_vision_non_rilevati",
        user_id=actor_id,
        nota_breve=str(extracted_count) if extracted_count else None,
    )
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def _get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


def _get_document_of_type(db: Session, document_id: int, expected_type: str) -> Document:
    document = get_document(db, document_id)
    if document.tipo_documento != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document {document_id} is not of type {expected_type}",
        )
    return document


def _resolve_supplier_id(
    db: Session,
    explicit_supplier_id: int | None,
    ddt_document: Document | None,
    certificate_document: Document | None,
) -> int | None:
    supplier_ids = {
        supplier_id
        for supplier_id in {
            explicit_supplier_id,
            ddt_document.fornitore_id if ddt_document is not None else None,
            certificate_document.fornitore_id if certificate_document else None,
        }
        if supplier_id is not None
    }
    if explicit_supplier_id is not None:
        _get_supplier(db, explicit_supplier_id)
    if len(supplier_ids) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier mismatch across row documents")
    return next(iter(supplier_ids), None)


def _normalize_upload_batch_id(value: str | None) -> str | None:
    normalized = _string_or_none(value)
    if normalized is None:
        return None
    return normalized[:64]


def _find_temporary_duplicate_document_for_user(db: Session, *, actor_id: int, file_hash: str) -> Document | None:
    if not file_hash:
        return None
    return (
        db.query(Document)
        .options(joinedload(Document.supplier))
        .filter(
            Document.utente_upload_id == actor_id,
            Document.stato_upload == "temporaneo",
            Document.hash_file == file_hash,
        )
        .order_by(Document.data_upload.desc(), Document.id.desc())
        .first()
    )


def _find_persistent_duplicate_document(db: Session, *, file_hash: str) -> Document | None:
    if not file_hash:
        return None
    return (
        db.query(Document)
        .options(joinedload(Document.supplier))
        .filter(
            Document.stato_upload == "persistente",
            Document.hash_file == file_hash,
        )
        .order_by(Document.data_upload.desc(), Document.id.desc())
        .first()
    )


def _get_latest_temporary_upload_batch_id(db: Session, *, actor_id: int) -> str | None:
    document = (
        db.query(Document)
        .filter(
            Document.utente_upload_id == actor_id,
            Document.stato_upload == "temporaneo",
            Document.upload_batch_id.isnot(None),
        )
        .order_by(Document.data_upload.desc(), Document.id.desc())
        .first()
    )
    if document is None:
        return None
    return _normalize_upload_batch_id(document.upload_batch_id)


def _delete_storage_key_if_present(storage_key: str | None) -> None:
    resolved_key = _string_or_none(storage_key)
    if resolved_key is None:
        return
    path = _resolve_storage_path(resolved_key)
    if path.exists():
        path.unlink()


def _delete_temporary_upload_batch(db: Session, *, actor_id: int, upload_batch_id: str) -> None:
    documents = (
        db.query(Document)
        .options(joinedload(Document.pages), joinedload(Document.evidences))
        .filter(
            Document.utente_upload_id == actor_id,
            Document.stato_upload == "temporaneo",
            Document.upload_batch_id == upload_batch_id,
        )
        .all()
    )
    if not documents:
        return

    for document in documents:
        if document.rows_as_ddt or document.rows_as_certificate or document.matches or document.match_candidates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot discard a batch that is already in use")
        page_ids = [page.id for page in document.pages]
        for evidence in document.evidences:
            _delete_storage_key_if_present(evidence.storage_key_derivato)
            db.delete(evidence)
        if page_ids:
            page_evidences = db.query(DocumentEvidence).filter(DocumentEvidence.document_page_id.in_(page_ids)).all()
            for evidence in page_evidences:
                _delete_storage_key_if_present(evidence.storage_key_derivato)
                db.delete(evidence)
        for page in document.pages:
            _delete_storage_key_if_present(page.immagine_pagina_storage_key)
            db.delete(page)
        _delete_storage_key_if_present(document.storage_key)
        db.delete(document)

    db.commit()


def _delete_temporary_documents_by_ids(db: Session, *, actor_id: int, document_ids: list[int]) -> None:
    normalized_ids = _normalize_document_id_list(document_ids)
    if not normalized_ids:
        return
    documents = (
        db.query(Document)
        .options(joinedload(Document.pages), joinedload(Document.evidences))
        .filter(
            Document.utente_upload_id == actor_id,
            Document.stato_upload == "temporaneo",
            Document.id.in_(normalized_ids),
        )
        .all()
    )
    if not documents:
        return

    for document in documents:
        if document.rows_as_ddt or document.rows_as_certificate or document.matches or document.match_candidates:
            continue
        page_ids = [page.id for page in document.pages]
        for evidence in document.evidences:
            _delete_storage_key_if_present(evidence.storage_key_derivato)
            db.delete(evidence)
        if page_ids:
            page_evidences = db.query(DocumentEvidence).filter(DocumentEvidence.document_page_id.in_(page_ids)).all()
            for evidence in page_evidences:
                _delete_storage_key_if_present(evidence.storage_key_derivato)
                db.delete(evidence)
        for page in document.pages:
            _delete_storage_key_if_present(page.immagine_pagina_storage_key)
            db.delete(page)
        _delete_storage_key_if_present(document.storage_key)
        db.delete(document)

    db.commit()


def _set_documents_processing_state(db: Session, document_ids: list[int], *, stato_elaborazione: str) -> None:
    normalized_ids = _normalize_document_id_list(document_ids)
    if not normalized_ids:
        return
    documents = db.query(Document).filter(Document.id.in_(normalized_ids)).all()
    changed = False
    for document in documents:
        if document.stato_elaborazione == stato_elaborazione:
            continue
        document.stato_elaborazione = stato_elaborazione
        db.add(document)
        changed = True
    if changed:
        db.commit()


def _promote_documents_to_persistent(db: Session, document_ids: list[int]) -> None:
    normalized_ids = _normalize_document_id_list(document_ids)
    if not normalized_ids:
        return
    documents = db.query(Document).filter(Document.id.in_(normalized_ids)).all()
    changed = False
    for document in documents:
        if document.stato_upload == "persistente" and document.upload_batch_id is None and document.scadenza_batch is None:
            continue
        document.stato_upload = "persistente"
        document.upload_batch_id = None
        document.scadenza_batch = None
        db.add(document)
        changed = True
    if changed:
        db.commit()


def _save_run(
    db: Session,
    run: AutonomousProcessingRun,
    **updates: object,
) -> AutonomousProcessingRun:
    for field_name, value in updates.items():
        setattr(run, field_name, value)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _normalize_document_id_list(document_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for document_id in document_ids:
        if document_id in seen:
            continue
        seen.add(document_id)
        normalized.append(document_id)
    return normalized


def _ensure_documents_type(db: Session, document_ids: list[int], expected_type: str) -> None:
    for document_id in document_ids:
        _get_document_of_type(db, document_id, expected_type)


def _resolve_certificate_documents_for_automation(
    db: Session,
    *,
    ddt_documents: list[Document],
    explicit_certificate_document_ids: list[int],
) -> list[Document]:
    documents_by_id: dict[int, Document] = {}

    for document_id in explicit_certificate_document_ids:
        document = _get_document_of_type(db, document_id, "certificato")
        documents_by_id[document.id] = document

    if not ddt_documents and explicit_certificate_document_ids:
        return list(documents_by_id.values())

    supplier_ids = {document.fornitore_id for document in ddt_documents if document.fornitore_id is not None}
    acquisition_query = (
        db.query(AcquisitionRow.document_certificato_id)
        .filter(AcquisitionRow.document_certificato_id.is_not(None))
    )
    if supplier_ids:
        acquisition_query = acquisition_query.filter(AcquisitionRow.fornitore_id.in_(supplier_ids))

    acquisition_certificate_ids = sorted(
        {
            int(document_id)
            for (document_id,) in acquisition_query.distinct().all()
            if document_id is not None
        }
    )
    for document_id in acquisition_certificate_ids:
        document = _get_document_of_type(db, document_id, "certificato")
        documents_by_id.setdefault(document.id, document)

    return list(documents_by_id.values())


def _ensure_autonomous_rows(
    db: Session,
    *,
    ddt_document: Document,
    actor_id: int,
    actor_email: str,
) -> tuple[list[AcquisitionRow], int]:
    existing_rows = (
        db.query(AcquisitionRow)
        .filter(AcquisitionRow.document_ddt_id == ddt_document.id)
        .order_by(AcquisitionRow.id.asc())
        .all()
    )
    if existing_rows:
        return [get_acquisition_row(db, row.id) for row in existing_rows], 0

    document = prepare_document_for_reader(db, ddt_document)
    plan = build_document_row_split_plan(document)
    if plan.row_split_candidates:
        split_result = create_rows_from_document_split_plan(
            db=db,
            document=document,
            actor_id=actor_id,
            actor_email=actor_email,
        )
        return [get_acquisition_row(db, item.id) for item in split_result.created_rows], split_result.created_count

    supplier_name = ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None
    created = create_acquisition_row(
        db=db,
        payload=AcquisitionRowCreateRequest(
            document_ddt_id=ddt_document.id,
            fornitore_id=ddt_document.fornitore_id,
            fornitore_raw=supplier_name,
        ),
        actor_id=actor_id,
        actor_email=actor_email,
    )
    return [get_acquisition_row(db, created.id)], 1


def _ensure_autonomous_rows_with_ai(
    db: Session,
    *,
    ddt_document: Document,
    actor_id: int,
    actor_email: str,
    openai_api_key: str,
) -> tuple[list[AcquisitionRow], int]:
    existing_rows = (
        db.query(AcquisitionRow)
        .filter(AcquisitionRow.document_ddt_id == ddt_document.id)
        .order_by(AcquisitionRow.id.asc())
        .all()
    )
    if existing_rows:
        return [get_acquisition_row(db, row.id) for row in existing_rows], 0

    template = resolve_supplier_template(
        ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None,
        ddt_document.nome_file_originale,
    )
    supplier_key = template.supplier_key if template is not None else None
    if not _supplier_supports_ai_vision_pipeline(supplier_key):
        return _ensure_autonomous_rows(
            db=db,
            ddt_document=ddt_document,
            actor_id=actor_id,
            actor_email=actor_email,
        )

    ddt_document = _ensure_document_page_images(db, _index_document_from_path(db, ddt_document) if not ddt_document.pages else ddt_document)
    ai_candidates = _extract_supplier_ddt_row_groups_with_vision(
        db=db,
        supplier_key=supplier_key,
        ddt_document=ddt_document,
        openai_api_key=openai_api_key,
    )
    if not ai_candidates:
        return [], 0

    existing_rows_all = (
        db.query(AcquisitionRow)
        .filter(AcquisitionRow.fornitore_id == ddt_document.fornitore_id)
        .order_by(AcquisitionRow.id.asc())
        .all()
    )
    existing_signatures = {
        _split_candidate_signature_from_row(row): row
        for row in existing_rows_all
        if row.document_ddt_id is not None
    }

    created_rows: list[AcquisitionRow] = []
    fallback_ddt = next((candidate.ddt_number for candidate in ai_candidates if _string_or_none(candidate.ddt_number)), None)
    for candidate in ai_candidates:
        candidate_signature = _split_candidate_signature_from_candidate(
            document=ddt_document,
            candidate=candidate,
            fallback_ddt=fallback_ddt,
        )
        existing_row = existing_signatures.get(candidate_signature)
        if existing_row is not None:
            continue

        certificate_first_row = _find_existing_certificate_first_row_for_split_candidate(
            db=db,
            rows=existing_rows_all,
            document=ddt_document,
            candidate=candidate,
            fallback_ddt=fallback_ddt,
            supplier_key=supplier_key,
        )
        if certificate_first_row is not None:
            certificate_first_row.document_ddt_id = ddt_document.id
            certificate_first_row.fornitore_id = ddt_document.fornitore_id
            certificate_first_row.fornitore_raw = ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None
            certificate_first_row.ddt = candidate.ddt_number or fallback_ddt
            certificate_first_row.ordine = candidate.customer_order_no
            certificate_first_row.lega_base = candidate.lega or certificate_first_row.lega_base
            certificate_first_row.diametro = candidate.diametro or certificate_first_row.diametro
            certificate_first_row.colata = candidate.colata or certificate_first_row.colata
            certificate_first_row.peso = candidate.peso_netto or certificate_first_row.peso
            if candidate.cdq:
                certificate_first_row.cdq = candidate.cdq
            db.add(certificate_first_row)
            db.commit()
            db.refresh(certificate_first_row)
            _persist_split_candidate_values(db=db, row=certificate_first_row, candidate=candidate, actor_id=actor_id)
            _apply_supplier_ai_candidate_to_row(
                db=db,
                row=certificate_first_row,
                ai_candidate=candidate,
                actor_id=actor_id,
                document_id=ddt_document.id,
            )
            db.commit()
            refreshed = get_acquisition_row(db, certificate_first_row.id)
            existing_signatures[candidate_signature] = refreshed
            existing_rows_all.append(refreshed)
            created_rows.append(refreshed)
            continue

        created_row = create_acquisition_row(
            db=db,
            payload=AcquisitionRowCreateRequest(
                document_ddt_id=ddt_document.id,
                fornitore_id=ddt_document.fornitore_id,
                fornitore_raw=ddt_document.supplier.ragione_sociale if ddt_document.supplier is not None else None,
                cdq=candidate.cdq,
                lega_base=candidate.lega,
                diametro=candidate.diametro,
                colata=candidate.colata,
                ddt=candidate.ddt_number or fallback_ddt,
                peso=candidate.peso_netto,
                ordine=candidate.customer_order_no,
                stato_tecnico="rosso",
                stato_workflow="nuova",
                priorita_operativa="media",
            ),
            actor_id=actor_id,
            actor_email=actor_email,
        )
        row = get_acquisition_row(db, created_row.id)
        _persist_split_candidate_values(db=db, row=row, candidate=candidate, actor_id=actor_id)
        _apply_supplier_ai_candidate_to_row(
            db=db,
            row=row,
            ai_candidate=candidate,
            actor_id=actor_id,
            document_id=ddt_document.id,
        )
        db.commit()
        refreshed = get_acquisition_row(db, row.id)
        existing_signatures[candidate_signature] = refreshed
        existing_rows_all.append(refreshed)
        created_rows.append(refreshed)

    log_service.record(
        "acquisition",
        f"AI rows created from document {ddt_document.id}: {len(created_rows)}",
        actor_email,
    )
    return created_rows, len(created_rows)


def _ensure_certificate_first_rows(
    db: Session,
    *,
    certificate_documents: list[Document],
    actor_id: int,
    actor_email: str,
    openai_api_key: str | None,
    use_ai_intervention: bool,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
) -> int:
    created_count = 0
    for certificate_document in certificate_documents:
        existing_for_document = (
            db.query(AcquisitionRow)
            .filter(AcquisitionRow.document_certificato_id == certificate_document.id)
            .first()
        )
        if existing_for_document is not None:
            continue

        certificate_document = prepare_document_for_reader(db, certificate_document)
        template = resolve_supplier_template(
            certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
            certificate_document.nome_file_originale,
        )
        supplier_key = template.supplier_key if template is not None else None
        if supplier_key not in {"aluminium_bozen", "impol"}:
            continue

        if use_ai_intervention and openai_api_key:
            payload = _get_supplier_certificate_ai_payload(
                db=db,
                supplier_key=supplier_key,
                certificate_document=certificate_document,
                openai_api_key=openai_api_key,
                certificate_ai_cache=certificate_ai_cache,
            )
            ai_match_values = cast(dict[str, str | None], payload.get("match_values") or {})
            ai_supplier_fields = cast(dict[str, str | None], payload.get("supplier_fields") or {})
            certificate_number = _string_or_none(ai_match_values.get("numero_certificato_certificato"))
            certificate_alloy = _string_or_none(ai_match_values.get("lega_certificato"))
            certificate_diameter = _string_or_none(ai_match_values.get("diametro_certificato"))
            certificate_cast = _string_or_none(ai_match_values.get("colata_certificato"))
            certificate_weight = _string_or_none(ai_match_values.get("peso_certificato"))
            certificate_article = (
                _string_or_none(ai_supplier_fields.get("article"))
                or _string_or_none(ai_supplier_fields.get("product_code"))
                or _string_or_none(ai_match_values.get("articolo_certificato"))
            )
            certificate_customer_code = _string_or_none(ai_supplier_fields.get("customer_code"))
            certificate_customer_order = (
                _string_or_none(ai_supplier_fields.get("customer_order_normalized"))
                or _string_or_none(ai_supplier_fields.get("customer_order_no"))
                or _string_or_none(ai_match_values.get("ordine_cliente_certificato"))
            )
            certificate_packing_list = _string_or_none(ai_supplier_fields.get("packing_list_no"))
            certificate_supplier_order = _string_or_none(ai_supplier_fields.get("supplier_order_no"))
        else:
            certificate_matches = reader_detect_certificate_core_matches(
                certificate_document.pages,
                supplier_key=supplier_key,
            )
            if not certificate_matches:
                continue
            supplier_fields = reader_extract_supplier_match_fields(
                certificate_document.pages,
                supplier_key,
                "certificato",
            )
            certificate_number = _string_or_none(cast(dict[str, object], certificate_matches.get("numero_certificato_certificato") or {}).get("final"))
            certificate_alloy = _string_or_none(cast(dict[str, object], certificate_matches.get("lega_certificato") or {}).get("final"))
            certificate_diameter = _string_or_none(cast(dict[str, object], certificate_matches.get("diametro_certificato") or {}).get("final"))
            certificate_cast = _string_or_none(cast(dict[str, object], certificate_matches.get("colata_certificato") or {}).get("final"))
            certificate_weight = _string_or_none(cast(dict[str, object], certificate_matches.get("peso_certificato") or {}).get("final"))
            certificate_article = _string_or_none(supplier_fields.get("article")) or _string_or_none(supplier_fields.get("product_code"))
            certificate_customer_code = _string_or_none(supplier_fields.get("customer_code"))
            certificate_customer_order = _string_or_none(supplier_fields.get("customer_order_normalized")) or _string_or_none(supplier_fields.get("customer_order_no"))
            certificate_packing_list = _string_or_none(supplier_fields.get("packing_list_no"))
            certificate_supplier_order = _string_or_none(supplier_fields.get("supplier_order_no"))

        if not any((certificate_number, certificate_article, certificate_customer_order, certificate_cast, certificate_packing_list, certificate_supplier_order)):
            continue
        certificate_signature = _certificate_first_signature(
            fornitore_id=certificate_document.fornitore_id,
            cdq=certificate_number,
            ordine=certificate_customer_order,
            article=certificate_article,
            customer_code=certificate_customer_code,
            lega=certificate_alloy,
            diametro=certificate_diameter,
            colata=certificate_cast,
            peso=certificate_weight,
        )
        linked_row = None
        if supplier_key == "aluminium_bozen":
            linked_row = _find_existing_aluminium_bozen_row_for_certificate(
                db=db,
                supplier_id=certificate_document.fornitore_id,
                certificate_number=certificate_number,
                article=certificate_article,
                customer_code=certificate_customer_code,
                customer_order=certificate_customer_order,
                alloy=certificate_alloy,
                diameter=certificate_diameter,
                cast=certificate_cast,
                weight=certificate_weight,
            )
        if linked_row is not None:
            if linked_row.document_certificato_id is None:
                linked_row.document_certificato_id = certificate_document.id
                _sync_row_cdq_from_certificate_document(db, linked_row, certificate_document)
                _sync_row_statuses(db, linked_row)
                db.commit()
                if not (use_ai_intervention and openai_api_key):
                    extract_core_fields(db=db, row=get_acquisition_row(db, linked_row.id), actor_id=actor_id)
                linked_row = _process_certificate_side_blocks(
                    db=db,
                    row=get_acquisition_row(db, linked_row.id),
                    actor_id=actor_id,
                    openai_api_key=openai_api_key,
                    use_ai_intervention=use_ai_intervention,
                    certificate_ai_cache=certificate_ai_cache,
                )
            continue
        duplicate_row = next(
            (
                row
                for row in db.query(AcquisitionRow)
                .filter(
                    AcquisitionRow.document_ddt_id.is_(None),
                    AcquisitionRow.fornitore_id == certificate_document.fornitore_id,
                )
                .all()
                if _certificate_first_signature_from_row(row) == certificate_signature
            ),
            None,
        )
        if duplicate_row is not None:
            if duplicate_row.document_certificato_id is None:
                duplicate_row.document_certificato_id = certificate_document.id
                _sync_row_cdq_from_certificate_document(db, duplicate_row, certificate_document)
                _sync_row_statuses(db, duplicate_row)
                db.commit()
                if not (use_ai_intervention and openai_api_key):
                    extract_core_fields(db=db, row=get_acquisition_row(db, duplicate_row.id), actor_id=actor_id)
                duplicate_row = _process_certificate_side_blocks(
                    db=db,
                    row=get_acquisition_row(db, duplicate_row.id),
                    actor_id=actor_id,
                    openai_api_key=openai_api_key,
                    use_ai_intervention=use_ai_intervention,
                    certificate_ai_cache=certificate_ai_cache,
                )
            continue

        created_row = create_acquisition_row(
            db=db,
            payload=AcquisitionRowCreateRequest(
                document_ddt_id=None,
                document_certificato_id=certificate_document.id,
                fornitore_id=certificate_document.fornitore_id,
                fornitore_raw=certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
                cdq=certificate_number,
                lega_base=certificate_alloy,
                diametro=certificate_diameter,
                colata=certificate_cast,
                peso=certificate_weight,
                ordine=None,
                note_documento="Certificato caricato in attesa del DDT",
                stato_tecnico="rosso",
                stato_workflow="nuova",
                priorita_operativa="media",
            ),
            actor_id=actor_id,
            actor_email=actor_email,
        )
        created_row_model = get_acquisition_row(db, created_row.id)
        if not (use_ai_intervention and openai_api_key):
            extract_core_fields(db=db, row=created_row_model, actor_id=actor_id)
        created_row_model = _process_certificate_side_blocks(
            db=db,
            row=get_acquisition_row(db, created_row.id),
            actor_id=actor_id,
            openai_api_key=openai_api_key,
            use_ai_intervention=use_ai_intervention,
            certificate_ai_cache=certificate_ai_cache,
        )
        created_count += 1

    return created_count


def _find_existing_aluminium_bozen_row_for_certificate(
    db: Session,
    *,
    supplier_id: int | None,
    certificate_number: str | None,
    article: str | None,
    customer_code: str | None,
    customer_order: str | None,
    alloy: str | None,
    diameter: str | None,
    cast: str | None,
    weight: str | None,
) -> AcquisitionRow | None:
    if supplier_id is None:
        return None

    rows = (
        db.query(AcquisitionRow)
        .filter(AcquisitionRow.fornitore_id == supplier_id)
        .order_by(AcquisitionRow.id.asc())
        .all()
    )

    normalized_cdq = reader_normalize_match_token(certificate_number)
    normalized_article = reader_normalize_match_token(article)
    normalized_customer_code = reader_normalize_match_token(customer_code)
    normalized_customer_order = reader_normalize_match_token(customer_order)
    normalized_cast = reader_normalize_match_token(cast)
    normalized_alloy = reader_normalize_match_token(alloy)
    normalized_diameter = reader_normalize_match_token(diameter)
    normalized_weight = reader_normalize_match_token(weight)

    def score(row: AcquisitionRow) -> int:
        total = 0
        row_identity_fields = _certificate_first_row_identity_fields(row)
        row_cdq = reader_normalize_match_token(row.cdq)
        row_article = reader_normalize_match_token(row_identity_fields.get("article"))
        row_customer_code = reader_normalize_match_token(row_identity_fields.get("customer_code"))
        row_customer_order = reader_normalize_match_token(row_identity_fields.get("customer_order"))
        row_cast = reader_normalize_match_token(row.colata)
        row_alloy = reader_normalize_match_token(row.lega_base)
        row_diameter = reader_normalize_match_token(row.diametro)
        row_weight = reader_normalize_match_token(row.peso)

        if normalized_cdq:
            if row_cdq and row_cdq != normalized_cdq:
                return -1
            if row_cdq == normalized_cdq:
                total += 200
        if normalized_article and row_article:
            if row_article != normalized_article:
                return -1
            total += 80
        if normalized_customer_code and row_customer_code:
            if row_customer_code != normalized_customer_code:
                return -1
            total += 60
        if normalized_customer_order and row_customer_order:
            if row_customer_order != normalized_customer_order:
                return -1
            total += 60
        if normalized_cast and row_cast:
            if row_cast != normalized_cast:
                return -1
            total += 80
        if normalized_alloy and row_alloy:
            if row_alloy != normalized_alloy:
                return -1
            total += 40
        if normalized_diameter and row_diameter:
            if row_diameter != normalized_diameter:
                return -1
            total += 40
        if normalized_weight and row_weight:
            if row_weight != normalized_weight:
                return -1
            total += 20
        return total

    scored = [(score(row), row) for row in rows]
    scored = [item for item in scored if item[0] >= 180]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return scored[0][1]


def _certificate_first_signature(
    *,
    fornitore_id: int | None,
    cdq: str | None,
    ordine: str | None,
    article: str | None,
    customer_code: str | None,
    lega: str | None,
    diametro: str | None,
    colata: str | None,
    peso: str | None,
) -> tuple[str | int | None, ...]:
    return (
        fornitore_id,
        reader_normalize_match_token(cdq),
        reader_normalize_match_token(ordine),
        reader_normalize_match_token(article),
        reader_normalize_match_token(customer_code),
        reader_normalize_match_token(lega),
        reader_normalize_match_token(diametro),
        reader_normalize_match_token(colata),
        reader_normalize_match_token(peso),
    )


def _certificate_first_signature_from_row(row: AcquisitionRow) -> tuple[str | int | None, ...]:
    identity_fields = _certificate_first_row_identity_fields(row)
    return _certificate_first_signature(
        fornitore_id=row.fornitore_id,
        cdq=row.cdq,
        ordine=identity_fields.get("customer_order"),
        article=identity_fields.get("article"),
        customer_code=identity_fields.get("customer_code"),
        lega=row.lega_base or row.lega_designazione or row.variante_lega,
        diametro=row.diametro,
        colata=row.colata,
        peso=row.peso,
    )


def _certificate_first_row_identity_fields(row: AcquisitionRow) -> dict[str, str | None]:
    ddt_values = {
        value.campo: _final_value_for_row(value)
        for value in row.values
        if value.blocco == "ddt"
    }
    match_values = {
        value.campo: _final_value_for_row(value)
        for value in row.values
        if value.blocco == "match"
    }
    return {
        "article": _string_or_none(ddt_values.get("article_code")) or _string_or_none(match_values.get("articolo_certificato")),
        "customer_code": _string_or_none(ddt_values.get("customer_code")) or _string_or_none(match_values.get("codice_cliente_certificato")),
        "customer_order": _string_or_none(ddt_values.get("customer_order_no")) or _string_or_none(match_values.get("ordine_cliente_certificato")),
    }


def _row_needs_ddt_vision(db: Session, row: AcquisitionRow) -> bool:
    values = db.query(ReadValue).filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt").all()
    summary = _compute_ddt_field_summary_from_values(values)
    required_missing = [field for field in summary["missing"] if field in _ddt_required_fields()]
    return bool(required_missing)


def _block_has_values(db: Session, row_id: int, block: str) -> bool:
    values = db.query(ReadValue).filter(ReadValue.acquisition_row_id == row_id, ReadValue.blocco == block).all()
    if block in {"chimica", "proprieta"}:
        return any(_read_value_has_payload(value) for value in values)
    return bool(values)


def _block_has_confirmed_values(db: Session, row_id: int, block: str) -> bool:
    values = (
        db.query(ReadValue)
        .filter(
            ReadValue.acquisition_row_id == row_id,
            ReadValue.blocco == block,
            ReadValue.stato == "confermato",
        )
        .all()
    )
    if block in {"chimica", "proprieta"}:
        return any(_read_value_has_payload(value) for value in values)
    return bool(values)


def _auto_propose_certificate_match(
    db: Session,
    *,
    row: AcquisitionRow,
    certificate_documents: list[Document],
    actor_id: int,
    openai_api_key: str | None = None,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
    ai_only_mode: bool = False,
) -> bool:
    if row.certificate_match is not None or row.document_certificato_id is not None:
        return False

    ddt_values = {
        value.campo: _final_value_for_row(value)
        for value in (
            db.query(ReadValue)
            .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt")
            .all()
        )
    }
    ddt_certificate_number = ddt_values.get("numero_certificato_ddt") or row.cdq
    scored_candidates: list[dict[str, object]] = []
    for certificate_document in certificate_documents:
        candidate = _score_certificate_candidate(
            db=db,
            row=row,
            certificate_document=certificate_document,
            ddt_certificate_number=ddt_certificate_number,
            row_ddt_values=ddt_values,
            certificate_ai_cache=certificate_ai_cache,
            ai_only_mode=ai_only_mode,
        )
        if candidate is not None:
            scored_candidates.append(candidate)
    if not scored_candidates:
        return False

    scored_candidates.sort(key=lambda item: (-int(item["score"]), int(item["document"].id)))
    best_candidate = scored_candidates[0]
    second_score = int(scored_candidates[1]["score"]) if len(scored_candidates) > 1 else 0
    best_score = int(best_candidate["score"])
    should_propose = (
        best_score >= 80
        or (best_score >= 45 and best_score - second_score >= 20)
        or (len(scored_candidates) == 1 and best_score >= 35)
    )
    if not should_propose:
        return False

    candidates = []
    for rank, candidate in enumerate(scored_candidates[:3], start=1):
        certificate_document = candidate["document"]
        candidates.append(
            MatchCandidateRequest(
                document_certificato_id=certificate_document.id,
                rank=rank,
                motivo_breve=str(candidate["reason"]),
                fonte_proposta="sistema",
                stato="scelto" if rank == 1 else "candidato",
            )
        )

    upsert_match(
        db=db,
        row=row,
        payload=MatchUpsertRequest(
            document_certificato_id=int(best_candidate["document"].id),
            stato="proposto",
            motivo_breve=str(best_candidate["reason"]),
            fonte_proposta="sistema",
            candidates=candidates,
        ),
        actor_id=actor_id,
    )
    return True


def _score_certificate_candidate(
    db: Session,
    *,
    row: AcquisitionRow,
    certificate_document: Document,
    ddt_certificate_number: str | None,
    row_ddt_values: dict[str, str | None],
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
    ai_only_mode: bool = False,
) -> dict[str, object] | None:
    if row.fornitore_id is not None and certificate_document.fornitore_id is not None and row.fornitore_id != certificate_document.fornitore_id:
        return None

    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    template = resolve_supplier_template(
        row.supplier.ragione_sociale if row.supplier is not None else None,
        row.fornitore_raw,
        row.ddt_document.supplier.ragione_sociale if row.ddt_document and row.ddt_document.supplier else None,
        certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
    )

    supplier_key = template.supplier_key if template is not None else None
    matches: dict[str, dict[str, str | None]] = {}
    certificate_number: str | None = None
    certificate_cast: str | None = None
    certificate_weight: str | None = None
    if not (ai_only_mode and _supplier_supports_ai_vision_pipeline(supplier_key)):
        local_matches = reader_detect_certificate_core_matches(certificate_document.pages, supplier_key=supplier_key)
        matches = {
            field_name: {"final": _string_or_none(cast(dict[str, object], payload).get("final"))}
            for field_name, payload in local_matches.items()
        }
        certificate_number = _string_or_none(local_matches.get("numero_certificato_certificato", {}).get("final"))
        certificate_cast = _string_or_none(local_matches.get("colata_certificato", {}).get("final"))
        certificate_weight = _string_or_none(local_matches.get("peso_certificato", {}).get("final"))

    ddt_supplier_fields = (
        {}
        if ai_only_mode and _supplier_supports_ai_vision_pipeline(supplier_key)
        else reader_extract_supplier_match_fields(
            row.ddt_document.pages if row.ddt_document is not None else [],
            template.supplier_key if template is not None else None,
            "ddt",
        )
    )
    if supplier_key == "aluminium_bozen":
        row_supplier_fields = _extract_stable_aluminium_bozen_row_supplier_fields_for_match(
            row=row,
            ddt_values=row_ddt_values,
        )
        ddt_supplier_fields = {
            field_name: field_value
            for field_name, field_value in ddt_supplier_fields.items()
            if field_name not in {"article", "customer_code", "customer_order_normalized"}
        }
    else:
        row_supplier_fields = reader_extract_row_supplier_match_fields(
            row=row,
            ddt_values=row_ddt_values,
            supplier_key=template.supplier_key if template is not None else None,
        )
    ddt_supplier_fields = reader_merge_row_supplier_fields(ddt_supplier_fields, row_supplier_fields)
    certificate_supplier_fields = (
        {}
        if ai_only_mode and _supplier_supports_ai_vision_pipeline(supplier_key)
        else reader_extract_supplier_match_fields(
            certificate_document.pages,
            template.supplier_key if template is not None else None,
            "certificato",
        )
    )

    if _supplier_supports_ai_vision_pipeline(supplier_key) and certificate_ai_cache is not None:
        certificate_ai_fields = cast(dict[str, object], certificate_ai_cache.get(certificate_document.id) or {})
        ai_match_values = cast(dict[str, str | None], certificate_ai_fields.get("match_values") or {})
        ai_supplier_fields = cast(dict[str, str | None], certificate_ai_fields.get("supplier_fields") or {})
        certificate_number = certificate_number or _string_or_none(ai_match_values.get("numero_certificato_certificato"))
        certificate_cast = certificate_cast or _string_or_none(ai_match_values.get("colata_certificato"))
        certificate_weight = certificate_weight or _string_or_none(ai_match_values.get("peso_certificato"))
        if supplier_key == "aluminium_bozen":
            certificate_supplier_fields = {
                "article": _string_or_none(certificate_supplier_fields.get("article")) or _string_or_none(ai_supplier_fields.get("article")),
                "customer_code": _string_or_none(certificate_supplier_fields.get("customer_code")) or _string_or_none(ai_supplier_fields.get("customer_code")),
                "customer_order_normalized": _string_or_none(certificate_supplier_fields.get("customer_order_normalized"))
                or _string_or_none(ai_supplier_fields.get("customer_order_normalized")),
            }
        elif supplier_key == "impol":
            certificate_supplier_fields = {
                "packing_list_no": _string_or_none(certificate_supplier_fields.get("packing_list_no")) or _string_or_none(ai_supplier_fields.get("packing_list_no")),
                "customer_order_no": _string_or_none(certificate_supplier_fields.get("customer_order_no")) or _string_or_none(ai_supplier_fields.get("customer_order_no")),
                "supplier_order_no": _string_or_none(certificate_supplier_fields.get("supplier_order_no")) or _string_or_none(ai_supplier_fields.get("supplier_order_no")),
                "product_code": _string_or_none(certificate_supplier_fields.get("product_code")) or _string_or_none(ai_supplier_fields.get("product_code")),
                "charge": _string_or_none(certificate_supplier_fields.get("charge")) or _string_or_none(ai_supplier_fields.get("charge")),
                "diameter": _string_or_none(certificate_supplier_fields.get("diameter")) or _string_or_none(ai_supplier_fields.get("diameter")),
                "net_weight": _string_or_none(certificate_supplier_fields.get("net_weight")) or _string_or_none(ai_supplier_fields.get("net_weight")),
            }
        if "lega_certificato" not in matches and _string_or_none(ai_match_values.get("lega_certificato")) is not None:
            matches["lega_certificato"] = {"final": _string_or_none(ai_match_values.get("lega_certificato"))}
        if "diametro_certificato" not in matches and _string_or_none(ai_match_values.get("diametro_certificato")) is not None:
            matches["diametro_certificato"] = {"final": _string_or_none(ai_match_values.get("diametro_certificato"))}

    score = 0
    reasons: list[tuple[int, str]] = []

    def add_reason(points: int, label: str) -> None:
        nonlocal score
        score += points
        reasons.append((points, label))

    if reader_normalize_match_token(ddt_certificate_number) and reader_normalize_match_token(ddt_certificate_number) == reader_normalize_match_token(certificate_number):
        add_reason(120, "Numero certificato coerente")
    if reader_normalize_match_token(row.colata) and reader_normalize_match_token(row.colata) == reader_normalize_match_token(certificate_cast):
        add_reason(80, "Colata coerente")
    if reader_weights_are_compatible(row.peso, certificate_weight):
        add_reason(20, "Peso coerente")
    if row.ordine and reader_document_contains_token(certificate_document.pages, row.ordine):
        add_reason(25, "Ordine coerente")
    if row.diametro and reader_document_contains_token(certificate_document.pages, row.diametro):
        add_reason(10, "Diametro coerente")

    for points, label in reader_score_supplier_field_matches(
        supplier_key=supplier_key,
        row=row,
        ddt_supplier_fields=ddt_supplier_fields,
        certificate_supplier_fields=certificate_supplier_fields,
    ):
        add_reason(points, label)

    if supplier_key == "aluminium_bozen":
        article_match = (
            reader_normalize_match_token(ddt_supplier_fields.get("article"))
            and reader_normalize_match_token(ddt_supplier_fields.get("article"))
            == reader_normalize_match_token(certificate_supplier_fields.get("article"))
        )
        customer_code_match = (
            reader_normalize_match_token(ddt_supplier_fields.get("customer_code"))
            and reader_normalize_match_token(ddt_supplier_fields.get("customer_code"))
            == reader_normalize_match_token(certificate_supplier_fields.get("customer_code"))
        )
        customer_order_match = (
            reader_normalize_match_token(ddt_supplier_fields.get("customer_order_normalized"))
            and reader_normalize_match_token(ddt_supplier_fields.get("customer_order_normalized"))
            == reader_normalize_match_token(certificate_supplier_fields.get("customer_order_normalized"))
        )
        cast_match = (
            reader_normalize_match_token(row.colata)
            and reader_normalize_match_token(row.colata) == reader_normalize_match_token(certificate_cast)
        )
        certificate_number_match = (
            reader_normalize_match_token(ddt_certificate_number)
            and reader_normalize_match_token(ddt_certificate_number) == reader_normalize_match_token(certificate_number)
        )
        weight_match = reader_weights_are_compatible(row.peso, certificate_weight)
        alloy_match = (
            reader_normalize_match_token(row.lega_base)
            and reader_normalize_match_token(row.lega_base)
            == reader_normalize_match_token(_string_or_none(matches.get("lega_certificato", {}).get("final")))
        )
        diameter_match = (
            reader_normalize_match_token(row.diametro)
            and reader_normalize_match_token(row.diametro)
            == reader_normalize_match_token(_string_or_none(matches.get("diametro_certificato", {}).get("final")))
        )
        has_full_structural_match = bool(
            article_match and customer_code_match and customer_order_match and alloy_match and diameter_match
        )
        has_row_match_with_cast_support = bool(
            cast_match and article_match and (customer_code_match or customer_order_match or diameter_match)
        )
        has_strong_row_link = bool(
            certificate_number_match or has_full_structural_match or has_row_match_with_cast_support
        )
        if not has_strong_row_link:
            return None
    elif supplier_key == "impol":
        packing_match = bool(
            reader_normalize_match_token(ddt_supplier_fields.get("packing_list_no"))
            and reader_normalize_match_token(ddt_supplier_fields.get("packing_list_no"))
            == reader_normalize_match_token(certificate_supplier_fields.get("packing_list_no"))
        )
        supplier_order_match = bool(
            reader_normalize_match_token(ddt_supplier_fields.get("supplier_order_no"))
            and reader_normalize_match_token(ddt_supplier_fields.get("supplier_order_no"))
            == reader_normalize_match_token(certificate_supplier_fields.get("supplier_order_no"))
        )
        product_code_match = bool(
            reader_normalize_match_token(ddt_supplier_fields.get("product_code"))
            and reader_normalize_match_token(ddt_supplier_fields.get("product_code"))
            == reader_normalize_match_token(certificate_supplier_fields.get("product_code"))
        )
        customer_order_match = bool(
            reader_normalize_match_token(ddt_supplier_fields.get("customer_order_no"))
            and reader_normalize_match_token(ddt_supplier_fields.get("customer_order_no"))
            == reader_normalize_match_token(certificate_supplier_fields.get("customer_order_no"))
        )
        cast_match = bool(
            reader_normalize_match_token(row.colata)
            and reader_normalize_match_token(row.colata) == reader_normalize_match_token(certificate_cast)
        )
        diameter_match = bool(
            reader_normalize_match_token(row.diametro)
            and reader_normalize_match_token(row.diametro)
            == reader_normalize_match_token(_string_or_none(matches.get("diametro_certificato", {}).get("final")))
        )
        alloy_match = bool(
            reader_normalize_match_token(row.lega_base)
            and reader_normalize_match_token(row.lega_base)
            == reader_normalize_match_token(_string_or_none(matches.get("lega_certificato", {}).get("final")))
        )
        weight_match = reader_weights_are_compatible(row.peso, certificate_weight)
        strong_mismatch = False
        if row.colata and certificate_cast and not cast_match:
            strong_mismatch = True
        if row.diametro and _string_or_none(matches.get("diametro_certificato", {}).get("final")) and not diameter_match:
            strong_mismatch = True
        if row.lega_base and _string_or_none(matches.get("lega_certificato", {}).get("final")) and not alloy_match:
            strong_mismatch = True
        if row.peso and certificate_weight and not weight_match:
            strong_mismatch = True
        strong_row_match_count = sum(1 for flag in (cast_match, diameter_match, alloy_match, weight_match) if flag)
        if strong_mismatch:
            return None
        if not (packing_match and strong_row_match_count >= 3):
            return None

    if score <= 10:
        return None

    ranked_reasons = [label for _, label in sorted(reasons, key=lambda item: item[0], reverse=True)]

    return {
        "document": certificate_document,
        "score": score,
        "reason": ", ".join(ranked_reasons[:3]) or "Certificato plausibile",
    }


def _record_history_event(
    db: Session,
    acquisition_row_id: int,
    blocco: str,
    azione: str,
    user_id: int | None,
    nota_breve: str | None = None,
) -> None:
    db.add(
        AcquisitionHistoryEvent(
            acquisition_row_id=acquisition_row_id,
            blocco=blocco,
            azione=azione,
            utente_id=user_id,
            nota_breve=nota_breve,
        )
    )


def _reopen_row_if_validated(
    db: Session,
    row: AcquisitionRow,
    *,
    actor_id: int,
    reason: str,
) -> None:
    if not row.validata_finale:
        return
    row.validata_finale = False
    row.stato_workflow = "riaperta"
    db.add(row)
    _record_history_event(
        db=db,
        acquisition_row_id=row.id,
        blocco="workflow",
        azione="riga_riaperta",
        user_id=actor_id,
        nota_breve=reason,
    )


def _sync_row_statuses(db: Session, row: AcquisitionRow) -> None:
    block_states = _compute_block_states_from_db(db, row)
    required_blocks = ("ddt", "match", "chimica", "proprieta", "note")
    required_states = [block_states.get(block, "rosso") for block in required_blocks]

    if all(state == "verde" for state in required_states):
        row.stato_tecnico = "verde"
    elif any(state == "rosso" for state in required_states):
        row.stato_tecnico = "rosso"
    else:
        row.stato_tecnico = "giallo"

    if row.validata_finale:
        row.stato_workflow = "validata_quality"
    elif row.stato_workflow not in {"riaperta", "validata_quality"}:
        has_activity = any(block_states.get(block) != "rosso" for block in required_blocks)
        row.stato_workflow = "in_lavorazione" if has_activity else "nuova"

    if row.stato_tecnico == "rosso":
        row.priorita_operativa = "alta"
    elif row.stato_tecnico == "giallo":
        row.priorita_operativa = "media"
    else:
        row.priorita_operativa = "bassa"

    db.add(row)


def _document_storage_root() -> Path:
    return Path(settings.document_storage_root)


def _compute_block_states(row: AcquisitionRow) -> dict[str, str]:
    values_by_block: dict[str, list[ReadValue]] = {}
    for value in row.values:
        values_by_block.setdefault(value.blocco, []).append(value)

    return {
        "ddt": _compute_ddt_block_state(row, values_by_block.get("ddt", [])),
        "match": _compute_match_block_state(row),
        "chimica": _compute_value_block_state(values_by_block.get("chimica", []), require_payload=True),
        "proprieta": _compute_value_block_state(values_by_block.get("proprieta", []), require_payload=True),
        "note": _compute_value_block_state(values_by_block.get("note", [])),
    }


def _compute_block_states_from_db(db: Session, row: AcquisitionRow) -> dict[str, str]:
    values = db.query(ReadValue).filter(ReadValue.acquisition_row_id == row.id).all()
    values_by_block: dict[str, list[ReadValue]] = {}
    for value in values:
        values_by_block.setdefault(value.blocco, []).append(value)

    match = (
        db.query(CertificateMatch)
        .filter(CertificateMatch.acquisition_row_id == row.id)
        .one_or_none()
    )

    return {
        "ddt": _compute_ddt_block_state(row, values_by_block.get("ddt", [])),
        "match": _compute_match_block_state_from_match(row.document_certificato_id, match),
        "chimica": _compute_value_block_state(values_by_block.get("chimica", []), require_payload=True),
        "proprieta": _compute_value_block_state(values_by_block.get("proprieta", []), require_payload=True),
        "note": _compute_value_block_state(values_by_block.get("note", [])),
    }


def _compute_match_block_state(row: AcquisitionRow) -> str:
    return _compute_match_block_state_from_match(row.document_certificato_id, row.certificate_match)


def _compute_match_block_state_from_match(
    document_certificato_id: int | None,
    match: CertificateMatch | None,
) -> str:
    if match is not None:
        if match.stato == "confermato":
            return "verde"
        return "giallo"
    if document_certificato_id is not None:
        return "giallo"
    return "rosso"


def _compute_value_block_state(values: list[ReadValue], fallback: str = "rosso", *, require_payload: bool = False) -> str:
    effective_values = [value for value in values if _read_value_has_payload(value)] if require_payload else values
    if not effective_values:
        return fallback
    if all(value.stato == "confermato" for value in effective_values):
        return "verde"
    return "giallo"


def _compute_ddt_block_state(row: AcquisitionRow, values: list[ReadValue]) -> str:
    if not row.document_ddt_id:
        return "rosso"
    summary = _compute_ddt_field_summary_from_values(values)
    required_missing = [field for field in summary["missing"] if field in _ddt_required_fields()]
    if required_missing:
        return "rosso"
    if not summary["pending"]:
        return "verde"
    return "giallo"


def _compute_ddt_field_summary(row: AcquisitionRow) -> dict[str, list[str]]:
    values = [value for value in row.values if value.blocco == "ddt"]
    return _compute_ddt_field_summary_from_values(values, row=row)


def _compute_ddt_field_summary_from_values(values: list[ReadValue], *, row: AcquisitionRow | None = None) -> dict[str, list[str]]:
    by_field = {value.campo: value for value in values}
    confirmed: list[str] = []
    pending: list[str] = []
    missing: list[str] = []

    for field in _ddt_required_fields() + _ddt_optional_fields():
        has_payload = _ddt_field_has_payload(by_field, field, row=row)
        if not has_payload:
            missing.append(field)
        elif _ddt_field_is_confirmed(by_field, field, row=row):
            confirmed.append(field)
        else:
            pending.append(field)

    return {
        "confirmed": confirmed,
        "pending": pending,
        "missing": missing,
    }


def _ddt_field_has_payload(by_field: dict[str, ReadValue], field: str, *, row: AcquisitionRow | None = None) -> bool:
    value = by_field.get(field)
    if value is not None and any(
        _string_or_none(candidate) is not None
        for candidate in (value.valore_finale, value.valore_standardizzato, value.valore_grezzo)
    ):
        return True

    if field == "cdq":
        fallback_value = by_field.get("numero_certificato_ddt")
        return fallback_value is not None and any(
            _string_or_none(candidate) is not None
            for candidate in (fallback_value.valore_finale, fallback_value.valore_standardizzato, fallback_value.valore_grezzo)
        )
    if row is not None:
        return _row_ddt_field_value(row, field) is not None
    return False


def _ddt_field_is_confirmed(by_field: dict[str, ReadValue], field: str, *, row: AcquisitionRow | None = None) -> bool:
    value = by_field.get(field)
    if value is not None and value.stato == "confermato" and _ddt_field_has_payload(by_field, field, row=row):
        return True
    if field == "cdq":
        fallback_value = by_field.get("numero_certificato_ddt")
        return fallback_value is not None and fallback_value.stato == "confermato" and _ddt_field_has_payload(by_field, field, row=row)
    return False


def _row_ddt_field_value(row: AcquisitionRow, field: str) -> str | None:
    field_map = {
        "cdq": row.cdq,
        "colata": row.colata,
        "diametro": row.diametro,
        "peso": row.peso,
        "numero_certificato_ddt": row.cdq,
        "ordine": row.ordine,
    }
    value = field_map.get(field)
    if field in {"diametro", "peso"}:
        return _normalize_value_for_field("ddt", field, value)
    return _string_or_none(value)


def _ddt_required_fields() -> tuple[str, ...]:
    return ("cdq", "colata", "diametro", "peso")


def _ddt_optional_fields() -> tuple[str, ...]:
    return ("numero_certificato_ddt", "ordine")


def _document_file_url(document: Document) -> str:
    return f"/api/acquisition/documents/{document.id}/file"


def _document_page_image_url(page: DocumentPage) -> str:
    return f"/api/acquisition/document-pages/{page.id}/image"


def _resolve_storage_path(storage_key: str) -> Path:
    root = _document_storage_root().resolve()
    resolved = (root / Path(storage_key)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage path") from exc
    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return resolved


def _index_document_from_path(db: Session, document: Document) -> Document:
    storage_path = _document_storage_root() / Path(document.storage_key)
    if not storage_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored document file not found")

    db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete(synchronize_session=False)
    document.pages = []

    try:
        page_payloads = _extract_pdf_page_payloads(document, storage_path)
        for payload in page_payloads:
            db.add(
                DocumentPage(
                    document_id=document.id,
                    numero_pagina=payload["numero_pagina"],
                    larghezza=payload["larghezza"],
                    altezza=payload["altezza"],
                    rotazione=payload["rotazione"],
                    testo_estratto=payload["testo_estratto"],
                    ocr_text=None,
                    immagine_pagina_storage_key=payload["immagine_pagina_storage_key"],
                    stato_estrazione=payload["stato_estrazione"],
                    hash_render=None,
                )
            )

        document.numero_pagine = len(page_payloads)
        document.stato_elaborazione = "indicizzato"
    except Exception:
        document.numero_pagine = None
        document.stato_elaborazione = "errore"

    db.commit()
    return get_document(db, document.id)


def _is_pdf_document(document: Document, mime_type: str | None) -> bool:
    if mime_type == "application/pdf":
        return True
    return Path(document.nome_file_originale).suffix.lower() == ".pdf"


def normalize_extracted_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _pdf_text_needs_ocr_fallback(value: str | None) -> bool:
    normalized = normalize_extracted_text(value)
    if normalized is None:
        return True

    ascii_alnum_count = len(re.findall(r"[A-Za-z0-9]", normalized))
    extended_latin_count = len(re.findall(r"[À-ÿ]", normalized))
    word_count = len(normalized.split())
    mojibake_markers = len(re.findall(r"[ßÝÛÒÑÞÔ×ØÐ]", normalized))

    if ascii_alnum_count == 0 and extended_latin_count >= 4:
        return True
    if extended_latin_count >= 6 and ascii_alnum_count < 12:
        return True
    if word_count <= 3 and extended_latin_count > ascii_alnum_count:
        return True
    if mojibake_markers >= 12 and mojibake_markers * 3 >= max(ascii_alnum_count, 1):
        return True
    return False


def _best_page_text(page: DocumentPage) -> str:
    pdf_text = normalize_extracted_text(page.testo_estratto)
    ocr_text = normalize_extracted_text(page.ocr_text)
    if ocr_text and _pdf_text_needs_ocr_fallback(pdf_text):
        return ocr_text
    return pdf_text or ocr_text or ""


def _page_lines(page: DocumentPage) -> list[str]:
    return [line.strip() for line in _best_page_text(page).splitlines() if line.strip()]


def _extract_pdf_page_payloads(document: Document, storage_path: Path) -> list[dict[str, object]]:
    reader = PdfReader(str(storage_path))
    fitz_doc = fitz.open(str(storage_path))
    page_payloads: list[dict[str, object]] = []

    try:
        for index, page in enumerate(reader.pages, start=1):
            try:
                pypdf_text = normalize_extracted_text(page.extract_text())
            except Exception:
                pypdf_text = None

            fitz_page = fitz_doc.load_page(index - 1)
            fitz_text = normalize_extracted_text(fitz_page.get_text("text"))
            extracted_text = fitz_text or pypdf_text
            page_image_storage_key = None
            extraction_state = "testo_pdf" if extracted_text else "immagine_pronta"
            if extracted_text is None:
                page_image_storage_key = _render_page_image(document.storage_key, fitz_page, index)

            page_payloads.append(
                {
                    "numero_pagina": index,
                    "larghezza": float(page.mediabox.width) if page.mediabox.width is not None else float(fitz_page.rect.width),
                    "altezza": float(page.mediabox.height) if page.mediabox.height is not None else float(fitz_page.rect.height),
                    "rotazione": int(fitz_page.rotation),
                    "testo_estratto": extracted_text,
                    "immagine_pagina_storage_key": page_image_storage_key,
                    "stato_estrazione": extraction_state,
                }
            )
    finally:
        fitz_doc.close()

    return page_payloads


def _ensure_document_page_images(db: Session, document: Document) -> Document:
    if document.pages and all(page.immagine_pagina_storage_key for page in document.pages):
        return document

    storage_path = get_document_file_path(document)
    if not _is_pdf_document(document, document.mime_type):
        return document

    fitz_doc = fitz.open(str(storage_path))
    changed = False
    try:
        for page in document.pages:
            if page.immagine_pagina_storage_key:
                continue
            fitz_page = fitz_doc.load_page(page.numero_pagina - 1)
            page.immagine_pagina_storage_key = _render_page_image(document.storage_key, fitz_page, page.numero_pagina)
            if page.stato_estrazione == "testo_pdf":
                page.stato_estrazione = "testo_pdf_immagine_pronta"
            db.add(page)
            changed = True
    finally:
        fitz_doc.close()

    if changed:
        db.commit()
        return get_document(db, document.id)
    return document


def _render_page_image(storage_key: str, page: fitz.Page, page_number: int) -> str:
    relative_pdf_path = Path(storage_key)
    image_relative_path = Path("renders") / relative_pdf_path.parent / f"{relative_pdf_path.stem}_page_{page_number}.png"
    absolute_image_path = _document_storage_root() / image_relative_path
    absolute_image_path.parent.mkdir(parents=True, exist_ok=True)

    pixmap = page.get_pixmap(dpi=300, alpha=False)
    pixmap.save(str(absolute_image_path))
    return image_relative_path.as_posix()


def _ensure_document_page_ocr(db: Session, document: Document) -> Document:
    changed = False
    for page in document.pages:
        if page.ocr_text:
            continue
        if page.testo_estratto and not _pdf_text_needs_ocr_fallback(page.testo_estratto):
            continue
        if not page.immagine_pagina_storage_key:
            continue
        image_path = get_document_page_image_path(page)
        ocr_text, extraction_state = _ocr_page_image(image_path, page_number=page.numero_pagina)
        if not ocr_text:
            continue
        page.ocr_text = ocr_text
        if page.stato_estrazione == "immagine_pronta":
            page.stato_estrazione = extraction_state
        elif "ocr" not in page.stato_estrazione:
            page.stato_estrazione = f"{page.stato_estrazione}_ocr"
        db.add(page)
        changed = True
    if changed:
        db.commit()
        return get_document(db, document.id)
    return document


def _ocr_page_image(image_path: Path, *, page_number: int) -> tuple[str | None, str]:
    keyword_patterns = (
        "delivery",
        "documento",
        "packing",
        "weight",
        "batch",
        "order",
        "alloy",
        "diameter",
        "kg",
        "charge",
        "part",
        "certificate",
    )
    candidates = [
        ("--psm 6", "ocr_locale_psm6"),
        ("--psm 4", "ocr_locale_psm4"),
    ]
    if page_number > 1:
        candidates = [
            ("--psm 4", "ocr_locale_psm4"),
            ("--psm 6", "ocr_locale_psm6"),
        ]

    best_text: str | None = None
    best_state = "ocr_locale"
    best_score = -1
    with Image.open(image_path) as image:
        for config, state in candidates:
            try:
                text = pytesseract.image_to_string(image, lang="eng+ita+deu", config=config)
            except pytesseract.TesseractNotFoundError:
                return None, "ocr_non_disponibile"
            except Exception:
                continue
            cleaned = _string_or_none(text)
            if cleaned is None:
                continue
            lowered = cleaned.casefold()
            score = len(re.findall(r"\d", cleaned)) + len(cleaned.splitlines())
            score += sum(6 for pattern in keyword_patterns if pattern in lowered)
            if score > best_score:
                best_text = cleaned
                best_state = state
                best_score = score
    return best_text, best_state


def _build_ddt_safe_crops(
    pages: list[DocumentPage],
    *,
    row: AcquisitionRow | None = None,
    supplier_key: str | None = None,
    ddt_values: dict[str, str | None] | None = None,
) -> dict[str, dict[str, str | int]]:
    if supplier_key == "aluminium_bozen" and row is not None:
        specialized = _build_aluminium_bozen_ddt_safe_crops(
            pages,
            row=row,
            ddt_values=ddt_values or {},
        )
        if specialized:
            return specialized

    crops: dict[str, dict[str, str | int]] = {}
    for page in pages:
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            crop_specs = [
                ("upper", (0.08, 0.18, 0.92, 0.56), "generic_ddt"),
                ("lower", (0.08, 0.54, 0.92, 0.90), "generic_ddt"),
            ]
            for suffix, ratios, role in crop_specs:
                crop_definition = _create_ddt_crop_definition(page, image, suffix=suffix, role=role, ratios=ratios)
                if crop_definition is None:
                    continue
                crops[crop_definition["label"]] = crop_definition
    return crops


def _save_ddt_crop(page: DocumentPage, image: Image.Image, suffix: str) -> str:
    base_name = f"page_{page.numero_pagina}_{suffix}_{uuid4().hex[:12]}.png"
    relative_path = Path("crops") / "ddt_vision" / datetime.now(UTC).strftime("%Y/%m/%d") / base_name
    absolute_path = _document_storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(absolute_path, format="PNG")
    return relative_path.as_posix()


def _document_has_image_pages(document: Document) -> bool:
    return any(page.immagine_pagina_storage_key for page in document.pages)


def _build_certificate_safe_crops(
    pages: list[DocumentPage],
    *,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    if supplier_key == "aluminium_bozen":
        specialized = _build_aluminium_bozen_certificate_safe_crops(pages)
        if specialized:
            return specialized
    if supplier_key == "impol":
        specialized = _build_impol_certificate_safe_crops(pages)
        if specialized:
            return specialized

    crops: dict[str, dict[str, str | int]] = {}
    for page in pages:
        if not page.immagine_pagina_storage_key:
            continue
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            crop_specs = [
                ("body_upper", (0.10, 0.16, 0.92, 0.48), "certificate_body"),
                ("body_middle", (0.10, 0.34, 0.92, 0.70), "certificate_body"),
                ("body_lower", (0.10, 0.56, 0.92, 0.90), "certificate_body"),
            ]
            for suffix, ratios, role in crop_specs:
                crop_definition = _create_certificate_crop_definition(page, image, suffix=suffix, role=role, ratios=ratios)
                if crop_definition is None:
                    continue
                crops[crop_definition["label"]] = crop_definition
    return crops


def _save_certificate_crop(page: DocumentPage, image: Image.Image, suffix: str) -> str:
    base_name = f"page_{page.numero_pagina}_{suffix}_{uuid4().hex[:12]}.png"
    relative_path = Path("crops") / "certificate_vision" / datetime.now(UTC).strftime("%Y/%m/%d") / base_name
    absolute_path = _document_storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(absolute_path, format="PNG")
    return relative_path.as_posix()


def _build_aluminium_bozen_ddt_safe_crops(
    pages: list[DocumentPage],
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    if not pages:
        return crops

    sorted_pages = sorted(pages, key=lambda item: item.numero_pagina)
    first_page = sorted_pages[0]
    header_crop = _create_dynamic_page_crop(
        first_page,
        suffix="header_num",
        role="header_num",
        top_ratio=0.04,
        bottom_ratio=0.22,
        left_ratio=0.05,
        right_ratio=0.95,
        save_crop=_save_ddt_crop,
    )
    if header_crop is not None:
        crops[header_crop["label"]] = header_crop

    material_tokens = [
        _string_or_none(ddt_values.get("article_code")),
        _string_or_none(ddt_values.get("customer_code")),
        _string_or_none(row.diametro),
        _string_or_none(row.lega_base),
        "BARRA TONDA",
    ]
    material_index = _find_best_page_line_index(
        first_page,
        required_tokens=material_tokens,
        preferred_tokens=["BARRA TONDA"],
    )
    if material_index is not None:
        material_crop = _create_line_band_crop(
            first_page,
            suffix="material_row",
            role="material_row",
            line_index=material_index,
            before_lines=2,
            after_lines=3,
            save_crop=_save_ddt_crop,
            left_ratio=0.04,
            right_ratio=0.96,
        )
        if material_crop is not None:
            crops[material_crop["label"]] = material_crop
        material_context_crop = _create_line_band_crop(
            first_page,
            suffix="material_context",
            role="material_context",
            line_index=material_index,
            before_lines=4,
            after_lines=6,
            save_crop=_save_ddt_crop,
            left_ratio=0.03,
            right_ratio=0.97,
        )
        if material_context_crop is not None:
            crops[material_context_crop["label"]] = material_context_crop
    else:
        fallback_material = _create_dynamic_page_crop(
            first_page,
            suffix="material_rows",
            role="material_rows",
            top_ratio=0.18,
            bottom_ratio=0.72,
            left_ratio=0.04,
            right_ratio=0.96,
            save_crop=_save_ddt_crop,
        )
        if fallback_material is not None:
            crops[fallback_material["label"]] = fallback_material

    packing_page, packing_index = _find_best_aluminium_bozen_packing_location(sorted_pages, row=row, ddt_values=ddt_values)
    if packing_page is not None and packing_index is not None:
        packing_crop = _create_line_band_crop(
            packing_page,
            suffix="packing_group",
            role="packing_group",
            line_index=packing_index,
            before_lines=3,
            after_lines=10,
            save_crop=_save_ddt_crop,
            left_ratio=0.03,
            right_ratio=0.97,
        )
        if packing_crop is not None:
            crops[packing_crop["label"]] = packing_crop
        packing_context_crop = _create_line_band_crop(
            packing_page,
            suffix="packing_context",
            role="packing_context",
            line_index=packing_index,
            before_lines=6,
            after_lines=16,
            save_crop=_save_ddt_crop,
            left_ratio=0.02,
            right_ratio=0.98,
        )
        if packing_context_crop is not None:
            crops[packing_context_crop["label"]] = packing_context_crop
    elif len(sorted_pages) > 1:
        fallback_page = sorted_pages[-1]
        fallback_packing = _create_dynamic_page_crop(
            fallback_page,
            suffix="packing_group",
            role="packing_group",
            top_ratio=0.24,
            bottom_ratio=0.94,
            left_ratio=0.03,
            right_ratio=0.97,
            save_crop=_save_ddt_crop,
        )
        if fallback_packing is not None:
            crops[fallback_packing["label"]] = fallback_packing

    return crops


def _build_aluminium_bozen_certificate_safe_crops(
    pages: list[DocumentPage],
) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    image_pages = [page for page in sorted(pages, key=lambda item: item.numero_pagina) if page.immagine_pagina_storage_key]
    if not image_pages:
        return crops

    for index, page in enumerate(image_pages):
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            masked_page = _build_aluminium_bozen_certificate_masked_page(image)
            storage_key = _save_certificate_crop(page, masked_page, f"masked_page_{page.numero_pagina}")
            width, height = masked_page.size
            if index == 0:
                role_specs = [
                    ("certificate_header", "certificate_header"),
                    ("identity_block", "identity_block"),
                    ("core_context", "certificate_core_context"),
                    ("chemistry_page", "chemistry_table"),
                    ("properties_page", "properties_table"),
                    ("notes_page", "notes_block"),
                ]
            else:
                role_specs = [
                    ("continuation_page", "certificate_continuation"),
                    ("notes_page", "notes_block"),
                ]
            for suffix, role in role_specs:
                label = f"page{page.numero_pagina}_{suffix}"
                crops[label] = {
                    "label": label,
                    "role": role,
                    "page_id": page.id,
                    "page_number": page.numero_pagina,
                    "storage_key": storage_key,
                    "bbox": f"0,0,{width},{height}",
                }
    return crops


def _build_aluminium_bozen_certificate_masked_page(image: Image.Image) -> Image.Image:
    width, height = image.size
    left = int(width * 0.028)
    top = int(height * 0.160)
    right = int(width * 0.972)
    bottom = int(height * 0.952)
    masked = image.crop((left, top, right, bottom)).convert("RGB")

    _mask_aluminium_bozen_customer_name(masked)
    return masked


def _mask_aluminium_bozen_customer_name(image: Image.Image) -> None:
    try:
        data = pytesseract.image_to_data(image, lang="eng+ita+deu", output_type=pytesseract.Output.DICT)
    except (OSError, pytesseract.TesseractNotFoundError):
        return

    tokens = data.get("text") or []
    block_nums = data.get("block_num") or []
    par_nums = data.get("par_num") or []
    line_nums = data.get("line_num") or []
    lefts = data.get("left") or []
    tops = data.get("top") or []
    widths = data.get("width") or []
    heights = data.get("height") or []

    line_tokens: dict[tuple[int, int, int], list[tuple[int, str, int, int, int, int]]] = {}
    anchor_indices: list[int] = []
    for index, token in enumerate(tokens):
        normalized = re.sub(r"[^A-Z0-9]", "", _string_or_none(token) or "").upper()
        try:
            line_key = (int(block_nums[index]), int(par_nums[index]), int(line_nums[index]))
            x0 = int(lefts[index])
            y0 = int(tops[index])
            width = int(widths[index])
            height = int(heights[index])
        except (TypeError, ValueError, IndexError):
            continue
        if width <= 0 or height <= 0:
            continue
        x1 = x0 + width
        y1 = y0 + height
        line_tokens.setdefault(line_key, []).append((index, normalized, x0, y0, x1, y1))
        if "FORGIALLUMINIO" in normalized:
            anchor_indices.append(index)

    if not anchor_indices:
        return

    max_gap = max(24, image.width // 28)
    draw = ImageDraw.Draw(image)
    masked_rects: list[tuple[int, int, int, int]] = []

    for anchor_index in anchor_indices:
        try:
            line_key = (int(block_nums[anchor_index]), int(par_nums[anchor_index]), int(line_nums[anchor_index]))
        except (TypeError, ValueError, IndexError):
            continue
        entries = sorted(line_tokens.get(line_key, []), key=lambda item: item[2])
        if not entries:
            continue
        anchor_position = next((idx for idx, item in enumerate(entries) if item[0] == anchor_index), None)
        if anchor_position is None:
            continue
        anchor = entries[anchor_position]
        _, _, ax0, ay0, ax1, ay1 = anchor

        cluster = [anchor]
        prev_x1 = ax1
        next_limit = min(len(entries), anchor_position + 5)
        for entry in entries[anchor_position + 1 : anchor_position + 5]:
            _, token_text, ex0, ey0, ex1, ey1 = entry
            if ex0 - prev_x1 > max_gap:
                break
            if not token_text:
                continue
            cluster.append(entry)
            prev_x1 = ex1

        left = max(0, min(item[2] for item in cluster) - max(10, image.width // 300))
        top = max(0, min(item[3] for item in cluster) - max(6, image.height // 350))
        right = min(image.width - 1, max(item[4] for item in cluster) + max(10, image.width // 300))
        bottom = min(image.height - 1, max(item[5] for item in cluster) + max(6, image.height // 350))
        if right <= left or bottom <= top:
            continue

        is_duplicate = any(
            abs(left - existing[0]) <= 4
            and abs(top - existing[1]) <= 4
            and abs(right - existing[2]) <= 4
            and abs(bottom - existing[3]) <= 4
            for existing in masked_rects
        )
        if is_duplicate:
            continue

        draw.rectangle((left, top, right, bottom), fill="black")
        masked_rects.append((left, top, right, bottom))


def _build_impol_certificate_safe_crops(
    pages: list[DocumentPage],
) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    image_pages = [page for page in sorted(pages, key=lambda item: item.numero_pagina) if page.immagine_pagina_storage_key]
    if not image_pages:
        return crops

    for index, page in enumerate(image_pages):
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            masked_page = _build_impol_certificate_masked_page(image)
            storage_key = _save_certificate_crop(page, masked_page, f"impol_masked_page_{page.numero_pagina}")
            width, height = masked_page.size
            if index == 0:
                role_specs = [
                    ("core_page", "certificate_core_context"),
                    ("chemistry_page", "chemistry_table"),
                    ("properties_page", "properties_table"),
                    ("notes_page", "notes_block"),
                ]
            else:
                role_specs = [
                    ("continuation_page", "certificate_continuation"),
                    ("notes_page", "notes_block"),
                ]
            for suffix, role in role_specs:
                label = f"page{page.numero_pagina}_{suffix}"
                crops[label] = {
                    "label": label,
                    "role": role,
                    "page_id": page.id,
                    "page_number": page.numero_pagina,
                    "storage_key": storage_key,
                    "bbox": f"0,0,{width},{height}",
                }
    return crops


def _build_impol_certificate_masked_page(image: Image.Image) -> Image.Image:
    masked = image.convert("RGB")
    _mask_impol_certificate_customer_block(masked)
    return masked


def _mask_impol_certificate_customer_block(image: Image.Image) -> None:
    _mask_ocr_block_between_anchors(
        image,
        start_terms=("CUSTOMER",),
        stop_terms=(
            "CUSTOMER ORDER",
            "SUPPLIER ORDER",
            "PACKING LIST",
            "ISSUE DATE",
            "PRODUCT DESCRIPTION",
            "CHEMICAL COMPOSITION",
        ),
        max_following_lines=8,
        right_limit_ratio=0.48,
    )


def _mask_ocr_block_between_anchors(
    image: Image.Image,
    *,
    start_terms: tuple[str, ...],
    stop_terms: tuple[str, ...],
    max_following_lines: int,
    right_limit_ratio: float,
) -> None:
    try:
        data = pytesseract.image_to_data(image, lang="eng+ita+deu", output_type=pytesseract.Output.DICT)
    except (OSError, pytesseract.TesseractNotFoundError):
        return

    tokens = data.get("text") or []
    block_nums = data.get("block_num") or []
    par_nums = data.get("par_num") or []
    line_nums = data.get("line_num") or []
    lefts = data.get("left") or []
    tops = data.get("top") or []
    widths = data.get("width") or []
    heights = data.get("height") or []

    line_map: dict[tuple[int, int, int], dict[str, object]] = {}
    for index, token in enumerate(tokens):
        normalized = re.sub(r"\s+", " ", (_string_or_none(token) or "").upper()).strip()
        try:
            line_key = (int(block_nums[index]), int(par_nums[index]), int(line_nums[index]))
            x0 = int(lefts[index])
            y0 = int(tops[index])
            width = int(widths[index])
            height = int(heights[index])
        except (TypeError, ValueError, IndexError):
            continue
        if width <= 0 or height <= 0:
            continue
        x1 = x0 + width
        y1 = y0 + height
        entry = line_map.setdefault(
            line_key,
            {"text_parts": [], "left": x0, "top": y0, "right": x1, "bottom": y1},
        )
        if normalized:
            cast(list[str], entry["text_parts"]).append(normalized)
        entry["left"] = min(int(entry["left"]), x0)
        entry["top"] = min(int(entry["top"]), y0)
        entry["right"] = max(int(entry["right"]), x1)
        entry["bottom"] = max(int(entry["bottom"]), y1)

    lines = []
    for entry in line_map.values():
        text = " ".join(cast(list[str], entry["text_parts"])).strip()
        if not text:
            continue
        lines.append(
            {
                "text": text,
                "left": int(entry["left"]),
                "top": int(entry["top"]),
                "right": int(entry["right"]),
                "bottom": int(entry["bottom"]),
            }
        )
    lines.sort(key=lambda item: (int(item["top"]), int(item["left"])))
    if not lines:
        return

    normalized_start_terms = [term.upper() for term in start_terms]
    normalized_stop_terms = [term.upper() for term in stop_terms]
    start_index = next(
        (
            index
            for index, line in enumerate(lines)
            if any(term in str(line["text"]) for term in normalized_start_terms)
            and not any(term in str(line["text"]) for term in normalized_stop_terms)
        ),
        None,
    )
    if start_index is None:
        return

    cluster = [lines[start_index]]
    previous_bottom = int(lines[start_index]["bottom"])
    max_vertical_gap = max(18, image.height // 35)
    for line in lines[start_index + 1 : start_index + 1 + max_following_lines]:
        text = str(line["text"])
        if any(term in text for term in normalized_stop_terms):
            break
        if int(line["top"]) - previous_bottom > max_vertical_gap:
            break
        cluster.append(line)
        previous_bottom = int(line["bottom"])

    left = max(0, min(int(line["left"]) for line in cluster) - max(10, image.width // 250))
    top = max(0, min(int(line["top"]) for line in cluster) - max(6, image.height // 300))
    right = min(int(image.width * right_limit_ratio), max(int(line["right"]) for line in cluster) + max(12, image.width // 220))
    bottom = min(image.height - 1, max(int(line["bottom"]) for line in cluster) + max(8, image.height // 260))
    if right <= left or bottom <= top:
        return

    draw = ImageDraw.Draw(image)
    draw.rectangle((left, top, right, bottom), fill="black")

def _create_ddt_crop_definition(
    page: DocumentPage,
    image: Image.Image,
    *,
    suffix: str,
    role: str,
    ratios: tuple[float, float, float, float],
) -> dict[str, str | int] | None:
    return _create_image_crop_definition(
        page,
        image,
        suffix=suffix,
        role=role,
        ratios=ratios,
        save_crop=_save_ddt_crop,
    )


def _create_certificate_crop_definition(
    page: DocumentPage,
    image: Image.Image,
    *,
    suffix: str,
    role: str,
    ratios: tuple[float, float, float, float],
) -> dict[str, str | int] | None:
    return _create_image_crop_definition(
        page,
        image,
        suffix=suffix,
        role=role,
        ratios=ratios,
        save_crop=_save_certificate_crop,
    )


def _create_dynamic_page_crop(
    page: DocumentPage,
    *,
    suffix: str,
    role: str,
    top_ratio: float,
    bottom_ratio: float,
    left_ratio: float,
    right_ratio: float,
    save_crop,
) -> dict[str, str | int] | None:
    image_path = get_document_page_image_path(page)
    with Image.open(image_path) as image:
        return _create_image_crop_definition(
            page,
            image,
            suffix=suffix,
            role=role,
            ratios=(left_ratio, top_ratio, right_ratio, bottom_ratio),
            save_crop=save_crop,
        )


def _create_line_band_crop(
    page: DocumentPage,
    *,
    suffix: str,
    role: str,
    line_index: int,
    before_lines: int,
    after_lines: int,
    save_crop,
    left_ratio: float,
    right_ratio: float,
) -> dict[str, str | int] | None:
    lines = _page_lines(page)
    if not lines:
        return None
    total_lines = max(len(lines), 1)
    top_ratio = max(0.04, (line_index - before_lines) / total_lines)
    bottom_ratio = min(0.96, (line_index + after_lines + 1) / total_lines)
    if bottom_ratio - top_ratio < 0.08:
        center = (line_index + 0.5) / total_lines
        top_ratio = max(0.04, center - 0.06)
        bottom_ratio = min(0.96, center + 0.10)
    return _create_dynamic_page_crop(
        page,
        suffix=suffix,
        role=role,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio,
        left_ratio=left_ratio,
        right_ratio=right_ratio,
        save_crop=save_crop,
    )


def _create_image_crop_definition(
    page: DocumentPage,
    image: Image.Image,
    *,
    suffix: str,
    role: str,
    ratios: tuple[float, float, float, float],
    save_crop,
) -> dict[str, str | int] | None:
    width, height = image.size
    left_ratio, top_ratio, right_ratio, bottom_ratio = ratios
    left = int(width * left_ratio)
    top = int(height * top_ratio)
    right = int(width * right_ratio)
    bottom = int(height * bottom_ratio)
    if right <= left or bottom <= top:
        return None
    crop = image.crop((left, top, right, bottom))
    storage_key = save_crop(page, crop, suffix)
    crop_label = f"page{page.numero_pagina}_{suffix}"
    return {
        "label": crop_label,
        "role": role,
        "page_id": page.id,
        "page_number": page.numero_pagina,
        "storage_key": storage_key,
        "bbox": f"{left},{top},{right},{bottom}",
    }


def _find_best_page_line_index(
    page: DocumentPage,
    *,
    required_tokens: list[str | None],
    preferred_tokens: list[str | None] | None = None,
) -> int | None:
    lines = _page_lines(page)
    if not lines:
        return None
    normalized_tokens = [_normalize_mojibake_numeric_text(token).upper() for token in required_tokens if _string_or_none(token)]
    preferred = [_normalize_mojibake_numeric_text(token).upper() for token in (preferred_tokens or []) if _string_or_none(token)]
    best_index: int | None = None
    best_score = 0
    for index, line in enumerate(lines):
        normalized_line = _normalize_mojibake_numeric_text(line).upper()
        score = sum(8 for token in normalized_tokens if token in normalized_line)
        score += sum(3 for token in preferred if token in normalized_line)
        if score > best_score:
            best_score = score
            best_index = index
    return best_index if best_score > 0 else None


def _find_best_aluminium_bozen_packing_location(
    pages: list[DocumentPage],
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
) -> tuple[DocumentPage | None, int | None]:
    search_tokens = [
        _string_or_none(row.ordine),
        _string_or_none(ddt_values.get("customer_order_no")),
        _string_or_none(row.cdq),
        _string_or_none(row.colata),
        "RIF. ORDINE AB ODV",
        "CERT. N",
        "COD. COLATA",
    ]
    ranked_pages = sorted(pages, key=lambda page: (0 if page.numero_pagina > 1 else 1, page.numero_pagina))
    best_page: DocumentPage | None = None
    best_index: int | None = None
    best_score = 0
    for page in ranked_pages:
        lines = _page_lines(page)
        if not lines:
            continue
        normalized_tokens = [_normalize_mojibake_numeric_text(token).upper() for token in search_tokens if _string_or_none(token)]
        for index, line in enumerate(lines):
            normalized_line = _normalize_mojibake_numeric_text(line).upper()
            score = sum(10 for token in normalized_tokens if token in normalized_line)
            if "RIF. ORDINE AB ODV" in normalized_line:
                score += 6
            if "CERT" in normalized_line:
                score += 3
            if score > best_score:
                best_score = score
                best_page = page
                best_index = index
    return best_page, best_index


def _extract_ddt_fields_from_openai(
    crops: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> dict[str, dict[str, str | None]]:
    client = OpenAI(api_key=openai_api_key)
    field_names = [
        "ddt",
        "numero_certificato_ddt",
        "cdq",
        "colata",
        "peso",
        "diametro",
        "ordine",
        "customer_order_no",
        "customer_code",
        "article_code",
        "lega",
    ]
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi solo i ritagli mascherati di un documento tecnico di trasporto. "
                "I ritagli possono avere ruoli come header_num, material_row, material_context, packing_group, packing_context. "
                "Usa esclusivamente il testo visibile nei ritagli. Non inventare dati assenti. "
                f"Restituisci JSON puro con sole queste chiavi: {', '.join(field_names)}. "
                "Ogni chiave deve essere un oggetto con campi value, evidence, source_crop. "
                "Usa null se il dato non e' leggibile o se sei incerto. "
                "ddt = numero del documento di trasporto letto dal ritaglio header_num. "
                "numero_certificato_ddt = numero certificato letto da etichette tipo Cert. N o Certificato; "
                "non usare stringhe normative come EN 10204 3.1, Inspection Certificate o riferimenti ASTM/AMS. "
                "cdq = popolalo solo se il DDT riporta davvero una sigla esplicita CdQ/C.d.Q.; se sul DDT c'e' solo Cert. N lascia cdq null. "
                "ordine = per questo fornitore lascia null; non usare mai il valore di Rif. ns. Odv N. come ordine finale. "
                "customer_order_no = riferimento ordine cliente della riga, anche se visibile come numero e data o data e numero; "
                "usa solo il valore di Vs. Odv e normalizzalo come numero-data; non usare mai Rif. ns. Odv N. al posto di Vs. Odv. "
                "customer_code = codice cliente/materiale come token tecnico, ad esempio codici che iniziano con A. "
                "article_code = codice articolo tecnico, ad esempio token come 14BT.... "
                "lega = lega/stato metallurgico della riga materiale. "
                "diametro = valore associato alla riga materiale, non norme o altri riferimenti. "
                "colata = cast/lot/charge della stessa riga materiale. "
                "peso = solo il peso netto della singola riga materiale; non usare totali o riepiloghi di packing list. "
                "Usa source_crop esattamente come il label del ritaglio fornito."
            ),
        }
    ]

    for crop_label, crop in crops.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        mime_type = "image/png"
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Crop label: {crop_label}; "
                    f"role: {crop.get('role') or 'unknown'}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}", "detail": "high"})

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[
                {
                "role": "user",
                "content": content,
            }
        ],
    )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Vision extraction request failed") from exc

    return _parse_openai_json_payload_for_fields(response.output_text, field_names)


def _extract_certificate_fields_from_openai(
    crops: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
    field_names: list[str],
    instruction: str,
) -> dict[str, dict[str, str | None]]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                f"{instruction} "
                "Restituisci JSON puro. "
                f"Usa solo queste chiavi: {', '.join(field_names)}. "
                "Ogni chiave deve essere un oggetto con campi value, evidence, source_crop. "
                "Usa null se il dato non e' leggibile o se sei incerto. "
                "Usa source_crop esattamente come il label dell'immagine fornita. "
                "Non inventare valori mancanti."
            ),
        }
    ]

    for crop_label, crop in crops.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        mime_type = "image/png"
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Image label: {crop_label}; "
                    f"role: {crop.get('role') or 'unknown'}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}", "detail": "high"})

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Certificate vision extraction request failed") from exc

    return _parse_openai_json_payload_for_fields(response.output_text, field_names)


def _sanitize_aluminium_bozen_vision_certificate_fields(
    extracted: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    def _payload(raw_field_name: str) -> dict[str, str | None]:
        return extracted.get(raw_field_name) or {"value": None, "evidence": None, "source_crop": None}

    def _normalize_certificate_number(value: str | None, evidence: str | None) -> str | None:
        token = _extract_token_from_value_or_evidence(
            value,
            evidence,
            r"\b\d{4,7}[A-Z]?\b",
            disallow={"10204"},
        )
        if token is None or re.fullmatch(r"20\d{2}", token):
            return None
        if _looks_like_invalid_cdq(token, evidence):
            return None
        return token

    def _normalize_article_code(value: str | None, evidence: str | None) -> str | None:
        return _extract_token_from_value_or_evidence(
            value,
            evidence,
            r"\b[0-9]{2}[A-Z]{2}[0-9A-Z-]{4,}\b",
        )

    def _normalize_customer_code(value: str | None, evidence: str | None) -> str | None:
        token = _extract_token_from_value_or_evidence(
            value,
            evidence,
            r"\bA[0-9A-Z]{5,}\b",
        )
        return _normalize_aluminium_bozen_customer_code_token(token)

    def _normalize_customer_order(value: str | None, evidence: str | None) -> str | None:
        normalized = _normalize_customer_order_tokens(value) or _normalize_customer_order_tokens(evidence)
        if not _is_normalized_customer_order(normalized):
            return None
        return normalized

    def _normalize_alloy(value: str | None, evidence: str | None) -> str | None:
        haystacks = [candidate for candidate in (value, evidence) if _string_or_none(candidate)]
        for haystack in haystacks:
            match = re.search(
                r"\b([1-9][0-9]{3}[A-Z]{0,3})\s+(HF\s*/\s*F|H\s*/\s*F|G\s*/\s*F|GF|HF|F|T\d+[A-Z0-9/-]*)\b",
                haystack.upper(),
            )
            if match is None:
                continue
            alloy_base = match.group(1).strip()
            alloy_state = match.group(2).replace(" / ", " ").replace("/", " ").strip()
            if alloy_state == "F" and alloy_base.endswith("F") and not alloy_base.endswith(("HF", "GF")):
                alloy_base = alloy_base[:-1]
            alloy = f"{alloy_base} {alloy_state}"
            return re.sub(r"\s+", " ", alloy).strip()
        return None

    def _normalize_diameter(value: str | None, evidence: str | None) -> str | None:
        haystacks = [candidate for candidate in (value, evidence) if _string_or_none(candidate)]
        for haystack in haystacks:
            for match in re.finditer(r"\b\d{1,3}(?:[.,]\d+)?\b", haystack):
                normalized = _normalize_numeric_value(match.group(0))
                if normalized is None:
                    continue
                try:
                    numeric_value = float(normalized)
                except ValueError:
                    continue
                if 0 < numeric_value <= 400:
                    return normalized
        return None

    def _normalize_cast(value: str | None, evidence: str | None) -> str | None:
        return _extract_token_from_value_or_evidence(
            value,
            evidence,
            r"\b(?:[A-Z]\d{5,}[A-Z]?|\d{5,}[A-Z]\d|\d{5,}[A-Z]|\d{5,})\b",
            disallow={"10204"},
        )

    def _normalize_weight(value: str | None, evidence: str | None) -> str | None:
        return _normalize_numeric_value(value) or _normalize_numeric_value(evidence)

    field_mapping = {
        "numero_certificato_certificato": ("certificate_number_raw", _normalize_certificate_number),
        "articolo_certificato": ("article_code_raw", _normalize_article_code),
        "codice_cliente_certificato": ("profile_customer_description_raw", _normalize_customer_code),
        "ordine_cliente_certificato": ("customer_order_raw", _normalize_customer_order),
        "lega_certificato": ("alloy_raw", _normalize_alloy),
        "diametro_certificato": ("profile_customer_description_raw", _normalize_diameter),
        "colata_certificato": ("cast_raw", _normalize_cast),
        "peso_certificato": ("net_weight_raw", _normalize_weight),
    }

    normalized: dict[str, dict[str, str | None]] = {}
    for target_field, (raw_field_name, normalizer) in field_mapping.items():
        raw_payload = _payload(raw_field_name)
        raw_value = _string_or_none(raw_payload.get("value"))
        evidence = _string_or_none(raw_payload.get("evidence")) or raw_value
        normalized[target_field] = {
            "value": normalizer(raw_value, evidence),
            "evidence": evidence,
            "source_crop": _string_or_none(raw_payload.get("source_crop")),
        }

    return normalized


def _get_aluminium_bozen_certificate_ai_payload(
    db: Session,
    *,
    certificate_document: Document,
    openai_api_key: str,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
) -> dict[str, object]:
    cached = certificate_ai_cache.get(certificate_document.id) if certificate_ai_cache is not None else None
    if cached is not None:
        return cached

    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)
    certificate_document = _ensure_document_page_images(db, certificate_document)
    if not _document_has_image_pages(certificate_document):
        empty_payload = {
            "match_values": {},
            "supplier_fields": {},
            "chemistry": {},
            "properties": {},
            "notes": {},
        }
        if certificate_ai_cache is not None:
            certificate_ai_cache[certificate_document.id] = empty_payload
        return empty_payload

    crops = _build_certificate_safe_crops(certificate_document.pages, supplier_key="aluminium_bozen")
    page_images = _select_aluminium_bozen_certificate_document_images(crops)
    if not page_images:
        empty_payload = {
            "match_values": {},
            "supplier_fields": {},
            "chemistry": {},
            "properties": {},
            "notes": {},
        }
        if certificate_ai_cache is not None:
            certificate_ai_cache[certificate_document.id] = empty_payload
        return empty_payload

    raw_payload = _extract_aluminium_bozen_certificate_payload_from_openai(
        page_images,
        openai_api_key=openai_api_key,
    )
    payload = _normalize_aluminium_bozen_certificate_ai_payload(page_images, raw_payload)
    if certificate_ai_cache is not None:
        certificate_ai_cache[certificate_document.id] = payload
    return payload


def _select_aluminium_bozen_certificate_document_images(
    crops: dict[str, dict[str, str | int]],
) -> dict[str, dict[str, str | int]]:
    selected: dict[str, dict[str, str | int]] = {}
    by_page: dict[int, list[tuple[str, dict[str, str | int]]]] = {}
    for label, crop in crops.items():
        page_number = int(crop.get("page_number") or 0)
        if page_number <= 0:
            continue
        by_page.setdefault(page_number, []).append((label, crop))

    role_priority = {
        "certificate_core_context": 1,
        "certificate_continuation": 2,
        "identity_block": 3,
        "chemistry_table": 4,
        "properties_table": 5,
        "notes_block": 6,
        "certificate_header": 7,
    }
    for page_number, entries in sorted(by_page.items()):
        best_label, best_crop = sorted(
            entries,
            key=lambda item: (
                role_priority.get(_string_or_none(item[1].get("role")) or "", 99),
                item[0],
            ),
        )[0]
        selected[best_label] = best_crop
    return selected


def _extract_aluminium_bozen_certificate_payload_from_openai(
    page_images: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> dict[str, object]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi questo certificato materiale. "
                "Scopo: estrarre i dati identificativi e tecnici del certificato, leggere composizione chimica, proprieta meccaniche e note tecniche rilevanti. "
                "Presta particolare attenzione a peso netto del materiale e descrizione profilo cliente. "
                "Usa solo testo realmente visibile nel documento. Non inventare, non inferire, non normalizzare. "
                "Se un campo non e chiaramente leggibile, restituisci null. "
                "Per l'ordine cliente usa il campo che indica chiaramente l'ordine del cliente; "
                "non usare il campo che indica l'ordine interno A.B. o equivalente. "
                "Campi core da estrarre. "
                "numero_certificato: estrai il numero certificato dal campo che identifica chiaramente il certificato; "
                "esempi frequenti: CERT.NO, Nr.CERT, No.CERT. "
                "ordine_cliente: estrai il valore del campo che indica chiaramente l'ordine cliente; "
                "esempi frequenti: Nr. ORDINE CLIENTE, CUSTOMER ORDER, CLIENT ORDER; "
                "non usare il campo dell'ordine interno A.B. o equivalente. "
                "articolo: estrai il codice articolo dal campo che identifica chiaramente articolo o profilo; "
                "esempi frequenti: ARTICOLO, ARTICLE, PROFIL. "
                "lega: estrai la lega dal campo che identifica chiaramente lega e stato fisico; "
                "esempi frequenti: LEGA, ALLOY, ALLOY & Phys.State. "
                "descrizione_profilo_cliente: estrai l'intero contenuto raw del campo DESCRIZIONE PROFILO CLIENTE "
                "o di un campo equivalente che descrive profilo cliente o sezione cliente; "
                "il valore puo contenere codice, descrizione e numero finale; "
                "se il contenuto e spezzato su due righe ma appartiene allo stesso blocco o cella, unisci le righe con uno spazio; "
                "includi anche il numero sotto o dopo la descrizione se appartiene ancora allo stesso blocco visivo; "
                "fermati solo quando inizia chiaramente un nuovo campo con label distinto; "
                "esempi frequenti: DESCRIZIONE PROFILO CLIENTE, CUSTOMER'S SECTION DESC., PROFILE CUSTOMER DESC, PROFIL NR. KUNDE. "
                "colata: estrai il valore del campo che identifica chiaramente colata, batch o charge; "
                "esempi frequenti: N° COLATA, CAST BATCH N°, CHARGE N°, CAST NO. "
                "peso_netto: estrai il valore del campo PESO NETTO "
                "o di un campo equivalente che indica chiaramente il peso netto del materiale; "
                "esempi frequenti: PESO NETTO, NET WEIGHT, POIDS NET, NETTOGEWICHT; "
                "il valore puo essere un numero senza unita; "
                "considera valido il numero piu vicino al label nella stessa riga, cella o area visiva; "
                "non confondere questo campo con altri pesi, quantita o valori tabellari; "
                "non restituire null se il label e presente e un numero e chiaramente associato nella stessa area. "
                "Chimica: usa solo Si, Fe, Cu, Mn, Mg, Cr, Ni, Zn, Ti, Pb, V, Bi, Sn, Zr, Be, Zr+Ti, Mn+Cr, Bi+Pb; "
                "restituisci solo i valori misurati veri e ignora Min e Max. "
                "Proprieta meccaniche: considera Rm, Rp0.2, A%, HB, IACS%, Rp0.2/Rm; non usare Min o Max; "
                "se ci sono piu righe misurate vere, restituisci tutte le righe misurate raw. "
                "Note: verifica solo nota_us_control_classe, nota_rohs, nota_radioactive_free. "
                "Restituisci solo JSON con questa struttura: "
                "{\"core\":{\"numero_certificato\":\"string|null\",\"ordine_cliente\":\"string|null\",\"articolo\":\"string|null\","
                "\"lega\":\"string|null\",\"descrizione_profilo_cliente\":\"string|null\",\"colata\":\"string|null\",\"peso_netto\":\"string|null\"},"
                "\"chemistry_raw\":{\"Si\":\"string|null\",\"Fe\":\"string|null\",\"Cu\":\"string|null\",\"Mn\":\"string|null\",\"Mg\":\"string|null\","
                "\"Cr\":\"string|null\",\"Ni\":\"string|null\",\"Zn\":\"string|null\",\"Ti\":\"string|null\",\"Pb\":\"string|null\",\"V\":\"string|null\","
                "\"Bi\":\"string|null\",\"Sn\":\"string|null\",\"Zr\":\"string|null\",\"Be\":\"string|null\",\"Zr+Ti\":\"string|null\",\"Mn+Cr\":\"string|null\","
                "\"Bi+Pb\":\"string|null\"},"
                "\"mechanical_raw\":{\"measured_rows\":[{\"Rm\":\"string|null\",\"Rp0.2\":\"string|null\",\"A%\":\"string|null\",\"HB\":\"string|null\","
                "\"IACS%\":\"string|null\",\"Rp0.2/Rm\":\"string|null\"}]},"
                "\"notes_raw\":{\"nota_us_control_classe_raw\":\"string|null\",\"nota_rohs_raw\":\"string|null\",\"nota_radioactive_free_raw\":\"string|null\"}}"
            ),
        }
    ]

    for image_label, crop in page_images.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Image label: {image_label}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{encoded}", "detail": "high"})

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Certificate AI extraction request failed") from exc

    return _parse_openai_json_payload_for_certificate_bundle(response.output_text)


def _parse_openai_json_payload_for_certificate_bundle(payload: str) -> dict[str, object]:
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from certificate AI extraction")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from certificate AI extraction") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected certificate AI payload structure")
    return data


def _normalize_aluminium_bozen_certificate_ai_payload(
    page_images: dict[str, dict[str, str | int]],
    raw_payload: dict[str, object],
) -> dict[str, object]:
    first_page_crop = next(iter(page_images.values()), None)
    first_page_id = int(first_page_crop.get("page_id")) if first_page_crop and first_page_crop.get("page_id") else 0
    last_page_crop = next(reversed(page_images.values()), None) if page_images else None
    last_page_id = int(last_page_crop.get("page_id")) if last_page_crop and last_page_crop.get("page_id") else first_page_id

    core_payload = cast(dict[str, object], raw_payload.get("core") or {})
    core_aliases = {
        "certificate_number_raw": ("numero_certificato", "certificate_number_raw"),
        "customer_order_raw": ("ordine_cliente", "customer_order_raw"),
        "article_code_raw": ("articolo", "article_code_raw"),
        "alloy_raw": ("lega", "alloy_raw"),
        "profile_customer_description_raw": ("descrizione_profilo_cliente", "profile_customer_description_raw"),
        "cast_raw": ("colata", "cast_raw"),
        "net_weight_raw": ("peso_netto", "net_weight_raw"),
    }
    core_extracted: dict[str, dict[str, str | None]] = {}
    for field_name, aliases in core_aliases.items():
        raw_value = None
        for alias in aliases:
            raw_value = _string_or_none(core_payload.get(alias))
            if raw_value is not None:
                break
        core_extracted[field_name] = {
            "value": raw_value,
            "evidence": raw_value,
            "source_crop": next(iter(page_images.keys()), None),
        }
    sanitized_core = _sanitize_aluminium_bozen_vision_certificate_fields(core_extracted)

    chemistry_payload = cast(dict[str, object], raw_payload.get("chemistry_raw") or {})
    chemistry_matches = _normalize_vision_numeric_matches(
        {
            field_name: {
                "value": _string_or_none(chemistry_payload.get(field_name)),
                "evidence": _string_or_none(chemistry_payload.get(field_name)),
                "source_crop": next(iter(page_images.keys()), None),
            }
            for field_name in ("Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Ni", "Zn", "Ti", "Pb", "V", "Bi", "Sn", "Zr", "Be", "Zr+Ti", "Mn+Cr", "Bi+Pb")
        },
        {
            next(iter(page_images.keys()), "page1"): {
                "page_id": first_page_id,
                "page_number": first_page_crop.get("page_number") if first_page_crop else 1,
            }
        },
    )

    measured_rows_payload = cast(dict[str, object], raw_payload.get("mechanical_raw") or {}).get("measured_rows") or []
    property_matches = _normalize_aluminium_bozen_measured_rows_payload(
        measured_rows_payload if isinstance(measured_rows_payload, list) else [],
        page_id=first_page_id,
    )

    notes_payload = cast(dict[str, object], raw_payload.get("notes_raw") or {})
    note_matches = _normalize_vision_note_matches(
        {
            "nota_us_control_classe": {
                "value": _string_or_none(notes_payload.get("nota_us_control_classe_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_us_control_classe_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
            "nota_rohs": {
                "value": _string_or_none(notes_payload.get("nota_rohs_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_rohs_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
            "nota_radioactive_free": {
                "value": _string_or_none(notes_payload.get("nota_radioactive_free_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_radioactive_free_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
        },
        {
            next(reversed(page_images.keys()), "page1"): {
                "page_id": last_page_id,
                "page_number": last_page_crop.get("page_number") if last_page_crop else (first_page_crop.get("page_number") if first_page_crop else 1),
            }
        },
    )

    return {
        "match_values": {
            field_name: _string_or_none(field_payload.get("value"))
            for field_name, field_payload in sanitized_core.items()
        },
        "supplier_fields": {
            "article": _string_or_none((sanitized_core.get("articolo_certificato") or {}).get("value")),
            "customer_code": _string_or_none((sanitized_core.get("codice_cliente_certificato") or {}).get("value")),
            "customer_order_normalized": _string_or_none((sanitized_core.get("ordine_cliente_certificato") or {}).get("value")),
        },
        "core_fields": sanitized_core,
        "chemistry": chemistry_matches,
        "properties": property_matches,
        "notes": note_matches,
        "debug_raw_output": json.dumps(raw_payload, ensure_ascii=False),
    }


def _get_impol_certificate_ai_payload(
    db: Session,
    *,
    certificate_document: Document,
    openai_api_key: str,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
) -> dict[str, object]:
    cached = certificate_ai_cache.get(certificate_document.id) if certificate_ai_cache is not None else None
    if cached is not None:
        return cached

    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)
    certificate_document = _ensure_document_page_images(db, certificate_document)
    if not _document_has_image_pages(certificate_document):
        empty_payload = {
            "match_values": {},
            "supplier_fields": {},
            "chemistry": {},
            "properties": {},
            "notes": {},
        }
        if certificate_ai_cache is not None:
            certificate_ai_cache[certificate_document.id] = empty_payload
        return empty_payload

    crops = _build_certificate_safe_crops(certificate_document.pages, supplier_key="impol")
    page_images = _select_impol_certificate_document_images(crops)
    if not page_images:
        empty_payload = {
            "match_values": {},
            "supplier_fields": {},
            "chemistry": {},
            "properties": {},
            "notes": {},
        }
        if certificate_ai_cache is not None:
            certificate_ai_cache[certificate_document.id] = empty_payload
        return empty_payload

    raw_payload = _extract_impol_certificate_payload_from_openai(
        page_images,
        openai_api_key=openai_api_key,
    )
    payload = _normalize_impol_certificate_ai_payload(page_images, raw_payload)
    if certificate_ai_cache is not None:
        certificate_ai_cache[certificate_document.id] = payload
    return payload


def _select_impol_certificate_document_images(
    crops: dict[str, dict[str, str | int]],
) -> dict[str, dict[str, str | int]]:
    selected: dict[str, dict[str, str | int]] = {}
    by_page: dict[int, list[tuple[str, dict[str, str | int]]]] = {}
    for label, crop in crops.items():
        page_number = int(crop.get("page_number") or 0)
        if page_number <= 0:
            continue
        by_page.setdefault(page_number, []).append((label, crop))

    role_priority = {
        "certificate_core_context": 1,
        "certificate_continuation": 2,
        "chemistry_table": 3,
        "properties_table": 4,
        "notes_block": 5,
    }
    for page_number, entries in sorted(by_page.items()):
        best_label, best_crop = sorted(
            entries,
            key=lambda item: (
                role_priority.get(_string_or_none(item[1].get("role")) or "", 99),
                item[0],
            ),
        )[0]
        selected[best_label] = best_crop
    return selected


def _extract_impol_certificate_payload_from_openai(
    page_images: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> dict[str, object]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi questo certificato materiale. "
                "Scopo: estrarre i dati identificativi e tecnici del certificato, leggere composizione chimica, proprieta meccaniche e note tecniche rilevanti. "
                "Presta particolare attenzione a Packing list No., Customer Order No., Supplier Order No., Netto e Product description. "
                "Usa solo testo realmente visibile nel documento. Non inventare, non inferire, non normalizzare. "
                "Se un campo non e chiaramente leggibile, restituisci null. "
                "Campi core da estrarre. "
                "numero_certificato: estrai il numero certificato dal campo No. "
                "ordine_cliente: estrai il valore del campo Customer Order No. "
                "articolo: estrai il valore del campo Impol product code o di un campo equivalente che identifica chiaramente il product code. "
                "lega: estrai la lega o stato dal blocco Product description. "
                "descrizione_profilo_cliente: per questo fornitore usa null se non esiste un vero campo equivalente a una descrizione profilo cliente separata; non inventare un codice cliente. "
                "colata: estrai il valore del campo Charge della riga misurata. "
                "peso_netto: estrai il valore del campo Netto o di un campo equivalente che indica chiaramente il peso netto del materiale; "
                "il valore puo essere un numero con o senza unita; considera valido il numero piu vicino al label nella stessa riga, cella o area visiva; "
                "non confondere questo campo con altri pesi o valori tabellari; non restituire null se il label e presente e un numero e chiaramente associato nella stessa area. "
                "Campi runtime di supporto da estrarre inoltre. "
                "packing_list_no: estrai il valore del campo Packing list No. "
                "supplier_order_no: estrai il valore del campo Supplier Order No. "
                "product_description_raw: estrai l'intero contenuto raw del blocco Product description; se il contenuto e spezzato su piu righe ma appartiene allo stesso blocco o cella, unisci le righe con uno spazio. "
                "diameter_raw: estrai il diametro dal blocco Product description se compare come DIA. "
                "Chimica: usa solo Si, Fe, Cu, Mn, Mg, Cr, Ni, Zn, Ti, Pb, V, Bi, Sn, Zr, Be, Zr+Ti, Mn+Cr, Bi+Pb; restituisci solo i valori misurati veri e ignora Min e Max. "
                "Proprieta meccaniche: considera Rm, Rp0.2, A%, HB, IACS%, Rp0.2/Rm; non usare Min o Max; se ci sono piu righe misurate vere, restituisci tutte le righe misurate raw. "
                "Note: verifica solo nota_us_control_classe, nota_rohs, nota_radioactive_free. "
                "Restituisci solo JSON con questa struttura: "
                "{\"core\":{\"numero_certificato\":\"string|null\",\"ordine_cliente\":\"string|null\",\"articolo\":\"string|null\","
                "\"lega\":\"string|null\",\"descrizione_profilo_cliente\":\"string|null\",\"colata\":\"string|null\",\"peso_netto\":\"string|null\","
                "\"packing_list_no\":\"string|null\",\"supplier_order_no\":\"string|null\",\"product_description_raw\":\"string|null\",\"diameter_raw\":\"string|null\"},"
                "\"chemistry_raw\":{\"Si\":\"string|null\",\"Fe\":\"string|null\",\"Cu\":\"string|null\",\"Mn\":\"string|null\",\"Mg\":\"string|null\","
                "\"Cr\":\"string|null\",\"Ni\":\"string|null\",\"Zn\":\"string|null\",\"Ti\":\"string|null\",\"Pb\":\"string|null\",\"V\":\"string|null\","
                "\"Bi\":\"string|null\",\"Sn\":\"string|null\",\"Zr\":\"string|null\",\"Be\":\"string|null\",\"Zr+Ti\":\"string|null\",\"Mn+Cr\":\"string|null\","
                "\"Bi+Pb\":\"string|null\"},"
                "\"mechanical_raw\":{\"measured_rows\":[{\"Rm\":\"string|null\",\"Rp0.2\":\"string|null\",\"A%\":\"string|null\",\"HB\":\"string|null\","
                "\"IACS%\":\"string|null\",\"Rp0.2/Rm\":\"string|null\"}]},"
                "\"notes_raw\":{\"nota_us_control_classe_raw\":\"string|null\",\"nota_rohs_raw\":\"string|null\",\"nota_radioactive_free_raw\":\"string|null\"}}"
            ),
        }
    ]

    for image_label, crop in page_images.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Image label: {image_label}; "
                    f"page_number: {crop.get('page_number') or 'unknown'}"
                ),
            }
        )
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{encoded}", "detail": "high"})

    try:
        response = client.responses.create(
            model=settings.document_vision_model,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Impol certificate AI extraction request failed") from exc

    return _parse_openai_json_payload_for_certificate_bundle(response.output_text)


def _normalize_impol_certificate_ai_payload(
    page_images: dict[str, dict[str, str | int]],
    raw_payload: dict[str, object],
) -> dict[str, object]:
    first_page_crop = next(iter(page_images.values()), None)
    first_page_id = int(first_page_crop.get("page_id")) if first_page_crop and first_page_crop.get("page_id") else 0
    last_page_crop = next(reversed(page_images.values()), None) if page_images else None
    last_page_id = int(last_page_crop.get("page_id")) if last_page_crop and last_page_crop.get("page_id") else first_page_id

    core_payload = cast(dict[str, object], raw_payload.get("core") or {})
    core_fields = _sanitize_impol_vision_certificate_fields(core_payload, next(iter(page_images.keys()), None))

    chemistry_payload = cast(dict[str, object], raw_payload.get("chemistry_raw") or {})
    chemistry_matches = _normalize_vision_numeric_matches(
        {
            field_name: {
                "value": _string_or_none(chemistry_payload.get(field_name)),
                "evidence": _string_or_none(chemistry_payload.get(field_name)),
                "source_crop": next(iter(page_images.keys()), None),
            }
            for field_name in ("Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Ni", "Zn", "Ti", "Pb", "V", "Bi", "Sn", "Zr", "Be", "Zr+Ti", "Mn+Cr", "Bi+Pb")
        },
        {
            next(iter(page_images.keys()), "page1"): {
                "page_id": first_page_id,
                "page_number": first_page_crop.get("page_number") if first_page_crop else 1,
            }
        },
    )

    measured_rows_payload = cast(dict[str, object], raw_payload.get("mechanical_raw") or {}).get("measured_rows") or []
    property_matches = _normalize_aluminium_bozen_measured_rows_payload(
        measured_rows_payload if isinstance(measured_rows_payload, list) else [],
        page_id=first_page_id,
    )

    notes_payload = cast(dict[str, object], raw_payload.get("notes_raw") or {})
    note_matches = _normalize_vision_note_matches(
        {
            "nota_us_control_classe": {
                "value": _string_or_none(notes_payload.get("nota_us_control_classe_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_us_control_classe_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
            "nota_rohs": {
                "value": _string_or_none(notes_payload.get("nota_rohs_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_rohs_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
            "nota_radioactive_free": {
                "value": _string_or_none(notes_payload.get("nota_radioactive_free_raw")),
                "evidence": _string_or_none(notes_payload.get("nota_radioactive_free_raw")),
                "source_crop": next(reversed(page_images.keys()), None) if page_images else None,
            },
        },
        {
            next(reversed(page_images.keys()), "page1"): {
                "page_id": last_page_id,
                "page_number": last_page_crop.get("page_number") if last_page_crop else (first_page_crop.get("page_number") if first_page_crop else 1),
            }
        },
    )

    packing_list_raw = _string_or_none(core_payload.get("packing_list_no"))
    customer_order_raw = _string_or_none(core_payload.get("ordine_cliente"))
    supplier_order_raw = _string_or_none(core_payload.get("supplier_order_no"))
    article_raw = _string_or_none(core_payload.get("articolo"))
    product_description_raw = _string_or_none(core_payload.get("product_description_raw"))
    diameter_raw = _string_or_none(core_payload.get("diameter_raw")) or product_description_raw
    cast_raw = _string_or_none(core_payload.get("colata"))
    weight_raw = _string_or_none(core_payload.get("peso_netto"))

    return {
        "match_values": {
            field_name: _string_or_none(field_payload.get("value"))
            for field_name, field_payload in core_fields.items()
        },
        "supplier_fields": {
            "packing_list_no": normalize_impol_packing_list_root(packing_list_raw),
            "customer_order_no": _extract_token_from_value_or_evidence(customer_order_raw, customer_order_raw, r"\b\d{1,6}\b"),
            "supplier_order_no": _extract_token_from_value_or_evidence(supplier_order_raw, supplier_order_raw, r"\b\d{3,6}/\d{1,2}\b"),
            "product_code": _normalize_impol_product_code(article_raw),
            "product_description_raw": product_description_raw,
            "charge": _extract_token_from_value_or_evidence(cast_raw, cast_raw, r"\b\d{6}\b", disallow={"10204"}),
            "diameter": _normalize_impol_diameter_from_text(diameter_raw),
            "net_weight": _normalize_numeric_value(weight_raw),
        },
        "core_fields": core_fields,
        "chemistry": chemistry_matches,
        "properties": property_matches,
        "notes": note_matches,
        "debug_raw_output": json.dumps(raw_payload, ensure_ascii=False),
    }


def _sanitize_impol_vision_certificate_fields(
    core_payload: dict[str, object],
    source_crop: str | None,
) -> dict[str, dict[str, str | None]]:
    certificate_raw = _string_or_none(core_payload.get("numero_certificato"))
    order_raw = _string_or_none(core_payload.get("ordine_cliente"))
    article_raw = _string_or_none(core_payload.get("articolo"))
    alloy_raw = _string_or_none(core_payload.get("lega")) or _string_or_none(core_payload.get("product_description_raw"))
    cast_raw = _string_or_none(core_payload.get("colata"))
    weight_raw = _string_or_none(core_payload.get("peso_netto"))
    diameter_raw = _string_or_none(core_payload.get("diameter_raw")) or _string_or_none(core_payload.get("product_description_raw"))

    def _payload(value: str | None) -> dict[str, str | None]:
        return {
            "value": value,
            "evidence": value,
            "source_crop": source_crop,
        }

    return {
        "numero_certificato_certificato": _payload(
            _extract_token_from_value_or_evidence(
                certificate_raw,
                certificate_raw,
                r"\b\d{1,6}\s*[/-]?\s*[A-Z0-9]{0,2}\b",
                disallow={"10204"},
            )
        ),
        "articolo_certificato": _payload(_normalize_impol_product_code(article_raw)),
        "codice_cliente_certificato": _payload(None),
        "ordine_cliente_certificato": _payload(
            _extract_token_from_value_or_evidence(order_raw, order_raw, r"\b\d{1,6}\b")
        ),
        "lega_certificato": _payload(_normalize_impol_alloy_from_text(alloy_raw)),
        "diametro_certificato": _payload(_normalize_impol_diameter_from_text(diameter_raw)),
        "colata_certificato": _payload(
            _extract_token_from_value_or_evidence(cast_raw, cast_raw, r"\b\d{6}\b", disallow={"10204"})
        ),
        "peso_certificato": _payload(_normalize_numeric_value(weight_raw)),
    }


def _normalize_impol_product_code(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\b(\d{6})(?:/\d)?\b", cleaned.upper())
    if match is None:
        return None
    return match.group(1)


def _normalize_aluminium_bozen_measured_rows_payload(
    measured_rows_payload: list[object],
    *,
    page_id: int,
) -> dict[str, dict[str, str | int]]:
    candidates: dict[str, list[tuple[float, str]]] = {}
    snippets: dict[str, str] = {}
    for raw_row in measured_rows_payload:
        if not isinstance(raw_row, dict):
            continue
        snippet_parts: list[str] = []
        for field_name in ("Rm", "Rp0.2", "A%", "HB", "IACS%", "Rp0.2/Rm"):
            raw_value = _string_or_none(raw_row.get(field_name))
            if raw_value is None:
                continue
            standardized = _normalize_numeric_value(raw_value)
            if standardized is None:
                continue
            try:
                numeric_value = float(standardized)
            except ValueError:
                continue
            candidates.setdefault(field_name, []).append((numeric_value, standardized))
            snippet_parts.append(f"{field_name}={raw_value}")
        if snippet_parts:
            snippet = " ".join(snippet_parts)
            for field_name in ("Rm", "Rp0.2", "A%", "HB", "IACS%", "Rp0.2/Rm"):
                if _string_or_none(raw_row.get(field_name)) is not None:
                    snippets.setdefault(field_name, snippet)

    normalized: dict[str, dict[str, str | int]] = {}
    for field_name, values in candidates.items():
        values.sort(key=lambda item: item[0])
        _, chosen = values[0]
        normalized[field_name] = {
            "page_id": page_id,
            "snippet": snippets.get(field_name, chosen),
            "raw": chosen,
            "standardized": chosen,
            "final": chosen,
            "method": "chatgpt",
        }
    return normalized


def _apply_aluminium_bozen_certificate_ai_payload(
    db: Session,
    *,
    row: AcquisitionRow,
    payload: dict[str, object],
    actor_id: int,
) -> None:
    certificate_document = get_document(db, row.document_certificato_id)
    raw_payload_text = _string_or_none(cast(dict[str, object], payload).get("debug_raw_output"))
    if raw_payload_text:
        _create_ai_payload_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=certificate_document.pages[0].id if certificate_document.pages else None,
            blocco="match",
            payload_text=raw_payload_text,
            actor_id=actor_id,
            confidence=0.77,
        )
    core_fields = cast(dict[str, dict[str, str | None]], payload.get("core_fields") or {})
    for field_name, field_payload in core_fields.items():
        field_value = _string_or_none(field_payload.get("value"))
        if field_value is None or _has_stable_value_protected_from_ai(row, "match", field_name):
            continue
        evidence = _string_or_none(field_payload.get("evidence")) or field_value
        evidence_model = _create_text_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=certificate_document.pages[0].id if certificate_document.pages else None,
            blocco="match",
            snippet=evidence,
            actor_id=actor_id,
            confidence=0.77,
        )
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="match",
            campo=field_name,
            valore_grezzo=field_value,
            valore_standardizzato=field_value,
            valore_finale=field_value,
            stato="proposto",
            document_evidence_id=evidence_model.id,
            metodo_lettura="chatgpt",
            fonte_documentale="certificato",
            confidenza=0.77,
            actor_id=actor_id,
        )

    for block_name, confidence in (("chemistry", 0.76), ("properties", 0.74), ("notes", 0.74)):
        block_key = {"chemistry": "chimica", "properties": "proprieta", "notes": "note"}[block_name]
        matches = cast(dict[str, dict[str, str | int]], payload.get(block_name) or {})
        if not matches:
            continue
        _prune_unconfirmed_block_values(db=db, row_id=row.id, block=block_key, keep_fields=set(matches.keys()))
        for field_name, match in matches.items():
            snippet = _string_or_none(cast(dict[str, object], match).get("snippet")) or _string_or_none(cast(dict[str, object], match).get("final")) or ""
            page_id = cast(dict[str, object], match).get("page_id")
            evidence = _create_text_evidence(
                db=db,
                row_id=row.id,
                document_id=certificate_document.id,
                document_page_id=int(page_id) if page_id else None,
                blocco=block_key,
                snippet=snippet,
                actor_id=actor_id,
                confidence=confidence,
            )
            _upsert_read_value_model(
                db=db,
                acquisition_row_id=row.id,
                blocco=block_key,
                campo=field_name,
                valore_grezzo=_string_or_none(cast(dict[str, object], match).get("raw")) or _string_or_none(cast(dict[str, object], match).get("final")),
                valore_standardizzato=_string_or_none(cast(dict[str, object], match).get("standardized")) or _string_or_none(cast(dict[str, object], match).get("final")),
                valore_finale=_string_or_none(cast(dict[str, object], match).get("final")),
                stato="proposto",
                document_evidence_id=evidence.id,
                metodo_lettura="chatgpt",
                fonte_documentale="certificato",
                confidenza=confidence,
                actor_id=actor_id,
            )

    _sync_row_from_match_values(db, row)
    _sync_row_statuses(db, row)
    db.add(row)


def _supplier_supports_ai_vision_pipeline(supplier_key: str | None) -> bool:
    return supplier_key in {"aluminium_bozen", "impol"}


def _get_supplier_certificate_ai_payload(
    db: Session,
    *,
    supplier_key: str | None,
    certificate_document: Document,
    openai_api_key: str,
    certificate_ai_cache: dict[int, dict[str, object]] | None = None,
) -> dict[str, object]:
    if supplier_key == "aluminium_bozen":
        return _get_aluminium_bozen_certificate_ai_payload(
            db=db,
            certificate_document=certificate_document,
            openai_api_key=openai_api_key,
            certificate_ai_cache=certificate_ai_cache,
        )
    if supplier_key == "impol":
        return _get_impol_certificate_ai_payload(
            db=db,
            certificate_document=certificate_document,
            openai_api_key=openai_api_key,
            certificate_ai_cache=certificate_ai_cache,
        )
    return {
        "match_values": {},
        "supplier_fields": {},
        "chemistry": {},
        "properties": {},
        "notes": {},
    }


def _extract_supplier_ddt_row_groups_with_vision(
    db: Session,
    *,
    supplier_key: str | None,
    ddt_document: Document,
    openai_api_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if supplier_key == "aluminium_bozen":
        return _extract_aluminium_bozen_ddt_row_groups_with_vision(
            db=db,
            ddt_document=ddt_document,
            openai_api_key=openai_api_key,
        )
    if supplier_key == "impol":
        return _extract_impol_ddt_row_groups_with_vision(
            db=db,
            ddt_document=ddt_document,
            openai_api_key=openai_api_key,
        )
    return []


def _apply_supplier_ai_candidate_to_row(
    db: Session,
    *,
    row: AcquisitionRow,
    ai_candidate: ReaderRowSplitCandidateResponse,
    actor_id: int,
    document_id: int,
) -> bool:
    if ai_candidate.supplier_key == "impol":
        return _apply_impol_ai_candidate_to_row(
            db=db,
            row=row,
            ai_candidate=ai_candidate,
            actor_id=actor_id,
            document_id=document_id,
        )
    return _apply_aluminium_bozen_ai_candidate_to_row(
        db=db,
        row=row,
        ai_candidate=ai_candidate,
        actor_id=actor_id,
        document_id=document_id,
    )


def _apply_supplier_certificate_ai_payload(
    db: Session,
    *,
    row: AcquisitionRow,
    payload: dict[str, object],
    actor_id: int,
) -> None:
    _apply_aluminium_bozen_certificate_ai_payload(
        db=db,
        row=row,
        payload=payload,
        actor_id=actor_id,
    )


def _parse_openai_json_payload_for_fields(payload: str, field_names: list[str]) -> dict[str, dict[str, str | None]]:
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from vision extraction")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from vision extraction") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected vision payload structure")

    normalized: dict[str, dict[str, str | None]] = {}
    for field_name in field_names:
        raw_field = data.get(field_name) or {}
        if not isinstance(raw_field, dict):
            raw_field = {"value": _string_or_none(raw_field), "evidence": None, "source_crop": None}
        normalized[field_name] = {
            "value": _string_or_none(raw_field.get("value")),
            "evidence": _string_or_none(raw_field.get("evidence")),
            "source_crop": _string_or_none(raw_field.get("source_crop")),
        }
    return normalized


def _parse_openai_json_payload(payload: str) -> dict[str, dict[str, str | None]]:
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from vision extraction")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from vision extraction") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected vision payload structure")

    normalized: dict[str, dict[str, str | None]] = {}
    for field_name in ("numero_certificato_ddt", "cdq", "colata", "peso", "diametro", "ordine"):
        raw_field = data.get(field_name) or {}
        if not isinstance(raw_field, dict):
            raw_field = {"value": _string_or_none(raw_field), "evidence": None, "source_crop": None}
        normalized[field_name] = {
            "value": _string_or_none(raw_field.get("value")),
            "evidence": _string_or_none(raw_field.get("evidence")),
            "source_crop": _string_or_none(raw_field.get("source_crop")),
        }
    return normalized


def _sanitize_vision_ddt_fields(
    extracted: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    normalized = {field: value.copy() for field, value in extracted.items()}

    ddt_value = _sanitize_ddt_number_candidate(
        _string_or_none(normalized.get("ddt", {}).get("value")),
        _string_or_none(normalized.get("ddt", {}).get("evidence")),
    )
    if "ddt" in normalized:
        normalized["ddt"]["value"] = ddt_value

    cdq_value = _string_or_none(normalized.get("cdq", {}).get("value"))
    cdq_evidence = _string_or_none(normalized.get("cdq", {}).get("evidence"))
    if cdq_value is not None and _looks_like_invalid_cdq(cdq_value, cdq_evidence):
        normalized["cdq"] = {
            "value": None,
            "evidence": cdq_evidence,
            "source_crop": _string_or_none(normalized.get("cdq", {}).get("source_crop")),
        }

    cert_value = _string_or_none(normalized.get("numero_certificato_ddt", {}).get("value"))
    cert_evidence = _string_or_none(normalized.get("numero_certificato_ddt", {}).get("evidence"))
    cert_source_crop = _string_or_none(normalized.get("numero_certificato_ddt", {}).get("source_crop"))
    if cert_value is not None:
        cert_value = _extract_token_from_value_or_evidence(
            cert_value,
            cert_evidence,
            r"\b\d{4,7}[A-Z]?\b",
            disallow={"10204"},
        )
        if cert_value is not None and _looks_like_invalid_cdq(cert_value, cert_evidence):
            cert_value = None
    if "numero_certificato_ddt" in normalized:
        normalized["numero_certificato_ddt"] = {
            "value": cert_value,
            "evidence": cert_evidence,
            "source_crop": cert_source_crop,
        }

    peso_value = _string_or_none(normalized.get("peso", {}).get("value"))
    peso_evidence = _string_or_none(normalized.get("peso", {}).get("evidence"))
    peso_source_crop = _string_or_none(normalized.get("peso", {}).get("source_crop"))
    if peso_value is not None and _looks_like_unreliable_weight(peso_value, peso_evidence, peso_source_crop):
        normalized["peso"] = {
            "value": None,
            "evidence": peso_evidence,
            "source_crop": peso_source_crop,
        }

    ordine_value = _string_or_none(normalized.get("ordine", {}).get("value"))
    ordine_evidence = _string_or_none(normalized.get("ordine", {}).get("evidence"))
    if ordine_value is not None:
        ordine_value = _normalize_order_from_evidence(ordine_value, ordine_evidence)
        normalized["ordine"]["value"] = ordine_value
    if ordine_value is not None and _looks_like_unreliable_order(ordine_value, ordine_evidence):
        normalized["ordine"] = {
            "value": None,
            "evidence": ordine_evidence,
            "source_crop": _string_or_none(normalized.get("ordine", {}).get("source_crop")),
        }

    customer_order_value = _string_or_none(normalized.get("customer_order_no", {}).get("value"))
    customer_order_evidence = _string_or_none(normalized.get("customer_order_no", {}).get("evidence"))
    customer_order_source_crop = _string_or_none(normalized.get("customer_order_no", {}).get("source_crop"))
    if customer_order_value is not None:
        customer_order_value = _normalize_customer_order_tokens(customer_order_value) or _normalize_customer_order_tokens(customer_order_evidence)
        if not _is_normalized_customer_order(customer_order_value):
            customer_order_value = None
    if "customer_order_no" in normalized:
        normalized["customer_order_no"] = {
            "value": customer_order_value,
            "evidence": customer_order_evidence,
            "source_crop": customer_order_source_crop,
        }

    customer_code_value = _string_or_none(normalized.get("customer_code", {}).get("value"))
    customer_code_evidence = _string_or_none(normalized.get("customer_code", {}).get("evidence"))
    customer_code_source_crop = _string_or_none(normalized.get("customer_code", {}).get("source_crop"))
    if customer_code_value is not None:
        customer_code_value = _extract_token_from_value_or_evidence(
            customer_code_value,
            customer_code_evidence,
            r"\bA\d[0-9A-Z]{4,}\b",
        )
    if "customer_code" in normalized:
        normalized["customer_code"] = {
            "value": customer_code_value,
            "evidence": customer_code_evidence,
            "source_crop": customer_code_source_crop,
        }

    article_code_value = _string_or_none(normalized.get("article_code", {}).get("value"))
    article_code_evidence = _string_or_none(normalized.get("article_code", {}).get("evidence"))
    article_code_source_crop = _string_or_none(normalized.get("article_code", {}).get("source_crop"))
    if article_code_value is not None:
        article_code_value = _extract_token_from_value_or_evidence(
            article_code_value,
            article_code_evidence,
            r"\b14BT[0-9A-Z-]+\b",
        )
    if "article_code" in normalized:
        normalized["article_code"] = {
            "value": article_code_value,
            "evidence": article_code_evidence,
            "source_crop": article_code_source_crop,
        }

    colata_value = _string_or_none(normalized.get("colata", {}).get("value"))
    colata_evidence = _string_or_none(normalized.get("colata", {}).get("evidence"))
    colata_source_crop = _string_or_none(normalized.get("colata", {}).get("source_crop"))
    if colata_value is not None:
        colata_value = _extract_token_from_value_or_evidence(
            colata_value,
            colata_evidence,
            r"\b(?:[A-Z]\d{5,}[A-Z]?|\d{5,}[A-Z]\d|\d{5,}[A-Z]|\d{5,})\b",
            disallow={"10204"},
        )
    if "colata" in normalized:
        normalized["colata"] = {
            "value": colata_value,
            "evidence": colata_evidence,
            "source_crop": colata_source_crop,
        }

    return normalized


def _extract_token_with_regex(
    text: str,
    pattern: str,
    *,
    disallow: set[str] | None = None,
) -> str | None:
    disallow_set = {token.upper() for token in (disallow or set())}
    for match in re.finditer(pattern, text.upper()):
        token = match.group(0).strip().upper()
        if token in disallow_set:
            continue
        return token
    return None


def _extract_token_from_value_or_evidence(
    value: str | None,
    evidence: str | None,
    pattern: str,
    *,
    disallow: set[str] | None = None,
) -> str | None:
    if value:
        token = _extract_token_with_regex(value, pattern, disallow=disallow)
        if token is not None:
            return token
    if evidence:
        return _extract_token_with_regex(evidence, pattern, disallow=disallow)
    return None


def _sanitize_ddt_number_candidate(value: str | None, evidence: str | None) -> str | None:
    token = _extract_token_from_value_or_evidence(value, evidence, r"\b\d{1,6}\b")
    if token is None:
        return None
    if token in {"0", "10204"}:
        return None
    return token


def _sanitize_impol_ddt_number_candidate(value: str | None, evidence: str | None) -> str | None:
    for haystack in (value, evidence):
        cleaned = _string_or_none(haystack)
        if cleaned is None:
            continue
        match = re.search(r"\b(\d{1,6}-\d{1,2})\b", cleaned)
        if match is not None:
            return match.group(1)
    return _sanitize_ddt_number_candidate(value, evidence)


def _looks_like_invalid_cdq(value: str, evidence: str | None) -> bool:
    haystack = f"{value} {evidence or ''}".lower()
    invalid_markers = (
        "en 10204",
        "inspection certificate",
        "astm",
        "ams",
        "class a",
        "class b",
        "classe a",
        "classe b",
    )
    return any(marker in haystack for marker in invalid_markers)


def _looks_like_unreliable_weight(value: str, evidence: str | None, source_crop: str | None) -> bool:
    haystack = f"{value} {evidence or ''}".lower()
    if any(marker in haystack for marker in ("totale", "total", "packing list", "colli", "imballi")):
        return True
    if source_crop and source_crop.endswith("_lower") and evidence and "peso netto" in haystack and "barra" not in haystack:
        return True
    return False


def _looks_like_unreliable_order(value: str, evidence: str | None) -> bool:
    normalized_value = value.strip().upper()
    if len(normalized_value) < 6:
        return True
    if not re.search(r"\d{4,}", normalized_value):
        return True
    if evidence:
        normalized_evidence = evidence.lower()
        if not any(marker in normalized_evidence for marker in ("ord", "odv", "ordine", "order", "rif")):
            return True
    return False


def _normalize_order_from_evidence(value: str, evidence: str | None) -> str:
    if not evidence:
        return value

    candidates = []
    for raw_candidate in re.findall(r"\d[\d./-]{5,}", evidence):
        candidate = raw_candidate.strip(" .,-")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            continue
        if re.fullmatch(r"20\d{2}\.\d{6,}(?:\.\d+)+", candidate):
            candidate = candidate.split(".", 1)[1]
        candidates.append(candidate)

    if not candidates:
        return value

    candidates.sort(key=lambda item: (sum(char.isdigit() for char in item), len(item)))
    return candidates[-1]


def _can_replace_row_field(row: AcquisitionRow, field_name: str) -> bool:
    current_value = getattr(row, field_name)
    if current_value is None:
        return True

    for value in row.values:
        if value.blocco != "ddt" or value.campo != field_name:
            continue
        if value.metodo_lettura == "chatgpt" and value.stato != "confermato":
            return True
    return False


def _has_stable_value_protected_from_ai(row: AcquisitionRow, block: str, field_name: str) -> bool:
    aliases = _ai_guardrail_field_aliases(block, field_name)
    for value in row.values:
        if value.blocco != block or value.campo not in aliases:
            continue
        if value.metodo_lettura == "chatgpt" and value.stato != "confermato":
            continue
        if _final_value_for_row(value) is not None:
            return True
    if block == "ddt":
        return _ddt_row_field_fallback_value(row, field_name) is not None
    return False


def _extract_stable_aluminium_bozen_row_supplier_fields_for_match(
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
) -> dict[str, str | None]:
    article = _string_or_none(ddt_values.get("article_code"))
    if not _has_stable_value_protected_from_ai(row, "ddt", "article_code"):
        article = None

    customer_code = _string_or_none(ddt_values.get("customer_code"))
    if not _has_stable_value_protected_from_ai(row, "ddt", "customer_code"):
        customer_code = None

    customer_order = _string_or_none(ddt_values.get("customer_order_no"))
    if not _has_stable_value_protected_from_ai(row, "ddt", "customer_order_no"):
        customer_order = None

    return {
        "article": article,
        "customer_code": customer_code,
        "customer_order_normalized": customer_order,
    }


def _ai_guardrail_field_aliases(block: str, field_name: str) -> tuple[str, ...]:
    if block == "ddt":
        if field_name in {"cdq", "numero_certificato_ddt"}:
            return ("cdq", "numero_certificato_ddt")
        if field_name == "ordine":
            return ("ordine", "customer_order_no")
        return (field_name,)
    return (field_name,)


def _ddt_row_field_fallback_value(row: AcquisitionRow, field_name: str) -> str | None:
    if field_name in {"cdq", "numero_certificato_ddt"}:
        return _string_or_none(row.cdq)
    if field_name == "colata":
        return _string_or_none(row.colata)
    if field_name == "peso":
        return _normalize_value_for_field("ddt", "peso", row.peso)
    if field_name == "diametro":
        return _normalize_value_for_field("ddt", "diametro", row.diametro)
    if field_name == "ordine":
        return _string_or_none(row.ordine)
    if field_name == "ddt":
        return _string_or_none(row.ddt)
    if field_name == "lega":
        return _string_or_none(row.lega_base)
    return None


def _normalize_aluminium_bozen_customer_code_token(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    token = cleaned.upper()
    if not token.startswith("A"):
        return token
    normalized_chars = [token[0]]
    for char in token[1:]:
        if char in {"O", "Q", "D"}:
            normalized_chars.append("0")
        elif char == "I":
            normalized_chars.append("1")
        else:
            normalized_chars.append(char)
    return "".join(normalized_chars)


def _is_revisable_chatgpt_ddt_value(row: AcquisitionRow, field_name: str) -> bool:
    for value in row.values:
        if value.blocco != "ddt" or value.campo != field_name:
            continue
        if value.metodo_lettura == "chatgpt" and value.stato != "confermato":
            return True
    return False


def _is_revisable_chatgpt_match_value(row: AcquisitionRow, field_name: str) -> bool:
    for value in row.values:
        if value.blocco != "match" or value.campo != field_name:
            continue
        if value.metodo_lettura == "chatgpt" and value.stato != "confermato":
            return True
    return False


def _sync_row_from_ddt_values(db: Session, row: AcquisitionRow) -> None:
    value_map = {
        value.campo: value
        for value in (
            db.query(ReadValue)
            .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "ddt")
            .all()
        )
    }

    if row.cdq is None and ("cdq" in value_map or "numero_certificato_ddt" in value_map):
        row.cdq = _final_value_for_row(value_map.get("cdq")) or _final_value_for_row(value_map.get("numero_certificato_ddt"))
    if row.colata is None and "colata" in value_map:
        row.colata = _final_value_for_row(value_map.get("colata"))
    if row.peso is None and "peso" in value_map:
        row.peso = _final_value_for_row(value_map.get("peso"))
    if row.diametro is None and "diametro" in value_map:
        row.diametro = _final_value_for_row(value_map.get("diametro"))
    if row.ordine is None and ("customer_order_no" in value_map or "ordine" in value_map):
        row.ordine = _final_value_for_row(value_map.get("customer_order_no")) or _final_value_for_row(value_map.get("ordine"))
    if "ddt" in value_map and row.ddt is None:
        row.ddt = _final_value_for_row(value_map.get("ddt"))
    if "lega" in value_map and row.lega_base is None:
        row.lega_base = _final_value_for_row(value_map.get("lega"))


def _row_ddt_core_field_value(row: AcquisitionRow, field_name: str) -> str | None:
    field_map = {
        "cdq": row.cdq,
        "numero_certificato_ddt": row.cdq,
        "colata": row.colata,
        "diametro": row.diametro,
        "peso": row.peso,
        "ordine": row.ordine,
        "ddt": row.ddt,
    }
    value = field_map.get(field_name)
    if field_name in {"diametro", "peso"}:
        return _normalize_value_for_field("ddt", field_name, value)
    return _string_or_none(value)


def _sync_ddt_values_from_row_fields(db: Session, row: AcquisitionRow, *, actor_id: int) -> None:
    for field_name in ("cdq", "numero_certificato_ddt", "colata", "diametro", "peso", "ordine", "ddt"):
        row_value = _row_ddt_core_field_value(row, field_name)
        if row_value is None:
            continue
        _upsert_read_value_model(
            db=db,
            acquisition_row_id=row.id,
            blocco="ddt",
            campo=field_name,
            valore_grezzo=row_value,
            valore_standardizzato=row_value,
            valore_finale=row_value,
            stato="proposto",
            document_evidence_id=None,
            metodo_lettura="sistema",
            fonte_documentale="ddt",
            confidenza=0.9,
            actor_id=actor_id,
        )


def _sync_row_from_match_values(db: Session, row: AcquisitionRow) -> None:
    value_map = {
        value.campo: value
        for value in (
            db.query(ReadValue)
            .filter(ReadValue.acquisition_row_id == row.id, ReadValue.blocco == "match")
            .all()
        )
    }
    certificate_number = _final_value_for_row(value_map.get("numero_certificato_certificato"))
    if certificate_number is not None:
        row.cdq = certificate_number
    if row.ordine is None and "ordine_cliente_certificato" in value_map:
        row.ordine = _final_value_for_row(value_map.get("ordine_cliente_certificato"))
    if row.lega_base is None and "lega_certificato" in value_map:
        row.lega_base = _final_value_for_row(value_map.get("lega_certificato"))
    if row.diametro is None and "diametro_certificato" in value_map:
        row.diametro = _final_value_for_row(value_map.get("diametro_certificato"))
    if row.colata is None and "colata_certificato" in value_map:
        row.colata = _final_value_for_row(value_map.get("colata_certificato"))
    if row.peso is None and "peso_certificato" in value_map:
        row.peso = _final_value_for_row(value_map.get("peso_certificato"))


def _sync_row_cdq_from_certificate_document(
    db: Session,
    row: AcquisitionRow,
    certificate_document: Document,
) -> None:
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)
    certificate_document = _ensure_document_page_ocr(db, certificate_document)
    certificate_template = resolve_supplier_template(
        row.supplier.ragione_sociale if row.supplier is not None else None,
        row.fornitore_raw,
        row.ddt_document.supplier.ragione_sociale if row.ddt_document and row.ddt_document.supplier else None,
        certificate_document.supplier.ragione_sociale if certificate_document.supplier is not None else None,
    )
    certificate_matches = reader_detect_certificate_core_matches(
        certificate_document.pages,
        supplier_key=certificate_template.supplier_key if certificate_template is not None else None,
    )
    certificate_number = _string_or_none(
        cast(dict[str, object], certificate_matches.get("numero_certificato_certificato") or {}).get("final")
    )
    if certificate_number is not None:
        row.cdq = certificate_number


def _final_value_for_row(value: ReadValue | None) -> str | None:
    if value is None:
        return None
    return _normalize_value_for_field(
        value.blocco,
        value.campo,
        value.valore_finale or value.valore_standardizzato or value.valore_grezzo,
    )


def _read_value_has_payload(value: ReadValue) -> bool:
    return any(
        _string_or_none(candidate) is not None
        for candidate in (
            _normalize_value_for_field(value.blocco, value.campo, value.valore_finale),
            _normalize_value_for_field(value.blocco, value.campo, value.valore_standardizzato),
            _string_or_none(value.valore_grezzo),
        )
    )


def _prune_unconfirmed_block_values(
    db: Session,
    *,
    row_id: int,
    block: str,
    keep_fields: set[str],
) -> None:
    stale_values = (
        db.query(ReadValue)
        .filter(
            ReadValue.acquisition_row_id == row_id,
            ReadValue.blocco == block,
            ReadValue.stato != "confermato",
        )
        .all()
    )
    for value in stale_values:
        if value.campo in keep_fields:
            continue
        value.valore_grezzo = None
        value.valore_standardizzato = None
        value.valore_finale = None
        value.stato = "scartato"
        value.document_evidence_id = None
        value.confidenza = None


def _upsert_read_value_model(
    db: Session,
    *,
    acquisition_row_id: int,
    blocco: str,
    campo: str,
    valore_grezzo: str | None,
    valore_standardizzato: str | None,
    valore_finale: str | None,
    stato: str,
    document_evidence_id: int | None,
    metodo_lettura: str,
    fonte_documentale: str,
    confidenza: float | None,
    actor_id: int,
) -> ReadValue:
    existing = (
        db.query(ReadValue)
        .filter(
            ReadValue.acquisition_row_id == acquisition_row_id,
            ReadValue.blocco == blocco,
            ReadValue.campo == campo,
        )
        .one_or_none()
    )

    before_value = None
    action = "valore_creato"
    if existing is None:
        existing = ReadValue(acquisition_row_id=acquisition_row_id, blocco=blocco, campo=campo)
        db.add(existing)
    else:
        before_value = existing.valore_finale or existing.valore_standardizzato or existing.valore_grezzo
        action = "valore_aggiornato"

    normalized_grezzo = _string_or_none(valore_grezzo)
    normalized_standardizzato = _normalize_value_for_field(blocco, campo, valore_standardizzato)
    normalized_finale = _normalize_value_for_field(blocco, campo, valore_finale)

    if normalized_standardizzato is None and _is_numeric_standardized_field(blocco, campo):
        normalized_standardizzato = _normalize_value_for_field(blocco, campo, normalized_grezzo)
    if normalized_finale is None and normalized_standardizzato is not None:
        normalized_finale = normalized_standardizzato

    existing.valore_grezzo = normalized_grezzo
    existing.valore_standardizzato = normalized_standardizzato
    existing.valore_finale = normalized_finale
    existing.stato = stato
    existing.document_evidence_id = document_evidence_id
    existing.metodo_lettura = metodo_lettura
    existing.fonte_documentale = fonte_documentale
    existing.confidenza = confidenza
    existing.utente_ultima_modifica_id = actor_id
    existing.timestamp_ultima_modifica = datetime.now(UTC)
    db.flush()

    after_value = existing.valore_finale or existing.valore_standardizzato or existing.valore_grezzo
    if before_value != after_value:
        db.add(
            AcquisitionValueHistory(
                acquisition_row_id=acquisition_row_id,
                value_id=existing.id,
                blocco=blocco,
                campo=campo,
                valore_prima=before_value,
                valore_dopo=after_value,
                utente_id=actor_id,
            )
        )

    _record_history_event(
        db=db,
        acquisition_row_id=acquisition_row_id,
        blocco=blocco,
        azione=action,
        user_id=actor_id,
        nota_breve=campo,
    )
    return existing


def normalize_existing_numeric_values(db: Session) -> dict[str, int]:
    updated_values = 0
    updated_rows = 0

    values = db.query(ReadValue).all()
    for value in values:
        if not _is_numeric_standardized_field(value.blocco, value.campo):
            continue

        normalized_standardizzato = _normalize_value_for_field(value.blocco, value.campo, value.valore_standardizzato)
        normalized_finale = _normalize_value_for_field(value.blocco, value.campo, value.valore_finale)

        if normalized_standardizzato is None:
            normalized_standardizzato = _normalize_value_for_field(value.blocco, value.campo, value.valore_grezzo)
        if normalized_finale is None and normalized_standardizzato is not None:
            normalized_finale = normalized_standardizzato

        if value.valore_standardizzato != normalized_standardizzato:
            value.valore_standardizzato = normalized_standardizzato
            updated_values += 1
        if value.valore_finale != normalized_finale:
            value.valore_finale = normalized_finale
            updated_values += 1

    rows = db.query(AcquisitionRow).options(selectinload(AcquisitionRow.values)).all()
    for row in rows:
        ddt_values = {value.campo: value for value in row.values if value.blocco == "ddt"}
        normalized_diametro = _final_value_for_row(ddt_values.get("diametro"))
        normalized_peso = _final_value_for_row(ddt_values.get("peso"))

        if row.diametro != normalized_diametro:
            row.diametro = normalized_diametro
            updated_rows += 1
        if row.peso != normalized_peso:
            row.peso = normalized_peso
            updated_rows += 1

    db.commit()
    return {
        "updated_values": updated_values,
        "updated_rows": updated_rows,
    }


def _create_text_evidence(
    db: Session,
    *,
    row_id: int,
    document_id: int,
    document_page_id: int,
    blocco: str,
    snippet: str,
    actor_id: int,
    confidence: float,
) -> DocumentEvidence:
    evidence = DocumentEvidence(
        document_id=document_id,
        document_page_id=document_page_id,
        acquisition_row_id=row_id,
        blocco=blocco,
        tipo_evidenza="testo",
        bbox=None,
        testo_grezzo=snippet,
        storage_key_derivato=None,
        metodo_estrazione="regex",
        mascherato=False,
        confidenza=confidence,
        utente_creazione_id=actor_id,
    )
    db.add(evidence)
    db.flush()
    return evidence


def _create_ai_payload_evidence(
    db: Session,
    *,
    row_id: int,
    document_id: int,
    document_page_id: int | None,
    blocco: str,
    payload_text: str,
    actor_id: int,
    confidence: float,
) -> DocumentEvidence:
    evidence = DocumentEvidence(
        document_id=document_id,
        document_page_id=document_page_id,
        acquisition_row_id=row_id,
        blocco=blocco,
        tipo_evidenza="ai_payload",
        bbox=None,
        testo_grezzo=payload_text,
        storage_key_derivato=None,
        metodo_estrazione="chatgpt",
        mascherato=True,
        confidenza=confidence,
        utente_creazione_id=actor_id,
    )
    db.add(evidence)
    db.flush()
    return evidence


def _normalize_weight(value: str) -> str:
    return _normalize_decimal_value(value)


def _normalize_decimal_value(value: str) -> str:
    normalized = value.strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", ".")
    return normalized


def _detect_leichtmetall_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    batch_counts: dict[str, tuple[int, int, str]] = {}
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if "ddt" not in matches:
                match = re.search(r"\b(?:delivery\s+note|beleg)\s*:?\s*([0-9]{5,})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1))
            if "ordine" not in matches:
                match = re.search(r"\border\s+confirmation\s+([0-9][0-9./-]{3,})\b", lowered)
                if match is not None:
                    matches["ordine"] = _build_match(page.id, line, match.group(1).replace("/", "-"))
            if "diametro" not in matches:
                match = re.search(r"\bdiameter\s+([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
            if "peso" not in matches:
                match = re.search(r"\bquantity\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*kg\b", lowered)
                if match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))

            batch_match = re.search(r"\b(\d{5})\b\s+\d+\s*$", line)
            if batch_match is not None:
                token = batch_match.group(1)
                count, page_id, snippet = batch_counts.get(token, (0, page.id, line))
                batch_counts[token] = (count + 1, page_id, snippet)

    if "colata" not in matches and batch_counts:
        token, (count, page_id, snippet) = max(batch_counts.items(), key=lambda item: item[1][0])
        if count >= 2:
            matches["colata"] = _build_match(page_id, snippet, token)
    return matches


def _detect_metalba_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    cast_counts: dict[str, tuple[int, int, str]] = {}
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if "ddt" not in matches:
                match = re.search(r"\bddt\s*([0-9]{2}[-/][0-9]{5})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1).replace("/", "-").upper())
            if "diametro" not in matches:
                match = re.search(r"\bbarra\s+tonda\s+diam\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
            if "peso" not in matches:
                match = re.search(r"\bpeso\s+netto\s+kg\s*([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\b", lowered)
                if match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))

            cast_match = re.search(r"\b([0-9]{5}[a-z])\b", lowered)
            if cast_match is not None and "colate" not in lowered and "kg" not in lowered:
                token = cast_match.group(1).upper()
                count, page_id, snippet = cast_counts.get(token, (0, page.id, line))
                cast_counts[token] = (count + 1, page_id, snippet)

    if "colata" not in matches and cast_counts:
        token, (count, page_id, snippet) = max(cast_counts.items(), key=lambda item: item[1][0])
        if count >= 2:
            matches["colata"] = _build_match(page_id, snippet, token)
    return matches


def _detect_aww_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    position_count = 0
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if re.match(r"^\d{3}\s+[a-z0-9-]{4,}", lowered):
                position_count += 1
            if "ddt" not in matches:
                match = re.search(r"\bdelivery\s+note\s+([0-9]{5,})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1))
            if "ordine" not in matches:
                match = re.search(r"\border\s+confirmation\s*:\s*([0-9][0-9-]{5,})\b", lowered)
                if match is not None:
                    matches["ordine"] = _build_match(page.id, line, match.group(1))

    if position_count <= 1:
        for page in pages:
            for line in _page_lines(page):
                lowered = line.casefold()
                if "diametro" not in matches:
                    match = re.search(r"\bouter\s+di\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                    if match is not None:
                        matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
                if "peso" not in matches:
                    match = re.search(r"\bnet\s+weight\b.*?([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\b", lowered)
                    if match is not None:
                        matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))
    return matches


def _detect_aluminium_bozen_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    packing_section_active = False
    current_cert_number: str | None = None

    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()

            if "ddt" not in matches:
                ddt_match = _extract_ddt_number_from_line(lowered)
                if ddt_match is not None:
                    matches["ddt"] = _build_match(page.id, line, ddt_match)

            if "ordine" not in matches:
                order_match = re.search(r"\brif\.\s*ns\.\s*odv\s*n\.?\s*([0-9]+(?:[./][0-9]+)?)", lowered)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1).replace("/", "."))

            if "diametro" not in matches:
                diameter_match = re.search(r"\bbarra\s+tonda\s+([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))

            if "colata" not in matches:
                cast_match = re.search(r"\bcast\s+nr\.?\s*([0-9]{6,}[A-Z0-9])\b", normalized, re.IGNORECASE)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1).upper())

            cert_match = re.search(r"\bcert\.\s*n[°o.]?\s*([0-9]{4,})\b", lowered)
            if cert_match is not None:
                current_cert_number = cert_match.group(1)
                if "numero_certificato_ddt" not in matches:
                    matches["numero_certificato_ddt"] = _build_match(page.id, line, current_cert_number)
                packing_section_active = True
                continue

            if packing_section_active:
                if current_cert_number and "numero_certificato_ddt" not in matches and current_cert_number in lowered:
                    matches["numero_certificato_ddt"] = _build_match(page.id, line, current_cert_number)
                if "rif. ordine cliente" in lowered or "articolo" in lowered or "lega stato fisico" in lowered:
                    continue
                if "totali" in lowered:
                    packing_section_active = False
                    continue
                row_match = re.search(
                    r"\b\d{4}-\d{6,}\s+\d+\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,][0-9]+)?)\s+\d+\s+([0-9]{6,}[A-Z0-9]?)\b",
                    normalized,
                    re.IGNORECASE,
                )
                if row_match is not None:
                    if "peso" not in matches:
                        matches["peso"] = _build_match(page.id, line, _normalize_weight(row_match.group(2)))
                    if "colata" not in matches:
                        matches["colata"] = _build_match(page.id, line, row_match.group(3).upper())
                    continue

            if "peso" not in matches:
                inline_weight_match = re.search(r"\bbarra\s+tonda\s+\d+(?:[.,]\d+)?\b.*?\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\)?\s*$", lowered)
                if inline_weight_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(inline_weight_match.group(1)))

    return matches


def _detect_zalco_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()

            if "ddt" not in matches:
                order_line_match = re.search(r"\border\b.*?\b(\d{8})\b.*?\b(0{0,4}\d{5})\b", lowered)
                if order_line_match is not None:
                    matches["ddt"] = _build_match(page.id, line, str(int(order_line_match.group(2))))
            if "ordine" not in matches:
                order_match = re.search(r"\border\b.*?\b(\d{8})\b", lowered)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))
            if "diametro" not in matches:
                diameter_match = re.search(r"\bformat\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
            if "peso" not in matches:
                weight_match = re.search(r"\bpoids\s*net\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if weight_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(weight_match.group(1)))
            if "colata" not in matches:
                cast_match = re.search(r"^\s*(?:\d{4}\s+)?(\d{5})\s+\d{3}\s+\d+\s+[0-9]+", normalized)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1))
    return matches


def _detect_arconic_hannover_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()

            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s+(\d{6,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))

            if "ordine" not in matches:
                customer_po_match = re.search(r"\bcustomer\s+purchase\s+order\s+([0-9][0-9A-Z/-]{1,})\b", normalized, re.IGNORECASE)
                if customer_po_match is not None:
                    matches["ordine"] = _build_match(page.id, line, customer_po_match.group(1).upper())

            if "diametro" not in matches:
                diameter_match = re.search(r"\b(?:die\s*/\s*dimension|die\s*dimension)\s*RD\s*([0-9]+(?:[.,][0-9]+)?)\b", normalized, re.IGNORECASE)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))

            if "colata" not in matches:
                cast_match = re.search(r"\b(C\d{9,})\b", normalized, re.IGNORECASE)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1).upper())

            if "peso" not in matches and "line total" in lowered:
                total_match = re.search(
                    r"\bline\s+total\b.*?\b\d+\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\s+([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\s+\d+\b",
                    normalized,
                    re.IGNORECASE,
                )
                if total_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(total_match.group(2)))

    return matches


def _detect_neuman_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()

            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s+(\d{6,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))

            if "ordine" not in matches:
                order_match = re.search(r"\bcustomer\s+order\s+number\s*:\s*([0-9]{1,6})\b", normalized, re.IGNORECASE)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))

            if "diametro" not in matches:
                diameter_match = re.search(r"\brundstangen\s*:\s*@\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))

    return matches


def _detect_grupa_kety_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    heat_candidates: set[str] = set()

    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()

            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s*:?\s*(\d{4,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))

            if "ordine" not in matches:
                order_match = re.search(r"\bpo\s+number\s+([0-9]{1,6})\b", normalized, re.IGNORECASE)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))

            if "diametro" not in matches:
                diameter_match = re.search(r"\bextruded\s+round\s+bar\s+([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))

            heat_matches = re.findall(r"\b\d{2}[A-Z]-\d{4}\b", normalized, re.IGNORECASE)
            for token in heat_matches:
                heat_candidates.add(token.upper())

    if "colata" not in matches and len(heat_candidates) == 1:
        token = next(iter(heat_candidates))
        page = pages[0]
        matches["colata"] = _build_match(page.id, token, token)

    return matches


def _detect_impol_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    lines: list[str] = []
    first_page_id = pages[0].id if pages else 0

    for page in pages:
        page_lines = _page_lines(page)
        lines.extend(page_lines)
        for line in page_lines:
            normalized = _normalize_mojibake_numeric_text(line).upper()
            if "ddt" in matches:
                continue
            match = re.search(r"\bPACKING\s+LIST(?:[\s_]+)?(\d{1,6})\s*[-/]\s*(\d{1,2})\b", normalized)
            if match is not None:
                document_number = f"{int(match.group(1))}-{int(match.group(2))}"
                matches["ddt"] = _build_match(page.id, line, document_number)

    impol_fields = _extract_impol_match_fields(lines, document_type="ddt")

    if "ordine" not in matches and impol_fields.get("customer_order_no"):
        snippet = _find_impol_field_snippet(lines, "ordine", impol_fields["customer_order_no"])
        matches["ordine"] = _build_match(first_page_id, snippet, impol_fields["customer_order_no"])
    if "colata" not in matches and impol_fields.get("charge"):
        snippet = _find_impol_field_snippet(lines, "colata", impol_fields["charge"])
        matches["colata"] = _build_match(first_page_id, snippet, impol_fields["charge"])
    if "diametro" not in matches and impol_fields.get("diameter"):
        snippet = _find_impol_field_snippet(lines, "diametro", impol_fields["diameter"])
        matches["diametro"] = _build_match(first_page_id, snippet, impol_fields["diameter"])
    if "peso" not in matches and impol_fields.get("net_weight"):
        snippet = _find_impol_field_snippet(lines, "peso", impol_fields["net_weight"])
        matches["peso"] = _build_match(first_page_id, snippet, impol_fields["net_weight"])

    return matches


def _find_impol_field_snippet(lines: list[str], field_name: str, value: str) -> str:
    normalized_value = _normalize_mojibake_numeric_text(value).upper()

    for line in lines:
        normalized_line = _normalize_mojibake_numeric_text(line).upper()
        if field_name == "diametro" and "DIA" in normalized_line and normalized_value in normalized_line:
            return line
        if field_name == "peso" and "POS. TOTAL" in normalized_line:
            return line
        if field_name == "colata" and normalized_value in normalized_line:
            return line
        if field_name == "ordine" and normalized_value in normalized_line:
            return line

    return value


def _extract_supplier_match_fields(
    pages: list[DocumentPage],
    supplier_key: str | None,
    document_type: str,
) -> dict[str, str]:
    if supplier_key is None:
        return {}
    lines: list[str] = []
    for page in pages:
        lines.extend(_page_lines(page))
    if not lines:
        return {}

    supplier_match_extractor = {
        "metalba": lambda current_lines, current_type: (
            {
                "vs_rif": (values := _extract_metalba_ddt_reference_values(current_lines))[0],
                "rif_ord_root": _normalize_commessa_root(values[1]),
            }
            if current_type == "ddt"
            else {
                "ordine_cliente": (values := _extract_metalba_certificate_reference_values(current_lines))[0],
                "commessa_root": _normalize_commessa_root(values[1]),
            }
        ),
        "aww": lambda current_lines, current_type: (
            {
                "your_part_number": _extract_value_near_anchor(current_lines, ("your part number",)),
                "part_number": _extract_code_pattern(current_lines, r"\bP3-\d{5}-\d{4}\b"),
                "order_confirmation_root": _normalize_order_confirmation_root(
                    _extract_value_near_anchor(current_lines, ("batch number (oc)", "batch number oc"))
                ),
            }
            if current_type == "ddt"
            else {
                "kunden_teile_nr": _extract_value_near_anchor(current_lines, ("kunden-teile-nr", "customer part number")),
                "artikel_nr": _extract_value_near_anchor(current_lines, ("artikel-nr", "article no", "article number")),
                "auftragsbestaetigung_root": _normalize_order_confirmation_root(
                    _extract_value_near_anchor(current_lines, ("auftragsbestätigung", "auftragsbestatigung", "order confirmation"))
                ),
            }
        ),
        "aluminium_bozen": lambda current_lines, current_type: {
            "article": _extract_code_pattern(current_lines, r"\b14BT[0-9A-Z-]+\b"),
            "customer_code": _extract_aluminium_bozen_customer_code(current_lines),
            "customer_order_normalized": _extract_aluminium_bozen_customer_order(current_lines, document_type=current_type),
        },
        "zalco": lambda current_lines, current_type: _extract_zalco_match_fields(current_lines, document_type=current_type),
        "arconic_hannover": lambda current_lines, current_type: _extract_arconic_hannover_match_fields(current_lines),
        "neuman": lambda current_lines, current_type: _extract_neuman_match_fields(current_lines),
        "grupa_kety": lambda current_lines, current_type: _extract_grupa_kety_match_fields(current_lines, document_type=current_type),
        "impol": lambda current_lines, current_type: _extract_impol_match_fields(current_lines, document_type=current_type),
    }.get(supplier_key)

    if supplier_match_extractor is None:
        return {}
    return supplier_match_extractor(lines, document_type)


def _extract_value_near_anchor(
    lines: list[str],
    anchors: tuple[str, ...],
    *,
    pattern: str | None = None,
) -> str | None:
    compiled = re.compile(pattern) if pattern else None
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if not any(anchor in lowered for anchor in anchors):
            continue

        same_line_candidate = line
        if compiled is not None:
            match = compiled.search(same_line_candidate)
            if match is not None:
                return match.group(0).strip()
        else:
            extracted = _extract_last_code_token(same_line_candidate)
            if extracted is not None:
                return extracted

        for candidate in lines[index + 1 : min(index + 4, len(lines))]:
            if compiled is not None:
                match = compiled.search(candidate)
                if match is not None:
                    return match.group(0).strip()
            else:
                extracted = _extract_last_code_token(candidate)
                if extracted is not None:
                    return extracted
    return None


def _extract_last_code_token(line: str) -> str | None:
    tokens = re.findall(r"[A-Z0-9][A-Z0-9./-]{2,}", _normalize_mojibake_numeric_text(line).upper())
    for token in reversed(tokens):
        if token not in {"COMMESSA", "ORDINE", "CLIENTE", "CUSTOMER", "PART", "NUMBER", "RIF", "VS"}:
            return token
    return None


def _normalize_commessa_root(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.match(r"(\d+/\d+)", cleaned)
    if match is not None:
        return match.group(1)
    return cleaned.split("/", 1)[0]


def _normalize_order_confirmation_root(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\d{6,}", cleaned)
    if match is None:
        return None
    return match.group(0)


def _extract_code_pattern(lines: list[str], pattern: str) -> str | None:
    compiled = re.compile(pattern)
    for line in lines:
        match = compiled.search(line.upper())
        if match is not None:
            return match.group(0)
    return None


def _extract_aluminium_bozen_customer_code(lines: list[str]) -> str | None:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line).upper()
        match = re.search(r"\bA\d[0-9A-Z]{4,}\b", normalized)
        if match is not None:
            return match.group(0)
    return None


def _extract_aluminium_bozen_customer_order(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            if "VS. ODV" not in line and "VS ODV" not in line and "RIF. ORDINE CLIENTE" not in line:
                continue
            normalized = _normalize_customer_order_tokens(line)
            if _is_normalized_customer_order(normalized):
                return normalized
        return None

    anchors = (
        "CUSTOMER",
        "KUNDENAUFTRAGS",
        "COMMANDE CLIENT",
        "ORDINE CLIENTE",
    )
    for index, line in enumerate(normalized_lines):
        if not any(anchor in line for anchor in anchors):
            continue
        if "CUSTOMER" in line and "ORDER" not in line and "COMMANDE CLIENT" not in line and "ORDINE CLIENTE" not in line:
            continue
        for candidate in normalized_lines[index : min(index + 5, len(normalized_lines))]:
                normalized = _normalize_customer_order_tokens(candidate)
                if _is_normalized_customer_order(normalized):
                    return normalized
    return None


def _extract_zalco_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "tally_sheet_no": _extract_zalco_tally_sheet_number(lines, document_type=document_type),
        "cast_no": _extract_zalco_cast_number(lines),
        "symbol": _extract_zalco_symbol(lines),
        "code_art": _extract_zalco_code_art(lines),
    }


def _extract_zalco_tally_sheet_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bORDER\b.*?\b\d{8}\b.*?\b(0{0,4}\d{5})\b", line)
            if match is not None:
                return str(int(match.group(1)))

    for index, line in enumerate(normalized_lines):
        if "TALLY SHEET" not in line and "NO. AVIS" not in line and "NO. AIS" not in line:
            continue
        match = re.search(r"\b(0{0,4}\d{5})\b", line)
        if match is not None:
            return str(int(match.group(1)))
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"\b(0{0,4}\d{5})\b", candidate)
            if candidate_match is not None:
                return str(int(candidate_match.group(1)))
    return None


def _extract_zalco_cast_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for index, line in enumerate(normalized_lines):
        if "CAST NR" not in line and "COULEE" not in line:
            continue
        match = re.search(r"\b(\d{5})\b", line)
        if match is not None:
            return match.group(1)
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"^\s*(?:\d{4}\s+)?(\d{5})\b", candidate)
            if candidate_match is not None:
                return candidate_match.group(1)
    return None


def _extract_zalco_symbol(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for index, line in enumerate(normalized_lines):
        if "SYMBOLE" in line:
            same_line_match = re.search(r"\bSYMBOLE\s+([0-9]{5,})\b", line)
            if same_line_match is not None:
                return same_line_match.group(1)
            for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
                candidate_match = re.search(r"\b([0-9]{5,})\b", candidate)
                if candidate_match is not None:
                    return candidate_match.group(1)

    for index, line in enumerate(normalized_lines):
        if "CUSTOMER ALLOY CODE" not in line:
            continue
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"\b([0-9]{5,})\b", candidate)
            if candidate_match is not None:
                return candidate_match.group(1)
    return None


def _extract_zalco_code_art(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        match = re.search(r"\bCO(?:DE|PE)(?:\s+ART)?\s*:?\s*([0-9]{4,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_arconic_hannover_match_fields(lines: list[str]) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_arconic_delivery_note(lines),
        "sales_order_number": _extract_value_near_anchor(lines, ("sales order number",), pattern=r"\b\d{6,}\b"),
        "customer_po": _extract_value_near_anchor(lines, ("customer purchase order", "customer p/o"), pattern=r"\b[0-9][0-9A-Z/-]{1,}\b"),
        "arconic_item_number": _extract_value_near_anchor(lines, ("arconic item number", "item no."), pattern=r"\bBG[0-9A-Z]+\b"),
        "cast_job_number": _extract_arconic_cast_job_number(lines),
    }


def _extract_arconic_delivery_note(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(
            r"\bdelivery\s+note(?:\s+no\.?)?\s+(\d{6,})\b",
            _normalize_mojibake_numeric_text(line),
            re.IGNORECASE,
        )
        if match is not None:
            return match.group(1)
    return None


def _extract_arconic_cast_job_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    for index, line in enumerate(normalized_lines):
        if "CAST/JOB NUMBER" in line:
            window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
            normalized = _normalize_arconic_cast_job_tokens(window)
            if normalized is not None:
                return normalized

    for line in normalized_lines:
        if "CAST NUMBER" in line or "PACKAGE" in line or "LINE TOTAL" in line:
            normalized = _normalize_arconic_cast_job_tokens([line])
            if normalized is not None:
                return normalized

    for line in normalized_lines:
        normalized = _normalize_arconic_cast_job_tokens([line])
        if normalized is not None and "|" in normalized:
            return normalized
    return None


def _normalize_arconic_cast_job_tokens(lines: list[str]) -> str | None:
    cast_token: str | None = None
    job_token: str | None = None
    for line in lines:
        if cast_token is None:
            cast_match = re.search(r"\b(C\d{9,})\b", line)
            if cast_match is not None:
                cast_token = cast_match.group(1)
        if job_token is None:
            job_match = re.search(r"\b(\d{8})\b", line)
            if job_match is not None:
                job_token = job_match.group(1)
    if cast_token and job_token:
        return f"{cast_token}|{job_token}"
    return cast_token or job_token


def _extract_neuman_match_fields(lines: list[str]) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_neuman_delivery_note(lines),
        "lot_number": _extract_neuman_lot_number(lines),
        "customer_material_number": _extract_value_near_anchor(
            lines,
            ("customer material number", "art-nr."),
            pattern=r"\bA[0-9A-Z]{5,}\b",
        ),
        "customer_order_number": _extract_value_near_anchor(
            lines,
            ("customer order number",),
            pattern=r"\b[0-9]{1,6}\b",
        ),
    }


def _extract_neuman_delivery_note(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bdelivery\s+note(?:\s*:)?\s*(\d{6,})\b", _normalize_mojibake_numeric_text(line), re.IGNORECASE)
        if match is not None:
            return match.group(1)
    return None


def _extract_neuman_lot_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    lot_candidates: list[str] = []
    for index, line in enumerate(normalized_lines):
        if "LOT" not in line:
            continue
        lot_candidates.extend(re.findall(r"\b(\d{5})\b", line))
        for candidate in normalized_lines[index + 1 : min(index + 3, len(normalized_lines))]:
            lot_candidates.extend(re.findall(r"\b(\d{5})\b", candidate))
    unique_candidates = sorted(set(lot_candidates))
    if len(unique_candidates) == 1:
        return unique_candidates[0]
    return None


def _extract_grupa_kety_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_grupa_kety_delivery_note(lines, document_type=document_type),
        "lot_number": _extract_grupa_kety_lot_number(lines, document_type=document_type),
        "order_no": _extract_grupa_kety_order_no(lines),
        "heat": _extract_grupa_kety_heat(lines),
        "customer_part_number": _extract_grupa_kety_customer_part_number(lines),
    }


def _extract_impol_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "packing_list_no": _extract_impol_packing_list_number(lines, document_type=document_type),
        "customer_order_no": _extract_impol_customer_order_number(lines, document_type=document_type),
        "supplier_order_no": _extract_impol_supplier_order_number(lines, document_type=document_type),
        "product_code": _extract_impol_product_code(lines, document_type=document_type),
        "charge": _extract_impol_charge(lines, document_type=document_type),
        "diameter": _extract_impol_diameter(lines),
        "net_weight": _extract_impol_net_weight(lines, document_type=document_type),
    }


def _extract_impol_packing_list_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bPACKING\s+LIST(?:[\s_]+)?(\d{1,6})\s*[-/]\s*(\d{1,2})\b", line)
            if match is not None:
                return str(int(match.group(1)))

    for line in normalized_lines:
        match = re.search(r"\bPACKING\s+LIST\s+NO\.?\s*:?\s*(\d{1,6})\b", line)
        if match is not None:
            return str(int(match.group(1)))
    return None


def _extract_impol_customer_order_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(lines, ("customer order no.", "customer order no", "customer order"), pattern=r"\b\d{1,6}\b")

    candidates: set[str] = set()
    for line in normalized_lines:
        if "YOUR ORDER NO" in line:
            for token in re.findall(r"\b\d{1,6}\b", line):
                candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_supplier_order_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(
            lines,
            ("supplier order no.", "supplier order no", "supplier order"),
            pattern=r"\b\d{3,6}/\d{1,2}\b",
        )

    candidates: set[str] = set()
    for line in normalized_lines:
        if "PRODUCT CODE" in line or "PRODUCT DESCRIPTION" in line or "YOUR ORDER NO" in line:
            continue
        for token in re.findall(r"\b\d{3,6}/\d{1,2}\b", line):
            candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_product_code(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(
            lines,
            ("impol product code",),
            pattern=r"\b\d{6}\b",
        )

    candidates: set[str] = set()
    for line in normalized_lines:
        if "PRODUCT CODE" in line:
            continue
        for match in re.findall(r"\b(\d{6})/\d\b", line):
            candidates.add(match)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_charge(lines: list[str], *, document_type: str) -> str | None:
    candidates = _collect_impol_charge_candidates(lines, document_type=document_type)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _collect_impol_charge_candidates(lines: list[str], *, document_type: str) -> set[str]:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()

    for line in normalized_lines:
        if "CHEMICAL COMPOSITION" in line or "MECHANICAL PROPERTIES" in line:
            continue

        if document_type == "ddt":
            for match in re.findall(r"\b(\d{6})\s*\(\d+/\d+\)", line):
                candidates.add(match)
            weight_row_match = re.match(
                r"\s*\d+\s+[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?\s+[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?\s+(\d{6})\b",
                line,
            )
            if weight_row_match is not None:
                candidates.add(weight_row_match.group(1))
        else:
            match = re.match(r"\s*(\d{6})(?:\(\d+/\d+\))?\b", line)
            if match is not None:
                candidates.add(match.group(1))

    return candidates


def _extract_impol_diameter(lines: list[str]) -> str | None:
    candidates = _collect_impol_diameter_candidates(lines)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _collect_impol_diameter_candidates(lines: list[str]) -> set[str]:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()
    for line in normalized_lines:
        for match in re.findall(r"\bDIA\s*([0-9]+(?:[.,][0-9]+)?)\s*[X×]\s*\d+\s*MM\b", line):
            normalized = _normalize_decimal_value(match)
            if normalized is not None:
                candidates.add(normalized)
    return candidates


def _extract_impol_net_weight(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        for line in normalized_lines:
            match = re.search(r"\bNETTO\s*:?\s*([0-9]+(?:[.,][0-9]+)?)\s*KG\b", line)
            if match is not None:
                return _normalize_weight(match.group(1))
        return None

    diameter_candidates = _collect_impol_diameter_candidates(lines)
    charge_candidates = _collect_impol_charge_candidates(lines, document_type=document_type)
    if len(diameter_candidates) > 1 or len(charge_candidates) > 1:
        return None

    candidates: set[str] = set()
    for line in normalized_lines:
        if "POS. TOTAL" not in line:
            continue
        numbers = re.findall(r"([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)", line)
        if not numbers:
            continue
        normalized = _normalize_weight(numbers[-1])
        if normalized is not None:
            candidates.add(normalized)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_delivery_note(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bDELIVERY\s+NOTE\s*:?\s*(\d{4,})\b", line)
            if match is not None:
                return match.group(1)

    for index, line in enumerate(normalized_lines):
        if "PACKING SLIP" not in line and "LOT" not in line and "DOWOD WYSYLKOWY" not in line:
            continue
        window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
        pair = _extract_grupa_kety_packing_slip_lot_pair(window)
        if pair is not None:
            return pair[0]
    return None


def _extract_grupa_kety_lot_number(lines: list[str], document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()

    if document_type == "ddt":
        for line in normalized_lines:
            for token in re.findall(r"\b100\d{5}(?:/\d{2})?\b", line):
                candidates.add(token.split("/", 1)[0])
    else:
        for index, line in enumerate(normalized_lines):
            if "PACKING SLIP" not in line and "LOT" not in line and "DOWOD WYSYLKOWY" not in line:
                continue
            window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
            pair = _extract_grupa_kety_packing_slip_lot_pair(window)
            if pair is not None:
                candidates.add(pair[1])
            for candidate in window:
                for token in re.findall(r"\b100\d{5}(?:/\d{2})?\b", candidate):
                    candidates.add(token.split("/", 1)[0])

    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_order_no(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        if "PO NUMBER" in line:
            match = re.search(r"\bPO\s+NUMBER\s+([0-9]{1,6})\b", line)
            if match is not None:
                return match.group(1)
        if "ORDER NO" in line and "SALES ORDER" not in line:
            match = re.search(r"\bORDER\s+NO\s+([0-9]{1,6})\b", line)
            if match is not None:
                return match.group(1)
    for index, line in enumerate(normalized_lines):
        if "ORDER NO" not in line and "NR ZAMOWIENIA KLIENTA" not in line:
            continue
        for candidate in normalized_lines[index + 1 : min(index + 3, len(normalized_lines))]:
            match = re.match(r"\s*([0-9]{1,6})\b", candidate)
            if match is not None:
                return match.group(1)
    return None


def _extract_grupa_kety_heat(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()
    for line in normalized_lines:
        for token in re.findall(r"\b\d{2}[A-Z]-\d{4}\b", line):
            candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_customer_part_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        if "CUSTOMER PART" in line:
            match = re.search(r"\b(PP[0-9A-Z ./:-]+?)\s+PO\s+NUMBER\b", line)
            if match is not None:
                return re.sub(r"\s+", " ", match.group(1).strip())
        if "NR ZAMOWIENIA KLIENTA" in line or "ORDER NO" in line:
            match = re.search(r"\b(PP[0-9A-Z ./:-]+?)\s+E\d{6,}", line)
            if match is not None:
                return re.sub(r"\s+", " ", match.group(1).strip())
    return None


def _extract_grupa_kety_packing_slip_lot_pair(lines: list[str]) -> tuple[str, str] | None:
    for line in lines:
        match = re.search(r"\b(\d{4,6})\s*/\s*(100\d{5})\b", line)
        if match is not None:
            return match.group(1), match.group(2)
    return None


def _normalize_customer_order_tokens(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None

    normalized_text = cleaned.upper()
    normalized_text = normalized_text.replace("/", "-")
    normalized_text = re.sub(r"(?<=\d)\.(?=\d)", "-", normalized_text)
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip()

    leading_date_match = re.search(r"(20\d{2}-\d{2}-\d{2})\D{0,4}(\d{1,4})\b", normalized_text)
    if leading_date_match is not None:
        return f"{int(leading_date_match.group(2))}-{leading_date_match.group(1)}"

    trailing_date_match = re.search(r"\b(\d{1,4})\D{0,4}(20\d{2}-\d{2}-\d{2})", normalized_text)
    if trailing_date_match is not None:
        return f"{int(trailing_date_match.group(1))}-{trailing_date_match.group(2)}"

    tokens = re.findall(r"[A-Z0-9]+", normalized_text)
    if not tokens:
        return None
    if re.search(r"20\d{2}-\d{2}-\d{2}", normalized_text):
        date_match = re.search(r"20\d{2}-\d{2}-\d{2}", normalized_text)
        date_value = date_match.group(0) if date_match else None
        other_tokens = [
            token
            for token in tokens
            if token not in {"VS", "ODV", "RIF", "ORDINE", "CLIENTE", "CUSTOMER", "ORDER", "NO", "N"}
            and token not in set(re.findall(r"\d+", date_value or ""))
        ]
        if date_value:
            prefix = next((token for token in other_tokens if re.fullmatch(r"\d{1,4}", token)), "".join(other_tokens))
            if prefix:
                return f"{int(prefix)}-{date_value}"
            return None
    if len(tokens) >= 4 and re.fullmatch(r"20\d{2}", tokens[1]):
        date_value = f"{tokens[1]}-{tokens[2]}-{tokens[3]}"
        prefix = next((token for token in tokens if re.fullmatch(r"\d{1,4}", token)), tokens[0])
        return f"{int(prefix)}-{date_value}"
    if len(tokens) >= 4 and re.fullmatch(r"20\d{2}", tokens[0]):
        date_value = f"{tokens[0]}-{tokens[1]}-{tokens[2]}"
        suffix = next((token for token in reversed(tokens) if re.fullmatch(r"\d{1,4}", token)), None)
        if suffix is not None:
            return f"{int(suffix)}-{date_value}"
    if len(tokens) >= 4 and re.fullmatch(r"\d{1,4}", tokens[0]) and re.fullmatch(r"20\d{2}", tokens[1]):
        date_value = f"{tokens[1]}-{tokens[2]}-{tokens[3]}"
        return f"{int(tokens[0])}-{date_value}"
    return None


def _is_normalized_customer_order(value: str | None) -> bool:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return False
    return re.fullmatch(r"\d{1,4}-20\d{2}-\d{2}-\d{2}", cleaned) is not None


def _extract_metalba_ddt_reference_values(lines: list[str]) -> tuple[str | None, str | None]:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line.upper())
        if "DDT" not in normalized:
            continue
        tokens = re.findall(r"\d{2}/\d{2,5}", normalized)
        if len(tokens) >= 2:
            return tokens[0], tokens[1]
    return None, None


def _extract_metalba_certificate_reference_values(lines: list[str]) -> tuple[str | None, str | None]:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line.upper())
        if "BARRA TONDA" not in normalized and "ESTRUSO" not in normalized:
            continue
        matches = re.findall(r"\d{2}/\d{4}(?:/\d+)?|\d{2}/\d{2}", normalized)
        if len(matches) >= 2:
            commessa = next((value for value in matches if value.count("/") >= 2 or re.fullmatch(r"\d{2}/\d{4}", value)), None)
            ordine_cliente = next((value for value in matches if re.fullmatch(r"\d{2}/\d{2}", value)), None)
            if ordine_cliente or commessa:
                return ordine_cliente, commessa
    return None, None


def _string_or_none(value: str | int | None) -> str | None:
    if value is None:
        return None
    string_value = str(value).strip()
    return string_value or None


def _detect_note_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        page_text = _best_page_text(page)
        if not page_text:
            continue
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for line in lines:
            normalized_line = line.lower()
            if "nota_us_control_classe" not in matches:
                us_control_value = _detect_us_control_class(normalized_line)
                if us_control_value is not None:
                    matches["nota_us_control_classe"] = {
                        "page_id": page.id,
                        "snippet": line,
                        "standardized": us_control_value,
                        "final": us_control_value,
                    }
            if "nota_rohs" not in matches and "rohs" in normalized_line:
                matches["nota_rohs"] = {
                    "page_id": page.id,
                    "snippet": line,
                    "standardized": "true",
                    "final": "true",
                }
            if "nota_radioactive_free" not in matches and _is_radioactive_free_line(normalized_line):
                matches["nota_radioactive_free"] = {
                    "page_id": page.id,
                    "snippet": line,
                    "standardized": "true",
                    "final": "true",
                }
    return matches


CHEMISTRY_FIELD_SET = {
    "Si",
    "Fe",
    "Cu",
    "Mn",
    "Mg",
    "Cr",
    "Ni",
    "Zn",
    "Ti",
    "Pb",
    "V",
    "Bi",
    "Sn",
    "Zr",
    "Be",
    "Zr+Ti",
    "Mn+Cr",
    "Bi+Pb",
}


PROPERTY_FIELD_SET = {"HB", "Rp0.2", "Rm", "A%", "Rp0.2 / Rm", "IACS%"}

DDT_NUMERIC_FIELD_SET = {"diametro", "peso"}


def _is_numeric_standardized_field(blocco: str, campo: str) -> bool:
    if blocco == "ddt":
        return campo in DDT_NUMERIC_FIELD_SET
    if blocco == "chimica":
        return campo in CHEMISTRY_FIELD_SET
    if blocco == "proprieta":
        return campo in PROPERTY_FIELD_SET
    return False


def _extract_numeric_token(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    normalized_text = _normalize_mojibake_numeric_text(cleaned).replace("−", "-")
    match = re.search(r"-?\d+(?:[.,]\d+)?", normalized_text)
    if match is None:
        return None
    return match.group(0)


def _normalize_numeric_value(value: str | None) -> str | None:
    token = _extract_numeric_token(value)
    if token is None:
        return None
    return token.replace(",", ".")


def _safe_float(value: str | None) -> float | None:
    normalized = _normalize_numeric_value(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _normalize_mojibake_numeric_text(value: str) -> str:
    translation = str.maketrans(
        {
            "ð": "0",
            "ï": "1",
            "î": "2",
            "í": "3",
            "ì": "4",
            "ë": "5",
            "ê": "6",
            "é": "7",
            "è": "8",
            "ç": "9",
            "ò": ".",
            "ô": ",",
            "ó": "-",
        }
    )
    return value.translate(translation)


def _normalize_value_for_field(blocco: str, campo: str, value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    if not _is_numeric_standardized_field(blocco, campo):
        return cleaned
    return _normalize_numeric_value(cleaned) or cleaned


def _detect_chemistry_matches(
    pages: list[DocumentPage],
    *,
    supplier_name: str | None = None,
) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    template = resolve_supplier_template(supplier_name) if supplier_name else None
    for page in pages:
        page_text = _best_page_text(page)
        if not page_text:
            continue
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        if template is not None and template.supplier_key == "aluminium_bozen":
            page_matches = _parse_aluminium_bozen_chemistry_from_lines(lines, page.id)
            if not page_matches:
                page_matches = _parse_chemistry_from_lines(lines, page.id)
        else:
            page_matches = _parse_chemistry_from_lines(lines, page.id)
        for field_name, payload in page_matches.items():
            matches.setdefault(field_name, payload)
    return matches


def _detect_property_matches(
    pages: list[DocumentPage],
    *,
    supplier_name: str | None = None,
) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    template = resolve_supplier_template(supplier_name) if supplier_name else None
    for page in pages:
        page_text = _best_page_text(page)
        if not page_text:
            continue
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]

        if template is not None and template.supplier_key == "aluminium_bozen":
            page_matches = _parse_aluminium_bozen_properties_from_lines(lines, page.id)
            if not _has_complete_measured_properties(page_matches):
                crop_lines = _extract_aluminium_bozen_mechanical_crop_lines(page)
                if crop_lines:
                    crop_matches = _parse_aluminium_bozen_properties_from_lines(crop_lines, page.id)
                    if _has_complete_measured_properties(crop_matches):
                        page_matches = crop_matches
            if page_matches:
                for field_name, payload in page_matches.items():
                    matches.setdefault(field_name, payload)
                continue

        spec_matches = _parse_properties_from_spec_lines(lines, page.id)
        compact_matches = _parse_properties_from_compact_lines(lines, page.id)
        cluster_matches = _parse_properties_from_numeric_cluster(lines, page.id)

        for field_name, payload in {**cluster_matches, **compact_matches, **spec_matches}.items():
            matches.setdefault(field_name, payload)

    return matches


def _has_complete_measured_properties(matches: dict[str, dict[str, str | int]]) -> bool:
    return all(field_name in matches for field_name in ("Rm", "Rp0.2", "A%", "HB"))


def _extract_aluminium_bozen_mechanical_crop_lines(page: DocumentPage) -> list[str]:
    if not page.immagine_pagina_storage_key:
        return []

    image_path = get_document_page_image_path(page)
    if not image_path.exists():
        return []

    try:
        with Image.open(image_path) as image:
            width, height = image.size
            crop = image.crop(
                (
                    int(width * 0.08),
                    int(height * 0.48),
                    int(width * 0.92),
                    int(height * 0.82),
                )
            )
    except OSError:
        return []

    seen_lines: set[str] = set()
    merged_lines: list[str] = []
    for config in ("--psm 4", "--psm 6", "--psm 11"):
        try:
            text = pytesseract.image_to_string(crop, lang="eng+ita+deu", config=config)
        except (OSError, pytesseract.TesseractNotFoundError):
            continue
        for line in text.splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned in seen_lines:
                continue
            seen_lines.add(cleaned)
            merged_lines.append(cleaned)
    return merged_lines


def _detect_chemistry_matches_with_vision(
    pages: list[DocumentPage],
    *,
    openai_api_key: str,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    crops = _build_certificate_safe_crops(pages, supplier_key=supplier_key)
    if supplier_key == "aluminium_bozen":
        crops = {
            label: crop
            for label, crop in crops.items()
            if str(crop.get("role")) in {"chemistry_table", "certificate_continuation"}
            or str(crop.get("label", "")).endswith("chemistry_context")
        }
    if not crops:
        return {}
    chemistry_fields = ["Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Ni", "Zn", "Ti", "Pb", "V", "Bi", "Sn", "Zr", "Be", "Zr+Ti", "Mn+Cr", "Bi+Pb"]
    extracted = _extract_certificate_fields_from_openai(
        crops,
        openai_api_key=openai_api_key,
        field_names=chemistry_fields,
        instruction=(
            "Leggi la tabella di composizione chimica del certificato materiale. "
            "La tabella puo essere orizzontale o verticale. "
            "Usa solo questi elementi: Si, Fe, Cu, Mn, Mg, Cr, Ni, Zn, Ti, Pb, V, Bi, Sn, Zr, Be, Zr+Ti, Mn+Cr, Bi+Pb. "
            "Ignora righe o colonne Min e Max. "
            "Riporta solo i valori misurati chiaramente leggibili."
        ),
    )
    return _normalize_vision_numeric_matches(extracted, crops)


def _detect_note_matches_with_vision(
    pages: list[DocumentPage],
    *,
    openai_api_key: str,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    crops = _build_certificate_safe_crops(pages, supplier_key=supplier_key)
    crops = {
        label: crop
        for label, crop in crops.items()
        if str(crop.get("role")) in {"notes_block", "certificate_continuation"}
        or str(crop.get("label", "")).endswith("notes_block")
        or str(crop.get("label", "")).endswith("continuation_lower")
    }
    if not crops:
        return {}

    extracted = _extract_certificate_fields_from_openai(
        crops,
        openai_api_key=openai_api_key,
        field_names=["nota_us_control_classe", "nota_rohs", "nota_radioactive_free"],
        instruction=(
            "Leggi le note tecniche finali del certificato materiale. "
            "Per nota_us_control_classe restituisci solo A o B se una nota ASTM/AMS indica chiaramente la classe. "
            "Per nota_rohs restituisci true solo se la conformita RoHS e chiaramente dichiarata. "
            "Per nota_radioactive_free restituisci true solo se il certificato dichiara esplicitamente assenza di contaminazione radioattiva."
        ),
    )
    return _normalize_vision_note_matches(extracted, crops)


def _detect_property_matches_with_vision(
    pages: list[DocumentPage],
    *,
    openai_api_key: str,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    crops = _build_certificate_safe_crops(pages, supplier_key=supplier_key)
    if supplier_key == "aluminium_bozen":
        crops = {
            label: crop
            for label, crop in crops.items()
            if str(crop.get("role")) in {"properties_table", "certificate_continuation"}
            or str(crop.get("label", "")).endswith("properties_context")
        }
    if not crops:
        return {}
    extracted = _extract_certificate_fields_from_openai(
        crops,
        openai_api_key=openai_api_key,
        field_names=sorted(PROPERTY_FIELD_SET),
        instruction=(
            "Leggi la tabella delle proprieta meccaniche o fisiche del certificato materiale. "
            "La tabella puo essere orizzontale o verticale. "
            "Ignora righe o colonne Min e Max. "
            "Se ci sono piu righe misurate vere, per ogni campo restituisci il valore misurato reale piu basso chiaramente leggibile."
        ),
    )
    return _normalize_vision_numeric_matches(extracted, crops)


def _normalize_vision_numeric_matches(
    extracted: dict[str, dict[str, str | None]],
    crops: dict[str, dict[str, str | int]],
) -> dict[str, dict[str, str | int]]:
    normalized: dict[str, dict[str, str | int]] = {}
    for field_name, payload in extracted.items():
        raw_value = _string_or_none(payload.get("value"))
        if raw_value is None:
            continue
        cleaned_value = raw_value.replace(",", ".").strip()
        if not re.search(r"\d", cleaned_value):
            continue
        source_crop = _string_or_none(payload.get("source_crop"))
        crop = crops.get(source_crop) if source_crop else None
        page_id = int(crop["page_id"]) if crop and crop.get("page_id") is not None else 0
        if page_id <= 0:
            continue
        normalized[field_name] = {
            "page_id": page_id,
            "snippet": _string_or_none(payload.get("evidence")) or raw_value,
            "raw": raw_value,
            "standardized": cleaned_value,
            "final": cleaned_value,
            "method": "chatgpt",
        }
    return normalized


def _normalize_vision_note_matches(
    extracted: dict[str, dict[str, str | None]],
    crops: dict[str, dict[str, str | int]],
) -> dict[str, dict[str, str | int]]:
    normalized: dict[str, dict[str, str | int]] = {}
    for field_name, payload in extracted.items():
        raw_value = _string_or_none(payload.get("value"))
        evidence = _string_or_none(payload.get("evidence")) or raw_value
        if evidence is None:
            continue
        source_crop = _string_or_none(payload.get("source_crop"))
        crop = crops.get(source_crop) if source_crop else None
        page_id = int(crop["page_id"]) if crop and crop.get("page_id") is not None else 0
        if page_id <= 0:
            continue

        final_value: str | None = None
        if field_name == "nota_us_control_classe":
            final_value = _detect_us_control_class(evidence.lower())
        elif field_name == "nota_rohs":
            haystack = evidence.lower()
            if "rohs" in haystack:
                final_value = "true"
        elif field_name == "nota_radioactive_free":
            if _is_radioactive_free_line(evidence.lower()):
                final_value = "true"

        if final_value is None:
            continue

        normalized[field_name] = {
            "page_id": page_id,
            "snippet": evidence,
            "standardized": final_value,
            "final": final_value,
            "method": "chatgpt",
        }
    return normalized


def _parse_properties_from_spec_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for line in lines:
        lowered = line.lower()
        if not lowered.startswith("spec."):
            continue

        tokens = re.findall(r"\d+(?:[.,]\d+)?", line)
        if len(tokens) < 8:
            continue

        # Spec. N HB Ø S Rp0.2 Rm A% Rp/Rm [date] [time]
        mapping = {
            "HB": tokens[1],
            "Rp0.2": tokens[4],
            "Rm": tokens[5],
            "A%": tokens[6],
            "Rp0.2 / Rm": tokens[7],
        }
        for field_name, raw_value in mapping.items():
            standardized = raw_value.replace(",", ".")
            matches.setdefault(
                field_name,
                {
                    "page_id": page_id,
                    "snippet": line,
                    "raw": raw_value,
                    "standardized": standardized,
                    "final": standardized,
                },
            )
        break
    return matches


def _parse_properties_from_compact_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    mechanical_anchor = None
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "mechanical properties" in lowered or "caratteristiche" in lowered or "meccan" in lowered:
            mechanical_anchor = index
            break

    if mechanical_anchor is None:
        return matches

    window = lines[mechanical_anchor : min(mechanical_anchor + 12, len(lines))]
    candidate_line = None
    for line in choose_measured_lines(window):
        lowered = line.lower()
        if lowered.startswith("spec."):
            continue
        numbers = re.findall(r"\d+(?:[.,]\d+)?", line)
        if len(numbers) >= 4:
            candidate_line = line
            break

    if candidate_line is None:
        for field_name, payload in _parse_vertical_properties_from_lines(window, page_id).items():
            matches.setdefault(field_name, payload)
        return matches

    numbers = re.findall(r"\d+(?:[.,]\d+)?", candidate_line)
    if len(numbers) < 4:
        for field_name, payload in _parse_vertical_properties_from_lines(window, page_id).items():
            matches.setdefault(field_name, payload)
        return matches

    mapping = {
        "Rm": numbers[0],
        "Rp0.2": numbers[1],
        "A%": numbers[2],
        "HB": numbers[3],
    }
    if len(numbers) >= 5:
        mapping["IACS%"] = numbers[4]

    for field_name, raw_value in mapping.items():
        standardized = raw_value.replace(",", ".")
        matches.setdefault(
            field_name,
            {
                "page_id": page_id,
                "snippet": candidate_line,
                "raw": raw_value,
                "standardized": standardized,
                "final": standardized,
            },
        )

    for field_name, payload in _parse_vertical_properties_from_lines(window, page_id).items():
        matches.setdefault(field_name, payload)
    return matches


def _parse_vertical_properties_from_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    value_lines: list[str] = []
    labels_found = {
        "Rm": False,
        "Rp0.2": False,
        "A%": False,
        "HB": False,
        "IACS%": False,
    }

    for line in lines:
        lowered = line.lower()
        if any(marker in lowered for marker in ("norma", "norm", "limit", "min.", "max.", "na custom")):
            break
        cleaned = line.strip()
        if re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned):
            value_lines.append(cleaned)

    for line in lines:
        lowered = line.lower()
        if "rp0" in lowered:
            labels_found["Rp0.2"] = True
        elif re.search(r"\brm\b", lowered):
            labels_found["Rm"] = True
        elif "hard" in lowered or "brinell" in lowered or "hbw" in lowered:
            labels_found["HB"] = True
        elif "iacs" in lowered or "ms/m" in lowered:
            labels_found["IACS%"] = True
        elif "a%" in lowered or re.search(r"\baû\b", lowered) or re.search(r"\b[aA][%Ã]\b", line):
            labels_found["A%"] = True

    if len(value_lines) < 4:
        return {}

    normalized_values = [_normalize_numeric_value(value) or value for value in value_lines]
    if len(normalized_values) >= 5 and re.fullmatch(r"\d+", value_lines[0] or ""):
        try:
            first_value = float(normalized_values[0])
        except ValueError:
            first_value = -1
        if 0 <= first_value <= 10:
            normalized_values = normalized_values[1:]

    ordered_fields = ["Rm", "Rp0.2", "A%", "HB"]
    if labels_found["IACS%"] and len(normalized_values) >= 5:
        ordered_fields.append("IACS%")

    if len(normalized_values) < len(ordered_fields):
        return {}

    matches: dict[str, dict[str, str | int]] = {}
    chosen_values = normalized_values[: len(ordered_fields)]
    snippet = " | ".join(chosen_values)
    for field_name, raw_value in zip(ordered_fields, chosen_values):
        matches.setdefault(
            field_name,
            {
                "page_id": page_id,
                "snippet": snippet,
                "raw": raw_value,
                "standardized": raw_value,
                "final": raw_value,
            },
        )
    return matches


def _parse_aluminium_bozen_properties_from_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    anchor_index = None
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "mechanical properties" in lowered or "caratteristiche meccaniche" in lowered:
            anchor_index = index
            break
    if anchor_index is None:
        return {}

    window = lines[anchor_index : min(anchor_index + 24, len(lines))]
    measured_candidates: list[tuple[str, dict[str, dict[str, str | int]]]] = []
    for line in window:
        lowered = line.lower()
        if any(
            marker in lowered
            for marker in (
                "mechanical properties",
                "caratteristiche meccaniche",
                "sample no",
                "provetta",
                "norma",
                "norm ",
                "limit",
                "na custom",
                "minimum values",
            )
        ):
            continue
        numbers = re.findall(r"\d+(?:[.,]\d+)?", line)
        if len(numbers) < 4:
            continue
        if len(numbers) >= 5:
            try:
                first_value = float(numbers[0].replace(",", "."))
            except ValueError:
                first_value = -1
            if 0 <= first_value <= 10:
                numbers = numbers[1:]
        candidate_values = [_normalize_numeric_value(value) or value for value in numbers[:5]]
        candidate_match = _build_property_match_from_candidate_values(candidate_values, page_id)
        if candidate_match:
            for payload in candidate_match.values():
                payload["snippet"] = line
            measured_candidates.append((line, candidate_match))

    aggregated = _aggregate_measured_property_candidates(measured_candidates, page_id)
    if aggregated:
        return aggregated

    # Older Aluminium Bozen certificates may expose only hardness/conductivity
    # around the mechanical-properties block. We keep them as partial measured values
    # instead of inventing a full Rm/Rp0.2/A row.
    labels_text = " ".join(window).lower()
    if ("hardness" in labels_text or "brinell" in labels_text or "hbw" in labels_text) and (
        "conduc" in labels_text or "condutt" in labels_text or "ms/m" in labels_text or "iacs" in labels_text
    ):
        for line in window:
            numbers = [_safe_float(value) for value in re.findall(r"\d+(?:[.,]\d+)?", line)]
            numbers = [value for value in numbers if value is not None]
            if len(numbers) < 2:
                continue
            meaningful = sorted((value for value in numbers if value > 0), reverse=True)
            if len(meaningful) < 2:
                continue
            hb_candidate = next((value for value in meaningful if 50 <= value <= 250), None)
            iacs_candidate = next((value for value in meaningful if 0 < value <= 30), None)
            if hb_candidate is None or iacs_candidate is None:
                continue
            hb_value = _normalize_numeric_value(str(hb_candidate)) or str(hb_candidate)
            iacs_value = _normalize_numeric_value(str(iacs_candidate)) or str(iacs_candidate)
            return {
                "HB": {
                    "page_id": page_id,
                    "snippet": line,
                    "raw": hb_value,
                    "standardized": hb_value,
                    "final": hb_value,
                },
                "IACS%": {
                    "page_id": page_id,
                    "snippet": line,
                    "raw": iacs_value,
                    "standardized": iacs_value,
                    "final": iacs_value,
                },
            }
    return {}


def _aggregate_measured_property_candidates(
    measured_candidates: list[tuple[str, dict[str, dict[str, str | int]]]],
    page_id: int,
) -> dict[str, dict[str, str | int]]:
    if not measured_candidates:
        return {}

    aggregated: dict[str, tuple[float, str, str]] = {}
    for line, candidate in measured_candidates:
        for field_name, payload in candidate.items():
            raw_value = _string_or_none(cast(dict[str, object], payload).get("final"))
            numeric_value = _safe_float(raw_value)
            if numeric_value is None:
                continue
            current = aggregated.get(field_name)
            if current is None or numeric_value < current[0]:
                standardized = _normalize_numeric_value(raw_value) or raw_value
                aggregated[field_name] = (numeric_value, standardized, line)

    if not aggregated:
        return {}

    ordered_fields = ["Rm", "Rp0.2", "A%", "HB", "IACS%"]
    result: dict[str, dict[str, str | int]] = {}
    for field_name in ordered_fields:
        payload = aggregated.get(field_name)
        if payload is None:
            continue
        _, standardized, line = payload
        result[field_name] = {
            "page_id": page_id,
            "snippet": line,
            "raw": standardized,
            "standardized": standardized,
            "final": standardized,
        }
    return result


def _parse_properties_from_numeric_cluster(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    for index in range(len(lines)):
        normalized_line = _normalize_mojibake_numeric_text(lines[index])
        inline_values = re.findall(r"\d+(?:[.,]\d+)?", normalized_line)
        if len(inline_values) >= 4:
            candidate_values = [_normalize_numeric_value(value) or value for value in inline_values[:5]]
            if len(candidate_values) >= 5 and re.fullmatch(r"\d+", inline_values[0] or ""):
                try:
                    first_value = float(candidate_values[0])
                except ValueError:
                    first_value = -1
                if 0 <= first_value <= 10:
                    candidate_values = candidate_values[1:]
            inline_match = _build_property_match_from_candidate_values(candidate_values, page_id)
            if inline_match:
                return inline_match

        cluster: list[str] = []
        cursor = index
        while cursor < len(lines):
            normalized = _normalize_numeric_value(lines[cursor])
            if normalized is None:
                break
            cluster.append(normalized)
            cursor += 1

        if len(cluster) < 4:
            continue

        candidate_values = cluster[:5]
        if len(candidate_values) >= 5 and re.fullmatch(r"\d+", candidate_values[0] or ""):
            try:
                first_value = float(candidate_values[0])
            except ValueError:
                first_value = -1
            if 0 <= first_value <= 10:
                candidate_values = candidate_values[1:]

        cluster_match = _build_property_match_from_candidate_values(candidate_values, page_id)
        if cluster_match:
            return cluster_match

    return {}


def _build_property_match_from_candidate_values(
    candidate_values: list[str],
    page_id: int,
) -> dict[str, dict[str, str | int]]:
    if len(candidate_values) < 4:
        return {}

    rm = _safe_float(candidate_values[0])
    rp02 = _safe_float(candidate_values[1])
    a_pct = _safe_float(candidate_values[2])
    hb = _safe_float(candidate_values[3])
    if None in (rm, rp02, a_pct, hb):
        return {}
    if not (rm >= 100 and rp02 >= 80 and 0 < a_pct <= 60 and 20 <= hb <= 250):
        return {}

    ordered_fields = ["Rm", "Rp0.2", "A%", "HB"]
    if len(candidate_values) >= 5:
        iacs = _safe_float(candidate_values[4])
        if iacs is not None and 0 < iacs <= 100:
            ordered_fields.append("IACS%")

    snippet = " | ".join(candidate_values[: len(ordered_fields)])
    matches: dict[str, dict[str, str | int]] = {}
    for field_name, raw_value in zip(ordered_fields, candidate_values):
        matches.setdefault(
            field_name,
            {
                "page_id": page_id,
                "snippet": snippet,
                "raw": raw_value,
                "standardized": raw_value,
                "final": raw_value,
            },
        )
    return matches


def _parse_chemistry_from_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for index, line in enumerate(lines):
        elements = _extract_chemistry_header(line)
        if not elements:
            continue

        measurement_line = _find_chemistry_measurement_line(lines, index + 1, len(elements))
        if measurement_line is None:
            continue

        values = re.findall(r"\d+(?:[.,]\d+)?|/|Other", measurement_line, flags=re.IGNORECASE)
        if len(values) < len(elements):
            continue

        for element, raw_value in zip(elements, values):
            if raw_value in {"/", "Other", "other"}:
                continue
            standardized = raw_value.replace(",", ".")
            matches.setdefault(
                element,
                {
                    "page_id": page_id,
                    "snippet": f"{line} | {measurement_line}",
                    "raw": raw_value,
                    "standardized": standardized,
                    "final": standardized,
                },
            )
    for field_name, payload in _parse_vertical_chemistry_from_lines(lines, page_id).items():
        matches.setdefault(field_name, payload)
    return matches


def _parse_vertical_chemistry_from_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    anchor_index = None
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "chemical analysis" in lowered or "analisi chimica" in lowered or "chemische analyse" in lowered:
            anchor_index = index
            break
    if anchor_index is None:
        return {}

    window = lines[anchor_index + 1 : min(anchor_index + 48, len(lines))]
    elements: list[str] = []
    measured_index: int | None = None

    for index, line in enumerate(window):
        element = _extract_vertical_chemistry_element(line)
        if element is not None:
            elements.append(element)
            continue
        lowered = line.lower()
        if "ist/act" in lowered or lowered == "value" or lowered == "valeur":
            measured_index = index
            break

    if not elements or measured_index is None:
        return {}

    measured_values = _collect_vertical_numeric_values(window, measured_index + 1, len(elements))
    if len(measured_values) < len(elements):
        return {}

    snippet_parts = [window[measured_index], *measured_values[: len(elements)]]
    matches: dict[str, dict[str, str | int]] = {}
    for element, raw_value in zip(elements, measured_values):
        standardized = raw_value.replace(",", ".")
        matches.setdefault(
            element,
            {
                "page_id": page_id,
                "snippet": " | ".join(snippet_parts),
                "raw": raw_value,
                "standardized": standardized,
                "final": standardized,
            },
        )
    return matches


def _extract_chemistry_header(line: str) -> list[str]:
    if any(marker in line.lower() for marker in ("chemical composition", "composizione chimica", "alloy", "charge", "notes", "mechanical")):
        return []
    tokens = re.findall(r"[A-Z][a-z]?(?:\+[A-Z][a-z]?)?", line)
    elements = [token for token in tokens if token in CHEMISTRY_FIELD_SET]
    if len(elements) < 3:
        return []
    return elements


def _extract_vertical_chemistry_element(line: str) -> str | None:
    token = line.strip().replace(" ", "")
    if token == "%":
        return None
    if token.lower().startswith("andere") or token.lower().startswith("other"):
        return None
    mojibake_token = token.lstrip("û")
    mojibake_map = {
        "Í·": "Si",
        "Ú»": "Fe",
        "Ý«": "Cu",
        "Ó²": "Mn",
        "Ó¹": "Mg",
        "Ý®": "Cr",
        "Ò·": "Ni",
        "Æ²": "Zn",
        "Ê": "V",
        "Ì·": "Ti",
        "Ð¾": "Pb",
        "Æ®": "Zr",
        "Þ·": "Bi",
        "Í²": "Sn",
        "Þ»": "Be",
    }
    if mojibake_token in mojibake_map:
        return mojibake_map[mojibake_token]
    if token in CHEMISTRY_FIELD_SET:
        return token
    return None


def _parse_aluminium_bozen_chemistry_from_lines(lines: list[str], page_id: int) -> dict[str, dict[str, str | int]]:
    anchor_index = None
    for index, line in enumerate(lines):
        lowered = line.lower()
        if (
            "chemical analysis" in lowered
            or "analisi chimica" in lowered
            or "chemische analyse" in lowered
            or "chemical composition" in lowered
            or "composizione chimica" in lowered
            or "zusammensetzung" in lowered
            or "composition chimique" in lowered
            or "ÝÑÓÐÑÍ" in line
        ):
            anchor_index = index
            break
    if anchor_index is None:
        return {}

    window = lines[anchor_index + 1 : min(anchor_index + 42, len(lines))]
    fixed_slots: list[str | None] = ["Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Ni", "Zn", "V", "Ti", "Pb", "Zr", "Bi", "Sn", None]
    for line in window:
        lowered = line.lower()
        if any(marker in lowered for marker in ("norma", "norm", "limit", "max.", "min.")):
            continue
        if not re.match(r"^\s*[A-Z]?\d{5,}[A-Z0-9]?", line, re.IGNORECASE):
            continue
        normalized_line = _normalize_mojibake_numeric_text(line)
        value_source = re.findall(r"\d+(?:[.,]\d+)?", normalized_line)
        if len(value_source) < 12:
            continue
        numeric_values = value_source[1:]
        matches: dict[str, dict[str, str | int]] = {}
        for element_name, raw_value in zip(fixed_slots, numeric_values):
            if element_name is None:
                continue
            standardized = _normalize_numeric_value(raw_value) or raw_value
            matches.setdefault(
                element_name,
                {
                    "page_id": page_id,
                    "snippet": line,
                    "raw": raw_value,
                    "standardized": standardized,
                    "final": standardized,
                },
            )
        if matches:
            return matches

    pending_cast_line: str | None = None
    for index, line in enumerate(window):
        lowered = line.lower()
        if any(marker in lowered for marker in ("norma", "norm", "limit", "max.", "min.")):
            continue
        if pending_cast_line is None and re.match(r"^\s*[A-Z]?\d{5,}[A-Z0-9]?\s*$", line, re.IGNORECASE):
            pending_cast_line = line.strip()
            continue
        if pending_cast_line is None:
            continue
        normalized_line = _normalize_mojibake_numeric_text(line)
        value_source = re.findall(r"\d+(?:[.,]\d+)?", normalized_line)
        if len(value_source) < 12:
            continue
        matches = {}
        for element_name, raw_value in zip(fixed_slots, value_source):
            if element_name is None:
                continue
            standardized = _normalize_numeric_value(raw_value) or raw_value
            matches.setdefault(
                element_name,
                {
                    "page_id": page_id,
                    "snippet": f"{pending_cast_line} | {line}",
                    "raw": raw_value,
                    "standardized": standardized,
                    "final": standardized,
                },
            )
        if matches:
            return matches

    elements: list[str] = []
    element_slots: list[str | None] = []
    for line in window:
        if not elements:
            inline_slots = _extract_aluminium_bozen_chemistry_slots_from_line(line)
            inline_elements = [slot for slot in inline_slots if slot is not None]
            if len(inline_elements) >= 8:
                element_slots = inline_slots
                elements.extend(inline_elements)
                continue
        element = _extract_vertical_chemistry_element(line)
        if element is not None:
            elements.append(element)
            element_slots.append(element)
            continue
        if elements:
            normalized_line = _normalize_mojibake_numeric_text(line)
            normalized_numbers = re.findall(r"\d+(?:[.,]\d+)?", normalized_line)
            segment_values = re.findall(r"\d,\d{3}", normalized_line)
            value_source = segment_values if len(segment_values) >= len(element_slots or elements) else normalized_numbers
            if len(value_source) >= max(8, len(element_slots or elements) - 2):
                snippet = line
                matches: dict[str, dict[str, str | int]] = {}
                if element_slots:
                    slot_values = value_source[: len(element_slots)]
                    for element_name, raw_value in zip(element_slots, slot_values):
                        if element_name is None:
                            continue
                        standardized = _normalize_numeric_value(raw_value) or raw_value
                        matches.setdefault(
                            element_name,
                            {
                                "page_id": page_id,
                                "snippet": snippet,
                                "raw": raw_value,
                                "standardized": standardized,
                                "final": standardized,
                            },
                        )
                    return matches

                measured_values = value_source[: len(elements)]
                for element_name, raw_value in zip(elements, measured_values):
                    standardized = _normalize_numeric_value(raw_value) or raw_value
                    matches.setdefault(
                        element_name,
                        {
                            "page_id": page_id,
                            "snippet": snippet,
                            "raw": raw_value,
                            "standardized": standardized,
                            "final": standardized,
                        },
                    )
                return matches
    return {}


def _extract_aluminium_bozen_chemistry_elements_from_line(line: str) -> list[str]:
    return [slot for slot in _extract_aluminium_bozen_chemistry_slots_from_line(line) if slot is not None]


def _extract_aluminium_bozen_chemistry_slots_from_line(line: str) -> list[str | None]:
    mojibake_map = {
        "Í·": "Si",
        "Ú»": "Fe",
        "Ý«": "Cu",
        "Ó²": "Mn",
        "Ó¹": "Mg",
        "Ý®": "Cr",
        "Ò·": "Ni",
        "Æ²": "Zn",
        "Ê": "V",
        "Ì·": "Ti",
        "Ð¾": "Pb",
        "Æ®": "Zr",
        "Þ·": "Bi",
        "Í²": "Sn",
        "Þ»": "Be",
    }
    tokens = [token.lstrip("û") for token in line.replace("%", " ").split()]
    slots: list[str | None] = []
    for token in tokens:
        if token in mojibake_map:
            slots.append(mojibake_map[token])
        elif token in CHEMISTRY_FIELD_SET:
            slots.append(token)
        elif re.fullmatch(r"[A-Za-z¿®Ù]+", token):
            slots.append(None)
    return slots


def _find_chemistry_measurement_line(lines: list[str], start_index: int, expected_count: int) -> str | None:
    window = lines[start_index : min(start_index + 6, len(lines))]
    for candidate in choose_measured_lines(window):
        lowered = candidate.lower()
        if any(marker in lowered for marker in ("spec.", "norm", "alloy", "charge", "notes", "mechanical")):
            continue
        values = re.findall(r"\d+(?:[.,]\d+)?|/|Other", candidate, flags=re.IGNORECASE)
        if len(values) >= min(expected_count, 3):
            return candidate
    return None


def _collect_vertical_numeric_values(lines: list[str], start_index: int, expected_count: int) -> list[str]:
    values: list[str] = []
    for candidate in lines[start_index : min(start_index + expected_count + 8, len(lines))]:
        cleaned = candidate.strip()
        if re.fullmatch(r"<?\d+(?:[.,]\d+)?", cleaned):
            values.append(cleaned)
        if len(values) >= expected_count:
            break
    return values


def _detect_us_control_class(line: str) -> str | None:
    if "astm" not in line and "ams" not in line:
        return None
    if re.search(r"(class|classe)\s*a", line):
        return "A"
    if re.search(r"(class|classe)\s*b", line):
        return "B"
    return None


def _is_radioactive_free_line(line: str) -> bool:
    if "radio" not in line:
        return False
    if "free from radioactive contamination" in line:
        return True
    if "free of radioactive contaminants" in line:
        return True
    if "contaminazione radioattiva" in line:
        return True
    if "radioaktiver kontamination" in line:
        return True
    if "contamination radioactive" in line:
        return True
    return False
