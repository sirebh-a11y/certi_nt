"""Read-only contract for the persistent DDT work queue."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DdtState = Literal["completed", "to_link", "quality_rejected", "waiting_incoming", "word_ready", "ready", "review"]
DdtScope = Literal["active", "completed", "all"]


class DdtWorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_documento: str
    id_riga_doc: str
    rif_lotto_alfanum: str | None
    cod_odp: str | None
    cod_f3: str | None
    ddt_raw: str | None
    ddt_date: date | None
    cliente: str | None
    ordine_cliente: str | None
    conferma_ordine: str | None
    quantita: Decimal | None
    first_seen_at: datetime
    last_seen_at: datetime
    source_present: bool
    source_review_reason: str | None
    certification_unit_key: str | None
    state: DdtState
    label: str
    reasons: list[str] = Field(default_factory=list)
    incoming_row_ids: list[int] = Field(default_factory=list)
    certificate_id: int | None = None
    word_candidate_id: int | None = None
    # "ready" means Incoming-ready, not permission to bypass standard/PDF checks.
    incoming_ready: bool = False


class DdtSyncAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None


class DdtQueueSyncResponse(BaseModel):
    enabled: bool
    last_attempt: DdtSyncAttemptResponse | None = None
    last_success: DdtSyncAttemptResponse | None = None


class DdtQueueCountersResponse(BaseModel):
    # Source filters apply; scope/state/pagination do not change these counters.
    total: int
    active: int
    by_state: dict[DdtState, int]
    sync: DdtQueueSyncResponse


class DdtQueueResponse(DdtQueueCountersResponse):
    total_items: int
    limit: int
    offset: int
    items: list[DdtWorkItemResponse]
