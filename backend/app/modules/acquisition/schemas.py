from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DocumentType = Literal["ddt", "certificato"]
DocumentStatus = Literal["caricato", "indicizzato", "letto", "errore"]
DocumentOrigin = Literal["utente", "import", "sistema"]
DocumentUploadState = Literal["temporaneo", "persistente"]
BlockName = Literal["ddt", "match", "chimica", "proprieta", "note"]
EvidenceType = Literal["testo", "crop", "tabella", "cella", "bbox", "pagina_mascherata"]
ExtractionMethod = Literal["pdf_text", "ocr", "regex", "parser_tabella", "chatgpt", "utente", "sistema"]
TechnicalState = Literal["verde", "giallo", "rosso"]
WorkflowState = Literal["nuova", "in_lavorazione", "validata_quality", "riaperta"]
PriorityState = Literal["alta", "media", "bassa"]
ReadValueState = Literal["proposto", "corretto", "confermato"]
DocumentSource = Literal["ddt", "certificato", "ddt_certificato", "utente", "db_esterno", "calcolato"]
MatchState = Literal["proposto", "confermato", "cambiato"]
MatchSource = Literal["sistema", "chatgpt", "utente", "archivio"]
CandidateState = Literal["candidato", "scartato", "scelto"]
AutomationRunState = Literal["in_coda", "in_esecuzione", "completato", "errore"]


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DocumentCreateRequest(BaseModel):
    tipo_documento: DocumentType
    stato_upload: DocumentUploadState = "persistente"
    upload_batch_id: str | None = Field(default=None, max_length=64)
    scadenza_batch: datetime | None = None
    fornitore_id: int | None = None
    nome_file_originale: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=1, max_length=512)
    hash_file: str | None = Field(default=None, max_length=128)
    mime_type: str | None = Field(default=None, max_length=255)
    numero_pagine: int | None = Field(default=None, ge=1)
    stato_elaborazione: DocumentStatus = "caricato"
    origine_upload: DocumentOrigin = "utente"
    documento_padre_id: int | None = None

    @field_validator("nome_file_originale", "storage_key", "hash_file", "mime_type", "upload_batch_id")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class DocumentPageCreateRequest(BaseModel):
    numero_pagina: int = Field(ge=1)
    larghezza: float | None = Field(default=None, ge=0)
    altezza: float | None = Field(default=None, ge=0)
    rotazione: int | None = None
    testo_estratto: str | None = None
    ocr_text: str | None = None
    immagine_pagina_storage_key: str | None = Field(default=None, max_length=512)
    stato_estrazione: str = Field(default="non_elaborata", max_length=64)
    hash_render: str | None = Field(default=None, max_length=128)

    @field_validator("testo_estratto", "ocr_text", "immagine_pagina_storage_key", "hash_render")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    numero_pagina: int
    larghezza: float | None
    altezza: float | None
    rotazione: int | None
    testo_estratto: str | None
    ocr_text: str | None
    immagine_pagina_storage_key: str | None
    image_url: str | None
    stato_estrazione: str
    hash_render: str | None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_documento: str
    stato_upload: str
    upload_batch_id: str | None
    scadenza_batch: datetime | None
    fornitore_id: int | None
    fornitore_nome: str | None
    nome_file_originale: str
    storage_key: str
    file_url: str
    hash_file: str | None
    mime_type: str | None
    numero_pagine: int | None
    data_upload: datetime
    utente_upload_id: int | None
    stato_elaborazione: str
    origine_upload: str
    documento_padre_id: int | None


class DocumentDetailResponse(DocumentResponse):
    pages: list[DocumentPageResponse]


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentBatchErrorResponse(BaseModel):
    file_name: str
    detail: str


class DocumentBatchUploadResponse(BaseModel):
    requested_count: int
    uploaded_count: int
    failed_count: int
    upload_batch_id: str | None
    uploaded: list[DocumentResponse]
    failed: list[DocumentBatchErrorResponse]


class CurrentUploadBatchResponse(BaseModel):
    upload_batch_id: str | None
    items: list[DocumentResponse]


class AutonomousRunStartRequest(BaseModel):
    ddt_document_ids: list[int] = Field(default_factory=list)
    certificate_document_ids: list[int] = Field(default_factory=list)
    usa_ddt_vision: bool = True
    usa_intervento_ai: bool = False


class AutonomousRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stato: AutomationRunState
    fase_corrente: str
    messaggio_corrente: str | None
    totale_documenti_ddt: int
    totale_documenti_certificato: int
    totale_righe_target: int
    righe_create: int
    righe_processate: int
    match_proposti: int
    chimica_rilevata: int
    proprieta_rilevate: int
    note_rilevate: int
    usa_ddt_vision: bool
    current_row_id: int | None
    current_document_name: str | None
    ultimo_errore: str | None
    triggered_by_user_id: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class AcquisitionRowCreateRequest(BaseModel):
    document_ddt_id: int | None = None
    document_certificato_id: int | None = None
    cdq: str | None = Field(default=None, max_length=128)
    fornitore_id: int | None = None
    fornitore_raw: str | None = Field(default=None, max_length=255)
    lega_base: str | None = Field(default=None, max_length=128)
    lega_designazione: str | None = Field(default=None, max_length=128)
    variante_lega: str | None = Field(default=None, max_length=128)
    diametro: str | None = Field(default=None, max_length=128)
    colata: str | None = Field(default=None, max_length=128)
    ddt: str | None = Field(default=None, max_length=128)
    peso: str | None = Field(default=None, max_length=128)
    ordine: str | None = Field(default=None, max_length=128)
    data_documento: date | None = None
    note_documento: str | None = None
    stato_tecnico: TechnicalState = "rosso"
    stato_workflow: WorkflowState = "nuova"
    priorita_operativa: PriorityState = "media"
    validata_finale: bool = False

    @field_validator(
        "cdq",
        "fornitore_raw",
        "lega_base",
        "lega_designazione",
        "variante_lega",
        "diametro",
        "colata",
        "ddt",
        "peso",
        "ordine",
        "note_documento",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class AcquisitionRowUpdateRequest(BaseModel):
    document_certificato_id: int | None = None
    cdq: str | None = Field(default=None, max_length=128)
    fornitore_id: int | None = None
    fornitore_raw: str | None = Field(default=None, max_length=255)
    lega_base: str | None = Field(default=None, max_length=128)
    lega_designazione: str | None = Field(default=None, max_length=128)
    variante_lega: str | None = Field(default=None, max_length=128)
    diametro: str | None = Field(default=None, max_length=128)
    colata: str | None = Field(default=None, max_length=128)
    ddt: str | None = Field(default=None, max_length=128)
    peso: str | None = Field(default=None, max_length=128)
    ordine: str | None = Field(default=None, max_length=128)
    data_documento: date | None = None
    note_documento: str | None = None
    stato_tecnico: TechnicalState | None = None
    stato_workflow: WorkflowState | None = None
    priorita_operativa: PriorityState | None = None
    validata_finale: bool | None = None

    @field_validator(
        "cdq",
        "fornitore_raw",
        "lega_base",
        "lega_designazione",
        "variante_lega",
        "diametro",
        "colata",
        "ddt",
        "peso",
        "ordine",
        "note_documento",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class DocumentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_documento: str
    nome_file_originale: str
    storage_key: str
    file_url: str


class DocumentEvidenceCreateRequest(BaseModel):
    document_id: int
    document_page_id: int | None = None
    blocco: BlockName
    tipo_evidenza: EvidenceType
    bbox: str | None = Field(default=None, max_length=255)
    testo_grezzo: str | None = None
    storage_key_derivato: str | None = Field(default=None, max_length=512)
    metodo_estrazione: ExtractionMethod
    mascherato: bool = False
    confidenza: float | None = Field(default=None, ge=0, le=1)

    @field_validator("bbox", "testo_grezzo", "storage_key_derivato")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class DocumentEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    document_page_id: int | None
    acquisition_row_id: int | None
    blocco: str
    tipo_evidenza: str
    bbox: str | None
    testo_grezzo: str | None
    storage_key_derivato: str | None
    metodo_estrazione: str
    mascherato: bool
    confidenza: float | None
    data_creazione: datetime
    utente_creazione_id: int | None


class ReadValueUpsertRequest(BaseModel):
    blocco: BlockName
    campo: str = Field(min_length=1, max_length=128)
    valore_grezzo: str | None = None
    valore_standardizzato: str | None = None
    valore_finale: str | None = None
    stato: ReadValueState = "proposto"
    document_evidence_id: int | None = None
    metodo_lettura: ExtractionMethod
    fonte_documentale: DocumentSource
    confidenza: float | None = Field(default=None, ge=0, le=1)

    @field_validator("campo", "valore_grezzo", "valore_standardizzato", "valore_finale")
    @classmethod
    def normalize_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class ReadValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_row_id: int
    blocco: str
    campo: str
    valore_grezzo: str | None
    valore_standardizzato: str | None
    valore_finale: str | None
    stato: str
    document_evidence_id: int | None
    metodo_lettura: str
    fonte_documentale: str
    confidenza: float | None
    utente_ultima_modifica_id: int | None
    timestamp_ultima_modifica: datetime


class MatchCandidateRequest(BaseModel):
    document_certificato_id: int
    rank: int = Field(default=1, ge=1)
    motivo_breve: str | None = Field(default=None, max_length=255)
    fonte_proposta: MatchSource = "sistema"
    stato: CandidateState = "candidato"

    @field_validator("motivo_breve")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class MatchCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_certificato_id: int
    document_certificato_id: int
    rank: int
    motivo_breve: str | None
    fonte_proposta: str
    stato: str


class MatchUpsertRequest(BaseModel):
    document_certificato_id: int
    stato: MatchState = "proposto"
    motivo_breve: str | None = Field(default=None, max_length=255)
    fonte_proposta: MatchSource = "sistema"
    candidates: list[MatchCandidateRequest] = Field(default_factory=list)

    @field_validator("motivo_breve")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_row_id: int
    document_certificato_id: int
    stato: str
    motivo_breve: str | None
    fonte_proposta: str
    utente_conferma_id: int | None
    timestamp: datetime
    candidates: list[MatchCandidateResponse]


class AcquisitionHistoryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_row_id: int
    blocco: str
    azione: str
    utente_id: int | None
    timestamp: datetime
    nota_breve: str | None


class AcquisitionValueHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_row_id: int
    value_id: int | None
    blocco: str
    campo: str
    valore_prima: str | None
    valore_dopo: str | None
    utente_id: int | None
    timestamp: datetime


class AcquisitionRowListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_ddt_id: int | None
    document_certificato_id: int | None
    cdq: str | None
    fornitore_id: int | None
    fornitore_nome: str | None
    fornitore_raw: str | None
    lega_base: str | None
    lega_designazione: str | None
    variante_lega: str | None
    diametro: str | None
    colata: str | None
    ddt: str | None
    peso: str | None
    ordine: str | None
    data_documento: date | None
    ddt_data_upload: datetime | None
    note_documento: str | None
    stato_tecnico: str
    stato_workflow: str
    priorita_operativa: str
    validata_finale: bool
    block_states: dict[str, str]
    match_state: str
    certificate_file_name: str | None
    ddt_confirmed_fields: list[str]
    ddt_pending_fields: list[str]
    ddt_missing_fields: list[str]
    created_at: datetime
    updated_at: datetime


class AcquisitionRowDetailResponse(AcquisitionRowListItemResponse):
    ddt_document: DocumentSummaryResponse | None
    certificate_document: DocumentSummaryResponse | None
    evidences: list[DocumentEvidenceResponse]
    values: list[ReadValueResponse]
    certificate_match: MatchResponse | None
    history_events: list[AcquisitionHistoryEventResponse]
    value_history: list[AcquisitionValueHistoryResponse]


class AcquisitionRowListResponse(BaseModel):
    items: list[AcquisitionRowListItemResponse]


class DocumentSplitRowsCreateResponse(BaseModel):
    document_id: int
    created_count: int
    created_rows: list[AcquisitionRowDetailResponse]
