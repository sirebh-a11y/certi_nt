from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReaderTemplateSummaryResponse(BaseModel):
    supplier_key: str | None
    supplier_display_name: str | None
    ddt_template_id: str | None
    certificate_template_id: str | None
    strong_match_fields: list[str] = Field(default_factory=list)
    openai_double_check_blocks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReaderTableInsightResponse(BaseModel):
    document_type: Literal["ddt", "certificato"]
    page_id: int
    orientation: Literal["horizontal", "vertical", "unknown"]
    measured_line_count: int
    min_line_count: int
    max_line_count: int
    notes: list[str] = Field(default_factory=list)


class OpenAIDoubleCheckEstimateResponse(BaseModel):
    model_default: str
    escalation_model: str
    recommended_detail: Literal["low", "high"]
    blocked_without_consent: bool
    planned_crops: int
    estimated_input_tokens: int
    estimated_input_cost_usd: float
    notes: list[str] = Field(default_factory=list)


class ReaderRowSplitHintResponse(BaseModel):
    needed: bool
    estimated_rows: int | None = None
    reason: str | None = None
    signals: list[str] = Field(default_factory=list)


class ReaderPlanResponse(BaseModel):
    row_id: int
    template: ReaderTemplateSummaryResponse
    local_pipeline: list[str] = Field(default_factory=list)
    masking_rules: list[str] = Field(default_factory=list)
    decision_policy: list[str] = Field(default_factory=list)
    row_split_hint: ReaderRowSplitHintResponse
    ddt_table_insights: list[ReaderTableInsightResponse] = Field(default_factory=list)
    certificate_table_insights: list[ReaderTableInsightResponse] = Field(default_factory=list)
    openai_double_check: OpenAIDoubleCheckEstimateResponse
