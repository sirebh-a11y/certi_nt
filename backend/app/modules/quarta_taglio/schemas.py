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
