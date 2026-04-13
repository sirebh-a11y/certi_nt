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


class ReaderDocumentPartResponse(BaseModel):
    document_type: Literal["ddt", "certificato"]
    part_key: str
    label: str
    kind: Literal["header", "identity", "table", "notes", "material_rows", "packing_list", "unknown"]
    page_id: int | None = None
    snippet: str | None = None
    bbox_hint: list[float] = Field(default_factory=list)
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


class ReaderRowSplitCandidateResponse(BaseModel):
    candidate_index: int
    supplier_key: str | None = None
    ddt_number: str | None = None
    cdq: str | None = None
    customer_code: str | None = None
    article_code: str | None = None
    lega: str | None = None
    diametro: str | None = None
    peso_netto: str | None = None
    colata: str | None = None
    lot_batch_no: str | None = None
    heat_no: str | None = None
    customer_order_no: str | None = None
    supplier_order_no: str | None = None
    product_code: str | None = None
    snippets: list[str] = Field(default_factory=list)


class ReaderPlanResponse(BaseModel):
    row_id: int
    template: ReaderTemplateSummaryResponse
    local_pipeline: list[str] = Field(default_factory=list)
    masking_rules: list[str] = Field(default_factory=list)
    decision_policy: list[str] = Field(default_factory=list)
    row_split_hint: ReaderRowSplitHintResponse
    row_split_candidates: list[ReaderRowSplitCandidateResponse] = Field(default_factory=list)
    ddt_part_hints: list[ReaderDocumentPartResponse] = Field(default_factory=list)
    certificate_part_hints: list[ReaderDocumentPartResponse] = Field(default_factory=list)
    ddt_table_insights: list[ReaderTableInsightResponse] = Field(default_factory=list)
    certificate_table_insights: list[ReaderTableInsightResponse] = Field(default_factory=list)
    openai_double_check: OpenAIDoubleCheckEstimateResponse


class DocumentRowSplitPlanResponse(BaseModel):
    document_id: int
    template: ReaderTemplateSummaryResponse
    row_split_hint: ReaderRowSplitHintResponse
    row_split_candidates: list[ReaderRowSplitCandidateResponse] = Field(default_factory=list)
    document_part_hints: list[ReaderDocumentPartResponse] = Field(default_factory=list)
