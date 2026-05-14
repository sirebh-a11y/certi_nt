from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session, joinedload

from app.modules.acquisition.models import AcquisitionRow
from app.modules.suppliers.models import Supplier  # noqa: F401
from app.modules.supplier_kpi.schemas import (
    SupplierKpiMetrics,
    SupplierKpiMonthBucket,
    SupplierKpiSummaryResponse,
    SupplierKpiSupplierBucket,
)

MONTH_LABELS = {
    1: "Gen",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mag",
    6: "Giu",
    7: "Lug",
    8: "Ago",
    9: "Set",
    10: "Ott",
    11: "Nov",
    12: "Dic",
}


@dataclass
class _Accumulator:
    kg: Decimal = Decimal("0")
    total: int = 0
    accepted: int = 0
    reserve: int = 0
    rejected: int = 0
    unvalued: int = 0
    delays: list[int] = field(default_factory=list)
    control_times: list[int] = field(default_factory=list)

    def add(self, row: AcquisitionRow) -> None:
        self.total += 1
        self.kg += _parse_decimal(row.peso)

        if row.qualita_valutazione == "accettato":
            self.accepted += 1
        elif row.qualita_valutazione == "accettato_con_riserva":
            self.reserve += 1
        elif row.qualita_valutazione == "respinto":
            self.rejected += 1
        else:
            self.unvalued += 1

        if row.qualita_data_ricezione and row.qualita_data_richiesta:
            self.delays.append((row.qualita_data_ricezione - row.qualita_data_richiesta).days)
        if row.qualita_data_ricezione and row.qualita_data_accettazione:
            self.control_times.append(_business_days_delta(row.qualita_data_ricezione, row.qualita_data_accettazione))

    def to_metrics(self) -> SupplierKpiMetrics:
        return SupplierKpiMetrics(
            tonnellate=round(float(self.kg / Decimal("1000")), 3),
            lotti_totali=self.total,
            lotti_accettati=self.accepted,
            lotti_deroga=self.reserve,
            lotti_scarti=self.rejected,
            lotti_non_valutati=self.unvalued,
            ritardo_medio_giorni=_average(self.delays),
            tempo_medio_controllo_giorni=_average(self.control_times),
        )


def build_supplier_kpi_summary(
    db: Session,
    *,
    year: int,
    supplier_id: int | None = None,
    month: int | None = None,
) -> SupplierKpiSummaryResponse:
    query = (
        db.query(AcquisitionRow)
        .options(joinedload(AcquisitionRow.supplier))
        .filter(AcquisitionRow.validata_finale.is_(True))
        .filter(AcquisitionRow.qualita_data_ricezione.is_not(None))
    )
    query = query.filter(AcquisitionRow.qualita_data_ricezione >= date(year, 1, 1))
    query = query.filter(AcquisitionRow.qualita_data_ricezione <= date(year, 12, 31))
    if supplier_id is not None:
        query = query.filter(AcquisitionRow.fornitore_id == supplier_id)

    year_rows = query.all()
    rows = [
        row
        for row in year_rows
        if month is None or (row.qualita_data_ricezione and row.qualita_data_ricezione.month == month)
    ]

    total_accumulator = _Accumulator()
    supplier_accumulators: dict[tuple[int | None, str], _Accumulator] = defaultdict(_Accumulator)
    month_accumulators: dict[int, _Accumulator] = defaultdict(_Accumulator)

    for row in rows:
        supplier_name = _supplier_name(row)
        supplier_key = (row.fornitore_id, supplier_name)
        total_accumulator.add(row)
        supplier_accumulators[supplier_key].add(row)

    for row in year_rows:
        if row.qualita_data_ricezione:
            month_accumulators[row.qualita_data_ricezione.month].add(row)

    by_supplier = [
        SupplierKpiSupplierBucket(supplier_id=key[0], fornitore=key[1], metrics=accumulator.to_metrics())
        for key, accumulator in supplier_accumulators.items()
    ]
    by_supplier.sort(key=lambda item: (-item.metrics.tonnellate, item.fornitore.lower()))

    by_month = [
        SupplierKpiMonthBucket(
            month=month,
            label=MONTH_LABELS[month],
            metrics=month_accumulators[month].to_metrics(),
        )
        for month in range(1, 13)
    ]

    return SupplierKpiSummaryResponse(
        year=year,
        supplier_id=supplier_id,
        generated_at=datetime.now(timezone.utc),
        totals=total_accumulator.to_metrics(),
        by_supplier=by_supplier,
        by_month=by_month,
    )


def _supplier_name(row: AcquisitionRow) -> str:
    if row.supplier and row.supplier.ragione_sociale:
        return row.supplier.ragione_sociale
    if row.fornitore_raw:
        return row.fornitore_raw
    return "Senza fornitore"


def _parse_decimal(value: str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    normalized = str(value).strip().replace(" ", "")
    if not normalized:
        return Decimal("0")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "." in normalized:
        parts = normalized.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return Decimal("0")


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _business_days_delta(start: date, end: date) -> int:
    if end < start:
        return -_business_days_delta(end, start)
    current = start
    count = 0
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current = date.fromordinal(current.toordinal() + 1)
    return max(count - 1, 0)
