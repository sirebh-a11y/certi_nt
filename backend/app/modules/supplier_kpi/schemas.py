from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SupplierKpiMetrics(BaseModel):
    tonnellate: float
    lotti_totali: int
    lotti_accettati: int
    lotti_deroga: int
    lotti_scarti: int
    lotti_non_valutati: int
    ritardo_medio_giorni: float | None
    tempo_medio_controllo_giorni: float | None


class SupplierKpiSupplierBucket(BaseModel):
    supplier_id: int | None
    fornitore: str
    metrics: SupplierKpiMetrics


class SupplierKpiMonthBucket(BaseModel):
    month: int
    label: str
    metrics: SupplierKpiMetrics


class SupplierKpiSummaryResponse(BaseModel):
    year: int
    supplier_id: int | None
    generated_at: datetime
    totals: SupplierKpiMetrics
    by_supplier: list[SupplierKpiSupplierBucket]
    by_month: list[SupplierKpiMonthBucket]
