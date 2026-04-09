from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4
from datetime import UTC, datetime

import fitz
from fastapi import UploadFile
from fastapi import HTTPException, status
from openai import OpenAI
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.logs.service import log_service
from app.modules.acquisition.models import (
    AcquisitionHistoryEvent,
    AcquisitionRow,
    AcquisitionValueHistory,
    CertificateMatch,
    CertificateMatchCandidate,
    Document,
    DocumentEvidence,
    DocumentPage,
    ReadValue,
)
from app.modules.acquisition.schemas import (
    AcquisitionHistoryEventResponse,
    AcquisitionRowCreateRequest,
    AcquisitionRowDetailResponse,
    AcquisitionRowListItemResponse,
    AcquisitionValueHistoryResponse,
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentEvidenceCreateRequest,
    DocumentEvidenceResponse,
    DocumentPageCreateRequest,
    DocumentPageResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    MatchCandidateResponse,
    MatchUpsertRequest,
    MatchResponse,
    ReadValueResponse,
    ReadValueUpsertRequest,
)
from app.modules.suppliers.models import Supplier


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
        fornitore_id=document.fornitore_id,
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
        valore_standardizzato=value.valore_standardizzato,
        valore_finale=value.valore_finale,
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


def serialize_acquisition_row_list_item(row: AcquisitionRow) -> AcquisitionRowListItemResponse:
    return AcquisitionRowListItemResponse(
        id=row.id,
        document_ddt_id=row.document_ddt_id,
        document_certificato_id=row.document_certificato_id,
        cdq=row.cdq,
        fornitore_id=row.fornitore_id,
        fornitore_raw=row.fornitore_raw,
        lega_base=row.lega_base,
        lega_designazione=row.lega_designazione,
        variante_lega=row.variante_lega,
        diametro=row.diametro,
        colata=row.colata,
        ddt=row.ddt,
        peso=row.peso,
        ordine=row.ordine,
        data_documento=row.data_documento,
        note_documento=row.note_documento,
        stato_tecnico=row.stato_tecnico,
        stato_workflow=row.stato_workflow,
        priorita_operativa=row.priorita_operativa,
        validata_finale=row.validata_finale,
        block_states=_compute_block_states(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_acquisition_row_detail(row: AcquisitionRow) -> AcquisitionRowDetailResponse:
    base = serialize_acquisition_row_list_item(row)
    return AcquisitionRowDetailResponse(
        **base.model_dump(),
        ddt_document=serialize_document_summary(row.ddt_document),
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
) -> list[DocumentResponse]:
    query = db.query(Document).order_by(Document.data_upload.desc(), Document.id.desc())
    if tipo_documento is not None:
        query = query.filter(Document.tipo_documento == tipo_documento)
    if fornitore_id is not None:
        query = query.filter(Document.fornitore_id == fornitore_id)
    return [serialize_document(document) for document in query.all()]


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
    extension = Path(original_name).suffix.lower()
    now = datetime.now(UTC)
    relative_storage_key = f"{tipo_documento}/{now:%Y/%m/%d}/{uuid4().hex}{extension}"
    storage_path = _document_storage_root() / relative_storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(file_bytes)

    document = Document(
        tipo_documento=tipo_documento,
        fornitore_id=fornitore_id,
        nome_file_originale=original_name,
        storage_key=relative_storage_key.replace("\\", "/"),
        hash_file=hashlib.sha256(file_bytes).hexdigest(),
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
        document = _index_document_from_path(db, document)
    log_service.record("acquisition", f"Document uploaded: {document.nome_file_originale}", actor_email)
    return serialize_document(document)


def index_document(db: Session, document: Document, actor_email: str | None = None) -> DocumentDetailResponse:
    document = _index_document_from_path(db, document)
    log_service.record("acquisition", f"Document indexed: {document.nome_file_originale}", actor_email)
    return serialize_document_detail(document)


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
        .options(selectinload(AcquisitionRow.values), joinedload(AcquisitionRow.certificate_match))
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
    return [serialize_acquisition_row_list_item(row) for row in query.all()]


def get_acquisition_row(db: Session, row_id: int) -> AcquisitionRow:
    row = (
        db.query(AcquisitionRow)
        .options(
            joinedload(AcquisitionRow.ddt_document),
            joinedload(AcquisitionRow.certificate_document),
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
    return row


def create_acquisition_row(
    db: Session,
    payload: AcquisitionRowCreateRequest,
    actor_id: int,
    actor_email: str,
) -> AcquisitionRowDetailResponse:
    ddt_document = _get_document_of_type(db, payload.document_ddt_id, "ddt")
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
        document_ddt_id=ddt_document.id,
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
        nota_breve=f"DDT document {ddt_document.id}",
    )
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
    db.commit()
    updated_row = get_acquisition_row(db, row.id)
    if updated_row.certificate_match is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Match not available after update")
    return serialize_match(updated_row.certificate_match)


def detect_standard_notes(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    matches = _detect_note_matches(certificate_document.pages)
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="note",
            azione="note_non_rilevate",
            user_id=actor_id,
        )
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
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def detect_chemistry(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    matches = _detect_chemistry_matches(certificate_document.pages)
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="chimica",
            azione="chimica_non_rilevata",
            user_id=actor_id,
        )
        db.commit()
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    for field_name, match in matches.items():
        evidence = _create_text_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=match["page_id"],
            blocco="chimica",
            snippet=match["snippet"],
            actor_id=actor_id,
            confidence=0.88,
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
            metodo_lettura="pdf_text",
            fonte_documentale="certificato",
            confidenza=0.88,
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
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def detect_properties(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    certificate_document_id = row.document_certificato_id
    if certificate_document_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Acquisition row has no certificate document")

    certificate_document = get_document(db, certificate_document_id)
    if not certificate_document.pages:
        certificate_document = _index_document_from_path(db, certificate_document)

    matches = _detect_property_matches(certificate_document.pages)
    if not matches:
        _record_history_event(
            db=db,
            acquisition_row_id=row.id,
            blocco="proprieta",
            azione="proprieta_non_rilevate",
            user_id=actor_id,
        )
        db.commit()
        return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))

    for field_name, match in matches.items():
        evidence = _create_text_evidence(
            db=db,
            row_id=row.id,
            document_id=certificate_document.id,
            document_page_id=match["page_id"],
            blocco="proprieta",
            snippet=match["snippet"],
            actor_id=actor_id,
            confidence=0.86,
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
            metodo_lettura="pdf_text",
            fonte_documentale="certificato",
            confidenza=0.86,
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
    db.commit()
    return serialize_acquisition_row_detail(get_acquisition_row(db, row.id))


def extract_core_fields(db: Session, row: AcquisitionRow, actor_id: int) -> AcquisitionRowDetailResponse:
    ddt_document = get_document(db, row.document_ddt_id)
    if not ddt_document.pages:
        ddt_document = _index_document_from_path(db, ddt_document)

    extracted_count = 0
    ddt_matches = _detect_ddt_core_matches(ddt_document.pages)
    for field_name, match in ddt_matches.items():
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

    if row.cdq is None:
        if "cdq" in ddt_matches:
            row.cdq = _string_or_none(ddt_matches["cdq"]["final"])
        elif "numero_certificato_ddt" in ddt_matches:
            row.cdq = _string_or_none(ddt_matches["numero_certificato_ddt"]["final"])
    if row.colata is None and "colata" in ddt_matches:
        row.colata = _string_or_none(ddt_matches["colata"]["final"])
    if row.peso is None and "peso" in ddt_matches:
        row.peso = _string_or_none(ddt_matches["peso"]["final"])

    if row.document_certificato_id is not None:
        certificate_document = get_document(db, row.document_certificato_id)
        if not certificate_document.pages:
            certificate_document = _index_document_from_path(db, certificate_document)
        certificate_matches = _detect_certificate_core_matches(certificate_document.pages)
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
        detect_standard_notes(db=db, row=refreshed_row, actor_id=actor_id)
        refreshed_row = get_acquisition_row(db, row.id)
    return serialize_acquisition_row_detail(refreshed_row)


def extract_ddt_fields_with_vision(
    db: Session,
    row: AcquisitionRow,
    *,
    actor_id: int,
    openai_api_key: str,
) -> AcquisitionRowDetailResponse:
    ddt_document = get_document(db, row.document_ddt_id)
    if not ddt_document.pages:
        ddt_document = _index_document_from_path(db, ddt_document)

    image_pages = [page for page in ddt_document.pages if page.immagine_pagina_storage_key]
    if not image_pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DDT has no image pages available for vision")

    crop_definitions = _build_ddt_safe_crops(image_pages)
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
    ddt_document: Document,
    certificate_document: Document | None,
) -> int | None:
    supplier_ids = {
        supplier_id
        for supplier_id in {explicit_supplier_id, ddt_document.fornitore_id, certificate_document.fornitore_id if certificate_document else None}
        if supplier_id is not None
    }
    if explicit_supplier_id is not None:
        _get_supplier(db, explicit_supplier_id)
    if len(supplier_ids) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier mismatch across row documents")
    return next(iter(supplier_ids), None)


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


def _document_storage_root() -> Path:
    return Path(settings.document_storage_root)


def _compute_block_states(row: AcquisitionRow) -> dict[str, str]:
    values_by_block: dict[str, list[ReadValue]] = {}
    for value in row.values:
        values_by_block.setdefault(value.blocco, []).append(value)

    return {
        "ddt": _compute_value_block_state(values_by_block.get("ddt", []), fallback="giallo" if row.document_ddt_id else "rosso"),
        "match": _compute_match_block_state(row),
        "chimica": _compute_value_block_state(values_by_block.get("chimica", [])),
        "proprieta": _compute_value_block_state(values_by_block.get("proprieta", [])),
        "note": _compute_value_block_state(values_by_block.get("note", [])),
    }


def _compute_match_block_state(row: AcquisitionRow) -> str:
    if row.certificate_match is not None:
        if row.certificate_match.stato == "confermato":
            return "verde"
        return "giallo"
    if row.document_certificato_id is not None:
        return "giallo"
    return "rosso"


def _compute_value_block_state(values: list[ReadValue], fallback: str = "rosso") -> str:
    if not values:
        return fallback
    if all(value.stato == "confermato" for value in values):
        return "verde"
    return "giallo"


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


def _render_page_image(storage_key: str, page: fitz.Page, page_number: int) -> str:
    relative_pdf_path = Path(storage_key)
    image_relative_path = Path("renders") / relative_pdf_path.parent / f"{relative_pdf_path.stem}_page_{page_number}.png"
    absolute_image_path = _document_storage_root() / image_relative_path
    absolute_image_path.parent.mkdir(parents=True, exist_ok=True)

    pixmap = page.get_pixmap(dpi=150, alpha=False)
    pixmap.save(str(absolute_image_path))
    return image_relative_path.as_posix()


def _build_ddt_safe_crops(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    crops: dict[str, dict[str, str | int]] = {}
    for page in pages:
        image_path = get_document_page_image_path(page)
        with Image.open(image_path) as image:
            width, height = image.size
            crop_specs = [
                ("upper", (0.08, 0.18, 0.92, 0.56)),
                ("lower", (0.08, 0.54, 0.92, 0.90)),
            ]
            for suffix, (left_ratio, top_ratio, right_ratio, bottom_ratio) in crop_specs:
                left = int(width * left_ratio)
                top = int(height * top_ratio)
                right = int(width * right_ratio)
                bottom = int(height * bottom_ratio)
                if right <= left or bottom <= top:
                    continue
                crop = image.crop((left, top, right, bottom))
                storage_key = _save_ddt_crop(page, crop, suffix)
                crop_label = f"page{page.numero_pagina}_{suffix}"
                crops[crop_label] = {
                    "page_id": page.id,
                    "page_number": page.numero_pagina,
                    "storage_key": storage_key,
                    "bbox": f"{left},{top},{right},{bottom}",
                }
    return crops


def _save_ddt_crop(page: DocumentPage, image: Image.Image, suffix: str) -> str:
    base_name = f"page_{page.numero_pagina}_{suffix}_{uuid4().hex[:12]}.png"
    relative_path = Path("crops") / "ddt_vision" / datetime.now(UTC).strftime("%Y/%m/%d") / base_name
    absolute_path = _document_storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(absolute_path, format="PNG")
    return relative_path.as_posix()


def _extract_ddt_fields_from_openai(
    crops: dict[str, dict[str, str | int]],
    *,
    openai_api_key: str,
) -> dict[str, dict[str, str | None]]:
    client = OpenAI(api_key=openai_api_key)
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                "Leggi solo i ritagli del corpo di un DDT metallurgico. "
                "Non inferire dati assenti. Restituisci JSON puro con queste chiavi: "
                "numero_certificato_ddt, cdq, colata, peso, diametro, ordine. "
                "Ogni chiave deve essere un oggetto con campi value, evidence, source_crop. "
                "Usa null se il dato non e' leggibile o se sei incerto. "
                "Se trovi 'Cert.' o 'Certificato' sul DDT, popolalo in numero_certificato_ddt. "
                "Popola cdq solo se trovi una sigla o valore esplicitamente etichettato come CdQ/C.d.Q.; "
                "non usare stringhe normative come EN 10204 3.1, Inspection Certificate o riferimenti ASTM/AMS. "
                "Per il peso, usa solo il peso netto della singola riga materiale; "
                "non usare totali o riepiloghi di packing list. "
                "Per il diametro, usa il valore associato alla riga materiale, ad esempio BARRA TONDA 75 -> 75. "
                "Usa source_crop esattamente come il label del ritaglio fornito."
            ),
        }
    ]

    for crop_label, crop in crops.items():
        crop_path = _resolve_storage_path(str(crop["storage_key"]))
        mime_type = "image/png"
        encoded = base64.b64encode(crop_path.read_bytes()).decode("utf-8")
        content.append({"type": "input_text", "text": f"Crop label: {crop_label}"})
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

    return _parse_openai_json_payload(response.output_text)


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

    cdq_value = _string_or_none(normalized.get("cdq", {}).get("value"))
    cdq_evidence = _string_or_none(normalized.get("cdq", {}).get("evidence"))
    if cdq_value is not None and _looks_like_invalid_cdq(cdq_value, cdq_evidence):
        normalized["cdq"] = {
            "value": None,
            "evidence": cdq_evidence,
            "source_crop": _string_or_none(normalized.get("cdq", {}).get("source_crop")),
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

    return normalized


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


def _is_revisable_chatgpt_ddt_value(row: AcquisitionRow, field_name: str) -> bool:
    for value in row.values:
        if value.blocco != "ddt" or value.campo != field_name:
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

    row.cdq = _final_value_for_row(value_map.get("cdq")) or _final_value_for_row(value_map.get("numero_certificato_ddt"))
    row.colata = _final_value_for_row(value_map.get("colata"))
    row.peso = _final_value_for_row(value_map.get("peso"))
    row.diametro = _final_value_for_row(value_map.get("diametro"))
    row.ordine = _final_value_for_row(value_map.get("ordine"))


def _final_value_for_row(value: ReadValue | None) -> str | None:
    if value is None:
        return None
    return _string_or_none(value.valore_finale or value.valore_standardizzato or value.valore_grezzo)


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

    existing.valore_grezzo = valore_grezzo
    existing.valore_standardizzato = valore_standardizzato
    existing.valore_finale = valore_finale
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


def _detect_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        lines = _page_lines(page)
        for line in lines:
            normalized_line = line.lower()
            if "numero_certificato_ddt" not in matches:
                cert_number = _extract_certificate_number(normalized_line)
                if cert_number is not None:
                    matches["numero_certificato_ddt"] = _build_match(page.id, line, cert_number)
            if "cdq" not in matches:
                explicit_cdq = _extract_by_keywords(normalized_line, ("cdq",))
                if explicit_cdq is not None:
                    matches["cdq"] = _build_match(page.id, line, explicit_cdq)
            if "colata" not in matches:
                colata = _extract_by_keywords(normalized_line, ("colata", "col.", "col "))
                if colata is not None:
                    matches["colata"] = _build_match(page.id, line, colata)
            if "peso" not in matches:
                weight = _extract_weight_from_line(normalized_line)
                if weight is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(weight))
    return matches


def _detect_certificate_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        lines = _page_lines(page)
        for line in lines:
            normalized_line = line.lower()
            if "numero_certificato_certificato" not in matches:
                cert_number = _extract_certificate_number(normalized_line)
                if cert_number is not None:
                    matches["numero_certificato_certificato"] = _build_match(page.id, line, cert_number)
            if "colata_certificato" not in matches:
                colata = _extract_by_keywords(normalized_line, ("cast", "charge", "batch", "colata", "heat"))
                if colata is not None:
                    matches["colata_certificato"] = _build_match(page.id, line, colata)
            if "peso_certificato" not in matches:
                weight = _extract_weight_from_line(normalized_line)
                if weight is not None:
                    matches["peso_certificato"] = _build_match(page.id, line, _normalize_weight(weight))
    return matches


def _page_lines(page: DocumentPage) -> list[str]:
    page_text = page.testo_estratto or page.ocr_text or ""
    return [line.strip() for line in page_text.splitlines() if line.strip()]


def _build_match(page_id: int, snippet: str, value: str) -> dict[str, str | int]:
    return {
        "page_id": page_id,
        "snippet": snippet,
        "standardized": value,
        "final": value,
    }


def _extract_certificate_number(line: str) -> str | None:
    pattern = re.compile(r"(?:cert(?:ificate)?|cdq)[^\w]{0,6}(?:n|no|nr|n°)?[^\w]{0,6}([a-z0-9][a-z0-9/-]{2,})")
    match = pattern.search(line)
    if match is None:
        return None
    return match.group(1).upper()


def _extract_by_keywords(line: str, keywords: tuple[str, ...]) -> str | None:
    if not any(keyword in line for keyword in keywords):
        return None
    pattern = re.compile(r"(?:[:=\-]|\b)([a-z0-9][a-z0-9/-]{2,})\s*$")
    tail_match = pattern.search(line)
    if tail_match is not None:
        return tail_match.group(1).upper()

    token_pattern = re.compile(r"([a-z0-9][a-z0-9/-]{2,})")
    tokens = token_pattern.findall(line)
    for token in reversed(tokens):
        if token not in {"cast", "charge", "batch", "colata", "heat", "cdq", "cert", "certificate"}:
            return token.upper()
    return None


def _extract_weight_from_line(line: str) -> str | None:
    if not any(keyword in line for keyword in ("net weight", "peso netto", "peso net", "netto", "kg")):
        return None
    matches = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?", line)
    if not matches:
        return None
    return matches[-1]


def _normalize_weight(value: str) -> str:
    return value.replace(",", ".")


def _string_or_none(value: str | int | None) -> str | None:
    if value is None:
        return None
    string_value = str(value).strip()
    return string_value or None


def _detect_note_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        page_text = page.testo_estratto or page.ocr_text or ""
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
    "Al",
    "Zr+Ti",
    "Mn+Cr",
    "Bi+Pb",
}


PROPERTY_FIELD_SET = {"HB", "Rp0.2", "Rm", "A%", "Rp0.2 / Rm", "IACS%"}


def _detect_chemistry_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        page_text = page.testo_estratto or page.ocr_text or ""
        if not page_text:
            continue
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        page_matches = _parse_chemistry_from_lines(lines, page.id)
        for field_name, payload in page_matches.items():
            matches.setdefault(field_name, payload)
    return matches


def _detect_property_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        page_text = page.testo_estratto or page.ocr_text or ""
        if not page_text:
            continue
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]

        spec_matches = _parse_properties_from_spec_lines(lines, page.id)
        compact_matches = _parse_properties_from_compact_lines(lines, page.id)

        for field_name, payload in {**compact_matches, **spec_matches}.items():
            matches.setdefault(field_name, payload)

    return matches


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
    for line in window:
        lowered = line.lower()
        if lowered.startswith("spec."):
            continue
        numbers = re.findall(r"\d+(?:[.,]\d+)?", line)
        if len(numbers) >= 4:
            candidate_line = line
            break

    if candidate_line is None:
        return matches

    numbers = re.findall(r"\d+(?:[.,]\d+)?", candidate_line)
    if len(numbers) < 4:
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
    return matches


def _extract_chemistry_header(line: str) -> list[str]:
    if any(marker in line.lower() for marker in ("chemical composition", "composizione chimica", "alloy", "charge", "notes", "mechanical")):
        return []
    tokens = re.findall(r"[A-Z][a-z]?(?:\+[A-Z][a-z]?)?", line)
    elements = [token for token in tokens if token in CHEMISTRY_FIELD_SET]
    if len(elements) < 3:
        return []
    return elements


def _find_chemistry_measurement_line(lines: list[str], start_index: int, expected_count: int) -> str | None:
    for candidate in lines[start_index : min(start_index + 4, len(lines))]:
        lowered = candidate.lower()
        if lowered.startswith("min") or lowered.startswith("max"):
            continue
        if any(marker in lowered for marker in ("spec.", "norm", "alloy", "charge", "notes", "mechanical")):
            continue
        values = re.findall(r"\d+(?:[.,]\d+)?|/|Other", candidate, flags=re.IGNORECASE)
        if len(values) >= min(expected_count, 3):
            return candidate
    return None


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
