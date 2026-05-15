from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

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

QUARTER_MONTHS = {
    1: (1, 2, 3),
    2: (4, 5, 6),
    3: (7, 8, 9),
    4: (10, 11, 12),
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
    quarter: int | None = None,
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
    period_months = _period_months(month=month, quarter=quarter)
    rows = [
        row
        for row in year_rows
        if row.qualita_data_ricezione and row.qualita_data_ricezione.month in period_months
    ]

    total_accumulator = _Accumulator()
    supplier_accumulators: dict[tuple[int | None, str], _Accumulator] = defaultdict(_Accumulator)
    month_accumulators: dict[int, _Accumulator] = defaultdict(_Accumulator)

    for row in rows:
        supplier_name = _supplier_name(row)
        supplier_key = (row.fornitore_id, supplier_name)
        total_accumulator.add(row)
        supplier_accumulators[supplier_key].add(row)

    for row in rows:
        if row.qualita_data_ricezione:
            month_accumulators[row.qualita_data_ricezione.month].add(row)

    by_supplier = [
        SupplierKpiSupplierBucket(supplier_id=key[0], fornitore=key[1], metrics=accumulator.to_metrics())
        for key, accumulator in supplier_accumulators.items()
    ]
    by_supplier.sort(key=lambda item: (-item.metrics.tonnellate, item.fornitore.lower()))

    by_month = [
        SupplierKpiMonthBucket(
            month=period_month,
            label=MONTH_LABELS[period_month],
            metrics=month_accumulators[period_month].to_metrics(),
        )
        for period_month in period_months
    ]

    return SupplierKpiSummaryResponse(
        year=year,
        supplier_id=supplier_id,
        generated_at=datetime.now(timezone.utc),
        totals=total_accumulator.to_metrics(),
        by_supplier=by_supplier,
        by_month=by_month,
    )


def build_supplier_kpi_xlsx(
    db: Session,
    *,
    year: int,
    supplier_id: int | None = None,
    month: int | None = None,
    quarter: int | None = None,
) -> bytes:
    summary = build_supplier_kpi_summary(
        db=db,
        year=year,
        supplier_id=supplier_id,
        month=month,
        quarter=quarter,
    )
    period_label = _period_label(year=year, month=month, quarter=quarter)
    supplier_label = summary.by_supplier[0].fornitore if supplier_id and len(summary.by_supplier) == 1 else "Tutti i fornitori"

    sheets = [
        (
            "Sintesi periodo",
            [
                ["Periodo", period_label],
                ["Fornitore", supplier_label],
                [],
                ["Tonnellate", _format_decimal_it(summary.totals.tonnellate, digits=3)],
                ["Lotti totali", summary.totals.lotti_totali],
                ["Accettati", summary.totals.lotti_accettati],
                ["Accettati con riserva", summary.totals.lotti_deroga],
                ["Respinti", summary.totals.lotti_scarti],
                ["Ritardo medio", _format_decimal_it(summary.totals.ritardo_medio_giorni, digits=2), "giorni"],
                ["Tempo medio controllo", _format_decimal_it(summary.totals.tempo_medio_controllo_giorni, digits=2), "giorni lavorativi"],
            ],
        ),
        (
            "Fornitori",
            [
                [
                    "Fornitore",
                    "Tonnellate",
                    "Lotti",
                    "Accettati",
                    "Riserva",
                    "Respinti",
                    "Ritardo medio",
                    "Tempo controllo",
                ],
                *[
                    [
                        row.fornitore,
                        _format_decimal_it(row.metrics.tonnellate, digits=3),
                        row.metrics.lotti_totali,
                        row.metrics.lotti_accettati,
                        row.metrics.lotti_deroga,
                        row.metrics.lotti_scarti,
                        _format_decimal_it(row.metrics.ritardo_medio_giorni, digits=2),
                        _format_decimal_it(row.metrics.tempo_medio_controllo_giorni, digits=2),
                    ]
                    for row in summary.by_supplier
                ],
            ],
        ),
        (
            "Mesi",
            [
                ["Mese", "Lotti", "Accettati", "Riserva", "Respinti", "Tonnellate"],
                *[
                    [
                        row.label,
                        row.metrics.lotti_totali,
                        row.metrics.lotti_accettati,
                        row.metrics.lotti_deroga,
                        row.metrics.lotti_scarti,
                        _format_decimal_it(row.metrics.tonnellate, digits=3),
                    ]
                    for row in summary.by_month
                ],
            ],
        ),
    ]
    return _write_xlsx(sheets)


def _supplier_name(row: AcquisitionRow) -> str:
    if row.supplier and row.supplier.ragione_sociale:
        return row.supplier.ragione_sociale
    if row.fornitore_raw:
        return row.fornitore_raw
    return "Senza fornitore"


def _period_months(*, month: int | None, quarter: int | None) -> tuple[int, ...]:
    if month is not None:
        return (month,)
    if quarter is not None:
        return QUARTER_MONTHS.get(quarter, tuple(range(1, 13)))
    return tuple(range(1, 13))


def _period_label(*, year: int, month: int | None, quarter: int | None) -> str:
    if month is not None:
        return f"{MONTH_LABELS.get(month, 'Mese')} {year}"
    if quarter is not None:
        return f"Q{quarter} {year}"
    return f"Tutto anno {year}"


def _format_decimal_it(value: float | None, *, digits: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".replace(".", ",")


def _write_xlsx(sheets: list[tuple[str, list[list[object]]]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        archive.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>CertI_nt</dc:creator>
  <cp:lastModifiedBy>CertI_nt</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:modified>
</cp:coreProperties>""",
        )
        archive.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>CertI_nt</Application>
</Properties>""",
        )
        workbook_sheets = []
        workbook_rels = []
        overrides = []
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook_sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
            workbook_rels.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))

        archive.writestr(
            "[Content_Types].xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {''.join(overrides)}
</Types>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>{''.join(workbook_sheets)}</sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {''.join(workbook_rels)}
  <Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="0"/>
  <fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium9" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>""",
        )
    return output.getvalue()


def _sheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{''.join(xml_rows)}</sheetData>
</worksheet>"""


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


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
