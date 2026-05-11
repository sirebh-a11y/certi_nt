from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.core.users.models import User
from app.modules.quarta_taglio.schemas import QuartaTaglioDetailResponse


APP_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = APP_ROOT / "assets" / "certificates"
LOGO_PATH = ASSET_ROOT / "forgialluminio_logo.png"
QUALITY_MANAGER_SIGNATURE_PATH = ASSET_ROOT / "quality_manager_signature.png"


def build_forgialluminio_draft_docx(
    *,
    detail: QuartaTaglioDetailResponse,
    output_path: Path,
    draft_number: str,
    certified_by: User,
    quality_manager: User | None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(9)

    _add_header(document, detail=detail, draft_number=draft_number)
    _add_materials_table(document, detail=detail)
    _add_chemistry_table(document, detail=detail)
    _add_properties_table(document, detail=detail)
    _add_notes(document, detail=detail)
    _add_signatures(document, certified_by=certified_by, quality_manager=quality_manager)
    _add_second_page_placeholder(document)

    document.save(output_path)


def _add_header(document: Document, *, detail: QuartaTaglioDetailResponse, draft_number: str) -> None:
    header = detail.header or {}

    table = document.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _clear_table_borders(table)
    left, center, right = table.rows[0].cells
    if LOGO_PATH.exists():
        paragraph = center.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(str(LOGO_PATH), width=Inches(3.0))
    else:
        paragraph = center.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run("Forgialluminio3 s.r.l.").bold = True
    right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    p = right.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("Mod. 065 Rev. 01")
    run.font.size = Pt(6)
    p = right.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("Pag. 1 / 1")
    run.font.size = Pt(10)

    title_table = document.add_table(rows=1, cols=2)
    _clear_table_borders(title_table)
    title_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    left_title, right_title = title_table.rows[0].cells
    left_paragraph = left_title.paragraphs[0]
    left_run = left_paragraph.add_run("EN 10204 - 3.1")
    left_run.bold = True
    left_run.font.size = Pt(18)
    right_paragraph = right_title.paragraphs[0]
    right_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_run = right_paragraph.add_run(f"Certificate n°{draft_number} dated -")
    right_run.font.size = Pt(13)

    data_rows = [
        (("Purchaser:", "Cliente:", header.get("cliente")), ("Cod. F3:", "Cod. F3:", header.get("codice_f3"))),
        (("Description:", "Descrizione:", header.get("descrizione")), ("Drawing:", "Disegno:", header.get("disegno"))),
        (("Order.:", "Ordine:", header.get("ordine_cliente")), ("Confirm of order:", "C.d.O.:", header.get("conferma_ordine"))),
        (("D.d.T.:", "D.d.T.:", header.get("ddt")), ("Amount:", "Quantità:", header.get("quantita"))),
        (("", "", ""), ("", "", "")),
    ]
    _add_header_data_table(document, data_rows)


def _add_chemistry_intro(document: Document, *, detail: QuartaTaglioDetailResponse) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(8)
    run = paragraph.add_run("•  Chemical composition: acc. to EN UNI 573-3")
    run.bold = True
    run.font.size = Pt(13)

    info_table = document.add_table(rows=1, cols=3)
    _clear_table_borders(info_table)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    alloy_cell, charge_cell, ref_cell = info_table.rows[0].cells
    _add_inline_label_value(alloy_cell.paragraphs[0], "Alloy:", detail.selected_standard.label if detail.selected_standard else "-")
    _add_inline_label_value(charge_cell.paragraphs[0], "Charge:", detail.cod_odp)
    _add_inline_label_value(ref_cell.paragraphs[0], "Ref.:", "-")


def _add_materials_table(document: Document, *, detail: QuartaTaglioDetailResponse) -> None:
    _add_section_title(document, "Supplier certificates / Certificati fornitore")
    table = _new_table(document, ["CDQ", "Colata", "Cod. art.", "Quantita", "Lotti"])
    for item in detail.materials:
        row = table.add_row().cells
        row[0].text = item.cdq or "-"
        row[1].text = item.colata or "-"
        row[2].text = item.cod_art or "-"
        row[3].text = _format_value(item.qta_totale)
        row[4].text = ", ".join(item.cod_lotti or []) or "-"


def _add_chemistry_table(document: Document, *, detail: QuartaTaglioDetailResponse) -> None:
    _add_chemistry_intro(document, detail=detail)
    chemistry = [item for item in detail.chemistry if item.status != "not_in_standard"]
    if not chemistry:
        document.add_paragraph("No chemical elements available from selected standard.")
        return
    font_size = 9 if len(chemistry) <= 14 else 8
    table = _new_table(document, [""] + [item.field for item in chemistry])
    min_row = table.add_row().cells
    max_row = table.add_row().cells
    value_row = table.add_row().cells
    min_row[0].text = "min"
    max_row[0].text = "max"
    value_row[0].text = "value"
    for index, item in enumerate(chemistry, start=1):
        min_row[index].text = _format_value(item.standard_min)
        max_row[index].text = _format_value(item.standard_max)
        value_row[index].text = _format_value(item.value)
    _set_table_font(table, size=font_size)
    _bold_row(value_row)
    _set_table_width(table, Inches(7.1))


def _add_properties_table(document: Document, *, detail: QuartaTaglioDetailResponse) -> None:
    _add_section_title(document, "Mechanical properties / Proprieta meccaniche")
    properties = [item for item in detail.properties if item.value is not None or item.standard_min is not None or item.standard_max is not None]
    if not properties:
        document.add_paragraph("No mechanical properties available.")
        return
    table = _new_table(document, [""] + [item.field for item in properties])
    min_row = table.add_row().cells
    max_row = table.add_row().cells
    value_row = table.add_row().cells
    min_row[0].text = "min"
    max_row[0].text = "max"
    value_row[0].text = "value"
    for index, item in enumerate(properties, start=1):
        min_row[index].text = _format_value(item.standard_min)
        max_row[index].text = _format_value(item.standard_max)
        value_row[index].text = _format_value(item.value)
    _set_table_font(table, size=9)
    _bold_row(value_row)
    _set_table_width(table, Inches(min(6.4, 1.0 + len(properties) * 0.85)))


def _add_notes(document: Document, *, detail: QuartaTaglioDetailResponse) -> None:
    _add_section_title(document, "Notes")
    ok_notes = [item for item in detail.notes if item.status == "ok"]
    if not ok_notes:
        document.add_paragraph("No confirmed notes.")
        return
    for item in ok_notes:
        text = item.value
        if text:
            document.add_paragraph(text, style=None)


def _add_signatures(document: Document, *, certified_by: User, quality_manager: User | None) -> None:
    _add_section_title(document, "Signatures")
    table = document.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.cell(0, 0).text = "Certified by / Certificatore"
    table.cell(0, 1).text = "Quality Manager"
    table.cell(1, 0).text = certified_by.name
    qm_cell = table.cell(1, 1)
    qm_cell.text = quality_manager.name if quality_manager else "Da configurare"
    if QUALITY_MANAGER_SIGNATURE_PATH.exists():
        paragraph = qm_cell.add_paragraph()
        paragraph.add_run().add_picture(str(QUALITY_MANAGER_SIGNATURE_PATH), width=Inches(1.1))


def _add_second_page_placeholder(document: Document) -> None:
    document.add_page_break()
    _add_section_title(document, "Second page")
    document.add_paragraph("Placeholder seconda pagina. Da completare con le regole finali.")


def _add_section_title(document: Document, text: str) -> None:
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = 0.4
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(51, 51, 51)


def _add_box_table(document: Document, rows: list[tuple[tuple[str, object], tuple[str, object]]]) -> None:
    table = document.add_table(rows=0, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for left, right in rows:
        cells = table.add_row().cells
        cells[0].text = left[0]
        cells[1].text = _empty_dash(left[1])
        cells[2].text = right[0]
        cells[3].text = _empty_dash(right[1])
        for cell_index in (0, 2):
            for paragraph in cells[cell_index].paragraphs:
                for run in paragraph.runs:
                    run.bold = True
    _set_table_font(table, size=8)


def _add_header_data_table(document: Document, rows: list[tuple[tuple[str, str, object], tuple[str, str, object]]]) -> None:
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for left, right in rows:
        cells = table.add_row().cells
        _fill_header_data_cell(cells[0], left[0], left[1], left[2])
        _fill_header_data_cell(cells[1], right[0], right[1], right[2])
    _set_table_width(table, Inches(7.1))


def _fill_header_data_cell(cell, english_label: str, italian_label: str, value: object) -> None:
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if english_label:
        label_run = paragraph.add_run(f"{english_label} ")
        label_run.bold = True
        label_run.font.name = "Arial"
        label_run.font.size = Pt(14)
    if value not in (None, ""):
        value_run = paragraph.add_run(str(value))
        value_run.font.name = "Times New Roman"
        value_run.font.size = Pt(12)
    italian = cell.add_paragraph()
    italian.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = italian.add_run(italian_label)
    run.font.name = "Arial"
    run.font.size = Pt(9)


def _add_inline_label_value(paragraph, label: str, value: object) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label_run = paragraph.add_run(f"{label} ")
    label_run.bold = True
    label_run.font.name = "Times New Roman"
    label_run.font.size = Pt(12)
    value_run = paragraph.add_run(_empty_dash(value))
    value_run.font.name = "Times New Roman"
    value_run.font.size = Pt(12)


def _new_table(document: Document, headers: list[str]):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_cells = table.rows[0].cells
    for index, header in enumerate(headers):
        header_cells[index].text = header
        for paragraph in header_cells[index].paragraphs:
            for run in paragraph.runs:
                run.bold = True
    _set_table_font(table, size=8)
    return table


def _set_table_font(table, *, size: int) -> None:
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(size)


def _bold_row(cells) -> None:
    for cell in cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True


def _set_table_width(table, width) -> None:
    table.autofit = False
    table.allow_autofit = False
    column_count = len(table.columns)
    if not column_count:
        return
    column_width = width / column_count
    for column in table.columns:
        for cell in column.cells:
            cell.width = column_width


def _clear_table_borders(table) -> None:
    for row in table.rows:
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            borders = tc_pr.first_child_found_in("w:tcBorders")
            if borders is None:
                borders = OxmlElement("w:tcBorders")
                tc_pr.append(borders)
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                tag = f"w:{edge}"
                element = borders.find(qn(tag))
                if element is None:
                    element = OxmlElement(tag)
                    borders.append(element)
                element.set(qn("w:val"), "nil")

def _empty_dash(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _format_value(value: float | str | None) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".").replace(".", ",")
    return str(value)
