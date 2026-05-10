from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuartaTaglioSyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    message: str | None
    total_ol: int
    total_cdq_rows: int
    started_at: datetime
    finished_at: datetime | None


class QuartaTaglioCertificateResponse(BaseModel):
    cdq: str
    colata: str | None
    cod_art: str | None
    qta_totale: float | None
    righe_materiale: int
    lotti_count: int
    cod_lotti: list[str]
    status_color: str
    status_message: str
    status_details: list[str]
    matching_row_ids: list[int]


class QuartaTaglioRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codice_registro: str
    data_registro: datetime | None
    cod_odp: str
    cod_art: str | None
    cdq: str
    colata: str | None
    qta_totale: float | None
    righe_materiale: int
    lotti_count: int
    cod_lotti: list[str]
    saldo: bool
    status_color: str
    status_message: str
    status_details: list[str]
    matching_row_ids: list[int]
    certificates: list[QuartaTaglioCertificateResponse] = Field(default_factory=list)
    seen_in_last_sync: bool
    first_seen_at: datetime
    last_seen_at: datetime


class QuartaTaglioListResponse(BaseModel):
    sync_run: QuartaTaglioSyncRunResponse
    items: list[QuartaTaglioRowResponse]


class QuartaTaglioMissingItemResponse(BaseModel):
    cdq: str
    colata: str | None = None
    status_color: str
    message: str
    details: list[str] = Field(default_factory=list)


class QuartaTaglioMaterialResponse(BaseModel):
    cdq: str
    colata: str | None = None
    cod_art: str | None = None
    qta_totale: float | None = None
    righe_materiale: int
    cod_lotti: list[str] = Field(default_factory=list)
    matching_row_ids: list[int] = Field(default_factory=list)


class QuartaTaglioStandardCandidateResponse(BaseModel):
    id: int
    code: str
    label: str
    confidence: str
    score: int
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QuartaTaglioAggregateValueResponse(BaseModel):
    field: str
    value: float | None = None
    method: str
    standard_min: float | None = None
    standard_max: float | None = None
    status: str
    message: str | None = None


class QuartaTaglioNoteResponse(BaseModel):
    code: str
    label: str
    value: str | None = None
    status: str
    message: str


class QuartaTaglioDetailResponse(BaseModel):
    cod_odp: str
    ready: bool
    status_color: str
    status_message: str
    header: dict[str, str | None]
    materials: list[QuartaTaglioMaterialResponse]
    missing_items: list[QuartaTaglioMissingItemResponse]
    standard_candidates: list[QuartaTaglioStandardCandidateResponse]
    selected_standard: QuartaTaglioStandardCandidateResponse | None = None
    selected_standard_confirmed: bool = False
    chemistry: list[QuartaTaglioAggregateValueResponse]
    properties: list[QuartaTaglioAggregateValueResponse]
    notes: list[QuartaTaglioNoteResponse]
    second_page_placeholder: bool = True


class QuartaTaglioStandardSelectionRequest(BaseModel):
    standard_id: int
