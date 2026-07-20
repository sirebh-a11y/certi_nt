from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.acquisition.models import AcquisitionRow
from app.modules.suppliers.models import Supplier  # noqa: F401
from app.modules.supplier_kpi.schemas import (
    SupplierKpiMetrics,
    SupplierKpiMonthBucket,
    SupplierKpiSummaryResponse,
    SupplierKpiSupplierBucket,
)
from app.modules.supplier_calendar.service import business_days_delta, load_non_working_dates_for_ranges

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
    2: (1, 2, 3, 4, 5, 6),
    3: (1, 2, 3, 4, 5, 6, 7, 8, 9),
    4: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
}

INVALID_SHEET_NAME_CHARS = set("[]:*?/\\")

CHEMISTRY_EXPORT_FIELDS = [
    ("Si", ("si",)),
    ("Fe", ("fe",)),
    ("Cu", ("cu",)),
    ("Mn", ("mn",)),
    ("Mg", ("mg",)),
    ("Cr", ("cr",)),
    ("Ni", ("ni",)),
    ("Zn", ("zn",)),
    ("Ti", ("ti",)),
    ("Pb", ("pb",)),
    ("V", ("v",)),
    ("Bi", ("bi",)),
    ("Sn", ("sn",)),
    ("Zr", ("zr",)),
    ("Be", ("be",)),
    ("Zr+Ti", ("zr+ti", "zrti", "zr_ti")),
    ("Mn+Cr", ("mn+cr", "mncr", "mn_cr")),
    ("Bi+Pb", ("bi+pb", "bipb", "bi_pb")),
]

PROPERTY_EXPORT_FIELDS = [
    ("Rm", ("rm",)),
    ("Rp0.2", ("rp0.2", "rp02", "rp0,2", "rp 0.2", "rp 0,2")),
    ("A%", ("a%", "a", "a5", "a5%")),
    ("HB", ("hb",)),
    ("IACS%", ("iacs%", "iacs")),
    ("Rp0.2/Rm", ("rp0.2/rm", "rp02/rm", "rp0,2/rm", "rp_rm", "rp/rm")),
]


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

    def add(self, row: AcquisitionRow, non_working_dates: set[date] | None = None) -> None:
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
            self.control_times.append(
                business_days_delta(row.qualita_data_ricezione, row.qualita_data_accettazione, non_working_dates)
            )

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
    period_months = _period_months(month=month, quarter=quarter)
    rows = _filtered_kpi_rows(db, year=year, supplier_id=supplier_id, period_months=period_months)
    non_working_dates = load_non_working_dates_for_ranges(
        db,
        [(row.qualita_data_ricezione, row.qualita_data_accettazione) for row in rows],
    )

    total_accumulator = _Accumulator()
    supplier_accumulators: dict[tuple[int | None, str], _Accumulator] = defaultdict(_Accumulator)
    month_accumulators: dict[int, _Accumulator] = defaultdict(_Accumulator)

    for row in rows:
        supplier_name = _supplier_name(row)
        supplier_key = (row.fornitore_id, supplier_name)
        total_accumulator.add(row, non_working_dates)
        supplier_accumulators[supplier_key].add(row, non_working_dates)

    for row in rows:
        if row.qualita_data_ricezione:
            month_accumulators[row.qualita_data_ricezione.month].add(row, non_working_dates)

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
    period_months = _period_months(month=month, quarter=quarter)
    detail_rows = _filtered_kpi_rows(
        db,
        year=year,
        supplier_id=supplier_id,
        period_months=period_months,
        include_values=True,
    )
    non_working_dates = load_non_working_dates_for_ranges(
        db,
        [(row.qualita_data_ricezione, row.qualita_data_accettazione) for row in detail_rows],
    )

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
    sheets.extend(
        _supplier_detail_sheets(
            detail_rows,
            period_label=period_label,
            supplier_label=supplier_label,
            non_working_dates=non_working_dates,
        )
    )
    return _write_xlsx(sheets)


def _filtered_kpi_rows(
    db: Session,
    *,
    year: int,
    supplier_id: int | None,
    period_months: tuple[int, ...],
    include_values: bool = False,
) -> list[AcquisitionRow]:
    options = [joinedload(AcquisitionRow.supplier)]
    if include_values:
        options.append(selectinload(AcquisitionRow.values))
    query = (
        db.query(AcquisitionRow)
        .options(*options)
        .filter(AcquisitionRow.validata_finale.is_(True))
        .filter(AcquisitionRow.qualita_data_ricezione.is_not(None))
        .filter(AcquisitionRow.qualita_data_ricezione >= date(year, 1, 1))
        .filter(AcquisitionRow.qualita_data_ricezione <= date(year, 12, 31))
    )
    if supplier_id is not None:
        query = query.filter(AcquisitionRow.fornitore_id == supplier_id)

    rows = [
        row
        for row in query.all()
        if row.qualita_data_ricezione and row.qualita_data_ricezione.month in period_months
    ]
    rows.sort(key=lambda row: (_supplier_name(row).lower(), row.qualita_data_ricezione or date.min, row.id))
    return rows


def _supplier_detail_sheets(
    rows: list[AcquisitionRow],
    *,
    period_label: str,
    supplier_label: str,
    non_working_dates: set[date] | None = None,
) -> list[tuple[str, list[list[object]]]]:
    rows_by_supplier: dict[tuple[int | None, str], list[AcquisitionRow]] = defaultdict(list)
    for row in rows:
        rows_by_supplier[(row.fornitore_id, _supplier_name(row))].append(row)

    sheets: list[tuple[str, list[list[object]]]] = []
    used_names = {"Sintesi periodo", "Fornitori", "Mesi"}
    for (_supplier_id, name), supplier_rows in sorted(rows_by_supplier.items(), key=lambda item: item[0][1].lower()):
        sheet_name = _unique_sheet_name(_sanitize_sheet_name(name), used_names)
        used_names.add(sheet_name)
        sheets.append(
            (
                sheet_name,
                _supplier_detail_rows(
                    supplier_rows,
                    period_label=period_label,
                    supplier_label=name if supplier_label == "Tutti i fornitori" else supplier_label,
                    non_working_dates=non_working_dates,
                ),
            )
        )
    return sheets


def _supplier_detail_rows(
    rows: list[AcquisitionRow],
    *,
    period_label: str,
    supplier_label: str,
    non_working_dates: set[date] | None = None,
) -> list[list[object]]:
    headers = [
        "N.",
        "Data ricezione",
        "Data accettazione",
        "Fornitore",
        "Lega",
        "Ø",
        "CDQ",
        "Colata",
        "DDT",
        "Peso Kg",
        "Vs. ODV",
        "Data richiesta",
        "Tipo controllo",
        "Valutazione",
        "Note",
        "Ritardo giorni",
        "Tempo controllo giorni",
        *[label for label, _aliases in CHEMISTRY_EXPORT_FIELDS],
        *[label for label, _aliases in PROPERTY_EXPORT_FIELDS],
    ]
    table_rows = [
        [
            row.id,
            _format_date(row.qualita_data_ricezione),
            _format_date(row.qualita_data_accettazione),
            _supplier_name(row),
            _clean_cell(row.lega_base or row.lega_designazione),
            _clean_cell(row.diametro),
            _clean_cell(row.cdq),
            _clean_cell(row.colata),
            _clean_cell(row.ddt),
            _clean_cell(row.peso),
            _clean_cell(row.ordine),
            _format_date(row.qualita_data_richiesta),
            _quality_control_type_label(row.qualita_tipo_controllo),
            _quality_label(row.qualita_valutazione),
            _clean_cell(row.qualita_note),
            _delay_days(row),
            _control_time_days(row, non_working_dates),
            *[_read_value(row, "chimica", aliases) for _label, aliases in CHEMISTRY_EXPORT_FIELDS],
            *[_read_value(row, "proprieta", aliases) for _label, aliases in PROPERTY_EXPORT_FIELDS],
        ]
        for row in rows
    ]
    return [
        ["Fornitore", supplier_label],
        ["Periodo", period_label],
        ["Righe", len(rows)],
        [],
        headers,
        *table_rows,
    ]


def _sanitize_sheet_name(name: str) -> str:
    sanitized = "".join("_" if char in INVALID_SHEET_NAME_CHARS else char for char in name).strip()
    return (sanitized or "Fornitore")[:31]


def _unique_sheet_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        return name
    base = name[:28].rstrip() or "Foglio"
    counter = 2
    while True:
        candidate = f"{base}_{counter}"[:31]
        if candidate not in used_names:
            return candidate
        counter += 1


def _read_value(row: AcquisitionRow, block: str, aliases: tuple[str, ...]) -> str:
    alias_keys = {_field_key(alias) for alias in aliases}
    for value in row.values:
        if _field_key(value.blocco) == _field_key(block) and _field_key(value.campo) in alias_keys:
            return _clean_cell(value.valore_finale or value.valore_standardizzato or value.valore_grezzo)
    return "-"


def _field_key(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(char.lower() for char in str(value).strip() if char.isalnum())


def _format_date(value: date | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d/%m/%Y")


def _clean_cell(value: object | None) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"


def _quality_label(value: str | None) -> str:
    labels = {
        "accettato": "Accettato",
        "accettato_con_riserva": "Accettato con riserva",
        "respinto": "Respinto",
    }
    return labels.get(value or "", _clean_cell(value))


def _quality_control_type_label(value: str | None) -> str:
    labels = {
        "diretta": "Diretta",
        "inversa": "Inversa",
    }
    return labels.get(value or "", "")


def _delay_days(row: AcquisitionRow) -> str:
    if row.qualita_data_ricezione is None or row.qualita_data_richiesta is None:
        return "-"
    return str((row.qualita_data_ricezione - row.qualita_data_richiesta).days)


def _control_time_days(row: AcquisitionRow, non_working_dates: set[date] | None = None) -> str:
    if row.qualita_data_ricezione is None or row.qualita_data_accettazione is None:
        return "-"
    return str(business_days_delta(row.qualita_data_ricezione, row.qualita_data_accettazione, non_working_dates))


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
