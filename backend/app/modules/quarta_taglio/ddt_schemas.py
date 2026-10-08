"""Queue read models and requests for manual DDT decisions."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DdtState = Literal["completed", "excluded", "to_link", "quality_rejected", "waiting_incoming", "word_ready", "ready", "review"]
DdtScope = Literal["active", "completed", "excluded", "all"]


class DdtDecisionRequest(BaseModel):
    action: Literal["exclude", "restore"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_decision_id: int = Field(ge=0)
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Inserire il motivo della decisione")
        return value


class DdtDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    reason: str
    actor_name: str
    created_at: datetime


class DdtPdfAction(BaseModel):
    id: int
    certificate_number: str
    pdf_file_name: str | None = None
    default_pdf_file_name: str
    word_source: str | None = None
    has_word: bool = True
    ddt: str
    cod_odp: str
    cod_f3: str


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
    # Calendar deadline for the queue only; not confirmation of external delivery.
    certification_due_date: date | None = None
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
    pdf_action: DdtPdfAction | None = None
    # "ready" means Incoming-ready, not permission to bypass standard/PDF checks.
    incoming_ready: bool = False
    operational_state: DdtState | None = None
    source_revision: str = ""
    latest_decision: DdtDecisionResponse | None = None
    exclusion_active: bool = False


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
