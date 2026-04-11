from __future__ import annotations

import re

from app.core.config import settings
from app.modules.acquisition.models import AcquisitionRow, Document
from app.modules.document_reader.decision_engine import build_default_decision_rules
from app.modules.document_reader.registry import resolve_supplier_template
from app.modules.document_reader.schemas import (
    DocumentRowSplitPlanResponse,
    OpenAIDoubleCheckEstimateResponse,
    ReaderPlanResponse,
    ReaderRowSplitCandidateResponse,
    ReaderRowSplitHintResponse,
    ReaderTableInsightResponse,
    ReaderTemplateSummaryResponse,
)
from app.modules.document_reader.table_analysis import analyze_measurement_table

GPT54_INPUT_USD_PER_1M = 2.50
LOW_DETAIL_IMAGE_TOKENS = 85


def _normalize_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _pdf_text_needs_ocr_fallback(value: str | None) -> bool:
    normalized = _normalize_text(value)
    if normalized is None:
        return True

    ascii_alnum_count = len(re.findall(r"[A-Za-z0-9]", normalized))
    extended_latin_count = len(re.findall(r"[À-ÿ]", normalized))
    word_count = len(normalized.split())

    if ascii_alnum_count == 0 and extended_latin_count >= 4:
        return True
    if extended_latin_count >= 6 and ascii_alnum_count < 12:
        return True
    if word_count <= 3 and extended_latin_count > ascii_alnum_count:
        return True
    return False


def build_reader_plan(row: AcquisitionRow) -> ReaderPlanResponse:
    template = resolve_supplier_template(
        row.supplier.ragione_sociale if row.supplier is not None else None,
        row.fornitore_raw,
        row.ddt_document.supplier.ragione_sociale if row.ddt_document and row.ddt_document.supplier else None,
        row.certificate_document.supplier.ragione_sociale if row.certificate_document and row.certificate_document.supplier else None,
    )

    ddt_insights = _build_document_table_insights(row.ddt_document, "ddt")
    certificate_insights = _build_document_table_insights(row.certificate_document, "certificato")
    planned_crops = _estimate_planned_crops(template, row)
    row_split_hint = _build_row_split_hint(row.ddt_document, template)
    row_split_candidates = _build_row_split_candidates(row.ddt_document, template)
    row_split_hint = _finalize_row_split_hint(row_split_hint, row_split_candidates, template)

    return ReaderPlanResponse(
        row_id=row.id,
        template=ReaderTemplateSummaryResponse(
            supplier_key=template.supplier_key if template else None,
            supplier_display_name=template.display_name if template else (row.supplier.ragione_sociale if row.supplier else row.fornitore_raw),
            ddt_template_id=template.ddt_template_id if template else None,
            certificate_template_id=template.certificate_template_id if template else None,
            strong_match_fields=list(template.strong_match_fields) if template else [],
            openai_double_check_blocks=list(template.openai_double_check_blocks) if template else [],
            notes=list(template.notes) if template else ["Template fornitore non risolto con certezza."],
        ),
        local_pipeline=[
            "classificazione documento/pagina",
            "render/OCR locale",
            "riconoscimento tabella orizzontale/verticale",
            "esclusione min/max",
            "selezione riga/colonna misurata",
            "normalizzazione valore",
            "match su campi letti",
        ],
        masking_rules=[
            "Mascherare o tagliare dati di Forgialluminio 3 non necessari",
            "Mascherare o tagliare indirizzi, P.IVA, email, telefono",
            "Inviare a OpenAI solo crop/blocchi tecnici utili",
        ],
        decision_policy=[rule.description for rule in build_default_decision_rules()],
        row_split_hint=row_split_hint,
        row_split_candidates=row_split_candidates,
        ddt_table_insights=ddt_insights,
        certificate_table_insights=certificate_insights,
        openai_double_check=_build_openai_estimate(template, planned_crops),
    )


def build_document_row_split_plan(document: Document) -> DocumentRowSplitPlanResponse:
    template = resolve_supplier_template(
        document.supplier.ragione_sociale if document.supplier is not None else None,
        document.nome_file_originale,
    )
    row_split_hint = _build_row_split_hint(document, template)
    row_split_candidates = _build_row_split_candidates(document, template)
    row_split_hint = _finalize_row_split_hint(row_split_hint, row_split_candidates, template)

    return DocumentRowSplitPlanResponse(
        document_id=document.id,
        template=ReaderTemplateSummaryResponse(
            supplier_key=template.supplier_key if template else None,
            supplier_display_name=template.display_name if template else (document.supplier.ragione_sociale if document.supplier else None),
            ddt_template_id=template.ddt_template_id if template else None,
            certificate_template_id=template.certificate_template_id if template else None,
            strong_match_fields=list(template.strong_match_fields) if template else [],
            openai_double_check_blocks=list(template.openai_double_check_blocks) if template else [],
            notes=list(template.notes) if template else ["Template fornitore non risolto con certezza."],
        ),
        row_split_hint=row_split_hint,
        row_split_candidates=row_split_candidates,
    )


def _build_document_table_insights(document: Document | None, document_type: str) -> list[ReaderTableInsightResponse]:
    if document is None:
        return []

    insights: list[ReaderTableInsightResponse] = []
    for page in document.pages:
        lines = _page_lines(page)
        if not lines:
            continue
        interesting_window = _select_table_window(lines)
        if not interesting_window:
            continue
        analysis = analyze_measurement_table(interesting_window)
        insights.append(
            ReaderTableInsightResponse(
                document_type=document_type,  # type: ignore[arg-type]
                page_id=page.id,
                orientation=analysis.orientation,
                measured_line_count=len(analysis.measured_line_indices),
                min_line_count=len(analysis.min_line_indices),
                max_line_count=len(analysis.max_line_indices),
                notes=list(analysis.notes),
            )
        )
    return insights


def _select_table_window(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if any(marker in lowered for marker in ("chemical", "chimica", "mechanical", "meccan", "charge no", "charge nr", "soll min", "set value max")):
            return lines[index : min(index + 14, len(lines))]
    return []


def _page_lines(page) -> list[str]:
    pdf_text = _normalize_text(page.testo_estratto)
    ocr_text = _normalize_text(page.ocr_text)
    text = ocr_text if (ocr_text and _pdf_text_needs_ocr_fallback(pdf_text)) else (pdf_text or ocr_text or "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _estimate_planned_crops(template, row: AcquisitionRow) -> int:
    if template is None:
        return 0
    block_count = len(template.openai_double_check_blocks)
    if row.ddt_document is None:
        block_count = max(0, block_count - 1)
    if row.certificate_document is None:
        block_count = 1 if "ddt_core" in template.openai_double_check_blocks else 0
    return block_count


def _build_openai_estimate(template, planned_crops: int) -> OpenAIDoubleCheckEstimateResponse:
    estimated_input_tokens = planned_crops * LOW_DETAIL_IMAGE_TOKENS
    estimated_input_cost_usd = round((estimated_input_tokens / 1_000_000) * GPT54_INPUT_USD_PER_1M, 6)
    notes = [
        "Stima su detail=low per crop mirati.",
        "Costo output escluso: dipende da prompt e JSON restituito.",
        "In sviluppo/test il double check OpenAI resta bloccato senza consenso esplicito.",
    ]
    if template is not None:
        notes.append(f"Blocchi consigliati: {', '.join(template.openai_double_check_blocks)}")
    return OpenAIDoubleCheckEstimateResponse(
        model_default=settings.document_vision_model,
        escalation_model="gpt-5.4-pro",
        recommended_detail="low",
        blocked_without_consent=True,
        planned_crops=planned_crops,
        estimated_input_tokens=estimated_input_tokens,
        estimated_input_cost_usd=estimated_input_cost_usd,
        notes=notes,
    )


def _build_row_split_hint(document: Document | None, template) -> ReaderRowSplitHintResponse:
    if document is None or template is None:
        return ReaderRowSplitHintResponse(needed=False, signals=[])

    lines: list[str] = []
    for page in document.pages:
        lines.extend(_page_lines(page))
    if not lines:
        return ReaderRowSplitHintResponse(needed=False, signals=[])

    if template.supplier_key == "impol":
        return _build_impol_row_split_hint(lines)
    if template.supplier_key == "grupa_kety":
        return _build_grupa_kety_row_split_hint(lines)

    return ReaderRowSplitHintResponse(needed=False, signals=[])


def _build_impol_row_split_hint(lines: list[str]) -> ReaderRowSplitHintResponse:
    normalized_lines = [line.upper() for line in lines]
    product_codes = {
        match
        for line in normalized_lines
        for match in re.findall(r"\b(\d{6})/\d\b", line)
    }
    diameters = {
        _normalize_decimal_value(match) or match
        for line in normalized_lines
        for match in re.findall(r"\bDIA\s*([0-9]+(?:[.,][0-9]+)?)\s*[X×]\s*\d+\s*MM\b", line)
    }
    charges = {
        match
        for line in normalized_lines
        for match in re.findall(r"\b(\d{6})\s*\(\d+/\d+\)", line)
    }
    signals: list[str] = []
    if len(product_codes) > 1:
        signals.append(f"product_code={len(product_codes)}")
    if len(diameters) > 1:
        signals.append(f"diameter={len(diameters)}")
    if len(charges) > 1:
        signals.append(f"charge={len(charges)}")

    estimated_rows = max([len(product_codes), len(diameters), len(charges), 1])
    if signals:
        return ReaderRowSplitHintResponse(
            needed=True,
            estimated_rows=estimated_rows,
            reason="Il packing list contiene piu posizioni materiale e va scisso in righe acquisition.",
            signals=signals,
        )
    return ReaderRowSplitHintResponse(needed=False, estimated_rows=1, signals=[])


def _build_row_split_candidates(document: Document | None, template) -> list[ReaderRowSplitCandidateResponse]:
    if document is None or template is None:
        return []

    lines: list[str] = []
    for page in document.pages:
        lines.extend(_page_lines(page))
    if not lines:
        return []

    if template.supplier_key == "impol":
        return _build_impol_row_split_candidates(lines, template.supplier_key)
    if template.supplier_key == "grupa_kety":
        return _build_grupa_kety_row_split_candidates(lines, template.supplier_key)
    return []


def _finalize_row_split_hint(
    hint: ReaderRowSplitHintResponse,
    candidates: list[ReaderRowSplitCandidateResponse],
    template,
) -> ReaderRowSplitHintResponse:
    if hint.needed or len(candidates) <= 1:
        return hint

    supplier_label = template.display_name if template is not None else "documento"
    return ReaderRowSplitHintResponse(
        needed=True,
        estimated_rows=len(candidates),
        reason=f"Il documento {supplier_label} contiene piu righe/lotti distinti e va scisso in righe acquisition.",
        signals=[f"candidate={len(candidates)}"],
    )


def _build_grupa_kety_row_split_hint(lines: list[str]) -> ReaderRowSplitHintResponse:
    normalized_lines = [line.upper() for line in lines]
    lots = {
        token.split("/", 1)[0]
        for line in normalized_lines
        for token in re.findall(r"\b100\d{5}(?:/\d{2})?\b", line)
    }
    heats = {
        token
        for line in normalized_lines
        for token in re.findall(r"\b\d{2}[A-Z]-\d{4}\b", line)
    }
    signals: list[str] = []
    if len(lots) > 1:
        signals.append(f"lot={len(lots)}")
    if len(heats) > 1:
        signals.append(f"heat={len(heats)}")

    estimated_rows = max([len(lots), len(heats), 1])
    if signals:
        return ReaderRowSplitHintResponse(
            needed=True,
            estimated_rows=estimated_rows,
            reason="Il documento contiene piu lotti o heat e puo richiedere piu righe acquisition.",
            signals=signals,
        )
    return ReaderRowSplitHintResponse(needed=False, estimated_rows=1, signals=[])


def _build_grupa_kety_row_split_candidates(lines: list[str], supplier_key: str) -> list[ReaderRowSplitCandidateResponse]:
    normalized_lines = [_normalize_line(line) for line in lines]
    lega = _extract_grupa_kety_lega(normalized_lines)
    diametro = _extract_grupa_kety_diameter(normalized_lines)
    product_code = _extract_grupa_kety_product_code(normalized_lines)
    customer_order_no = _extract_grupa_kety_header_order(normalized_lines)

    candidates: list[ReaderRowSplitCandidateResponse] = []
    for index, (original_line, normalized_line) in enumerate(zip(lines, normalized_lines), start=1):
        lot_batch_no = _extract_grupa_kety_lot(normalized_line)
        if lot_batch_no is None:
            continue
        heat_no = _extract_grupa_kety_heat(normalized_line)
        peso_netto = _extract_grupa_kety_net_weight_from_line(normalized_line)
        snippets = [snippet for snippet in _collect_grupa_kety_snippets(lines, normalized_line) if snippet.strip()][:6]
        candidates.append(
            ReaderRowSplitCandidateResponse(
                candidate_index=len(candidates) + 1,
                supplier_key=supplier_key,
                lega=lega,
                diametro=diametro,
                peso_netto=peso_netto,
                lot_batch_no=lot_batch_no,
                heat_no=heat_no,
                customer_order_no=customer_order_no,
                product_code=product_code,
                snippets=snippets,
            )
        )

    return candidates


def _build_impol_row_split_candidates(lines: list[str], supplier_key: str) -> list[ReaderRowSplitCandidateResponse]:
    normalized_lines = [_normalize_line(line) for line in lines]
    diameter_indices = [
        index
        for index, line in enumerate(normalized_lines)
        if re.search(r"\bDIA\s*[0-9]+(?:[.,][0-9]+)?\s*[X×]\s*\d+\s*MM\b", line)
    ]
    if not diameter_indices:
        return []

    candidates: list[ReaderRowSplitCandidateResponse] = []
    boundaries = diameter_indices + [len(lines)]
    for candidate_index, start_index in enumerate(diameter_indices, start=1):
        end_index = boundaries[candidate_index] if candidate_index < len(boundaries) else len(lines)
        header_hint = _find_impol_candidate_header_line(normalized_lines, start_index, end_index)
        section_original = _trim_impol_candidate_section(lines[start_index:end_index])
        section_normalized = [_normalize_line(line) for line in section_original]
        if header_hint is not None:
            header_index, header_line = header_hint
            section_normalized = [header_line, *section_normalized]
            original_header = lines[header_index]
            section_original = [original_header, *section_original]
        candidate = ReaderRowSplitCandidateResponse(
            candidate_index=candidate_index,
            supplier_key=supplier_key,
            lega=_extract_impol_candidate_lega(section_normalized),
            diametro=_extract_impol_candidate_diameter(section_normalized),
            peso_netto=_extract_impol_candidate_net_weight(section_normalized),
            colata=_extract_impol_candidate_charge(section_normalized),
            customer_order_no=_extract_impol_candidate_customer_order(section_normalized),
            supplier_order_no=_extract_impol_candidate_supplier_order(section_normalized),
            product_code=_extract_impol_candidate_product_code(section_normalized),
            snippets=[snippet for snippet in section_original if snippet.strip()][:6],
        )
        if any(
            getattr(candidate, field) is not None
            for field in ("lega", "diametro", "peso_netto", "colata", "customer_order_no", "supplier_order_no", "product_code")
        ):
            candidates.append(candidate)

    return candidates


def _trim_impol_candidate_section(lines: list[str]) -> list[str]:
    trimmed: list[str] = []
    for line in lines:
        normalized = _normalize_line(line)
        if any(marker in normalized for marker in ("POS. TOTAL", "DRUZ", "MATIGNA", "MATITNA", "REG. VLOZKA", "ID ZA DDV", "ID ZA PDV")):
            break
        trimmed.append(line)
    return trimmed


def _find_impol_candidate_header_line(lines: list[str], start_index: int, end_index: int) -> tuple[int, str] | None:
    lower_bound = max(0, start_index - 3)
    for index in range(start_index - 1, lower_bound - 1, -1):
        line = lines[index]
        if _looks_like_impol_weight_row(line):
            continue
        if any(marker in line for marker in ("AL ROUND", "FORGING", "ENAW", "EN AW", "PRODUCTCODE")):
            return index, line
        if re.search(r"\b\d{6}/\d\b", line):
            return index, line
    return None


def _extract_impol_candidate_lega(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"EN\s*AW\s*([0-9]{4}[A-Z]?)\s*F\b", line)
        if match is not None:
            return f"{match.group(1)} F"
    return None


def _extract_impol_candidate_diameter(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bDIA\s*([0-9]+(?:[.,][0-9]+)?)\s*[X×]\s*\d+\s*MM\b", line)
        if match is not None:
            return _normalize_decimal_value(match.group(1))
    return None


def _extract_impol_candidate_charge(lines: list[str]) -> str | None:
    candidates: set[str] = set()
    for line in lines:
        for match in re.findall(r"\b(\d{6})\s*\(\d+/\d+\)", line):
            candidates.add(match)
        row_components = _extract_impol_weight_row_components(line)
        if row_components is not None:
            candidates.add(row_components[2])
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_candidate_net_weight(lines: list[str]) -> str | None:
    total = 0.0
    found = False
    for line in lines:
        row_components = _extract_impol_weight_row_components(line)
        if row_components is not None:
            net = _parse_decimal_number(row_components[1])
            if net is not None:
                total += net
                found = True
    if found:
        return _format_weight_number(total)
    return None


def _extract_impol_candidate_customer_order(lines: list[str]) -> str | None:
    for line in lines:
        if "YOUR ORDER" not in line:
            continue
        numbers = re.findall(r"\b\d{1,6}\b", line)
        if numbers:
            return numbers[-1]
    return None


def _extract_impol_candidate_supplier_order(lines: list[str]) -> str | None:
    for line in lines:
        if "(" in line or any(marker in line for marker in ("DRUZ", "MATIGNA", "MATITNA", "ID ZA", "REG.")):
            continue
        if "DIA" not in line and not re.search(r"\b\d{6}/\d\b", line):
            continue
        match = re.search(r"\b(\d{3,6}/\d{1,2})\b", line)
        if match is not None:
            return match.group(1)
        alt = re.search(r"\b(\d{5,6})(\d)\b", line)
        if alt is not None and "DIA" in line and "KG" not in line:
            return f"{alt.group(1)}/{alt.group(2)}"
    return None


def _extract_impol_candidate_product_code(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\b(\d{6})/\d\b", line)
        if match is not None:
            return match.group(1)
        alt = re.search(r"\b([89]\d{5})\b", line)
        if alt is not None and "ROUND BARS" in line:
            return alt.group(1)
    return None


def _looks_like_impol_weight_row(line: str) -> bool:
    return _extract_impol_weight_row_components(line) is not None


def _extract_impol_weight_row_components(line: str) -> tuple[str, str, str] | None:
    match = re.search(
        r"\b\d+\s+([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)\s+([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)\s+(\d{6})(?:\s*\(\d+/\d+\))?\b",
        line,
    )
    if match is None:
        return None
    return match.group(1), match.group(2), match.group(3)


def _extract_grupa_kety_lega(lines: list[str]) -> str | None:
    alloy: str | None = None
    temper: str | None = None
    for line in lines:
        if alloy is None:
            alloy_match = re.search(r"\bALLOY\s*:?\s*([0-9]{4}[A-Z]?)\b", line)
            if alloy_match is not None:
                alloy = alloy_match.group(1)
        if temper is None:
            temper_match = re.search(r"\bTEMPER\s*:?\s*([A-Z0-9]+)\b", line)
            if temper_match is not None:
                temper = temper_match.group(1)
        if alloy and temper:
            return f"{alloy} {temper}"
    if alloy and temper:
        return f"{alloy} {temper}"
    return alloy


def _extract_grupa_kety_diameter(lines: list[str]) -> str | None:
    patterns = (
        r"\bEXTRUDED(?:\s+ROUND)?\s+BAR[S]?\s+([0-9]+(?:[.,][0-9]+)?)\b",
        r"\bPRET\s+WYCISKANY\s+([0-9]+(?:[.,][0-9]+)?)\b",
        r"\bPPO\s+([0-9]+(?:[.,][0-9]+)?)MM\b",
    )
    for line in lines:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match is not None:
                return _normalize_decimal_value(match.group(1))
    return None


def _extract_grupa_kety_product_code(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\b([0-9A-Z]{10,}--[0-9A-Z]{3,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_grupa_kety_lot(line: str) -> str | None:
    for pattern in (r"\b(\d{9}-[A-Z0-9]{6,})\b", r"\b(\d{8}[_-]\d{5})\b"):
        match = re.search(pattern, line)
        if match is not None:
            return match.group(1)
    spaced_match = re.search(r"\b(\d{8})\s+(\d{5})\b", line)
    if spaced_match is not None:
        return f"{spaced_match.group(1)}_{spaced_match.group(2)}"
    return None


def _extract_grupa_kety_order_from_line(line: str) -> str | None:
    numbers = re.findall(r"\b\d{8,10}\b", line)
    filtered_numbers = [number for number in numbers if not number.startswith(("1003", "7500"))]
    if filtered_numbers:
        return filtered_numbers[0]
    if numbers:
        return numbers[0]
    return None


def _extract_grupa_kety_heat(line: str) -> str | None:
    match = re.search(r"\b(\d{2}[A-Z]-\d{4})\b", line)
    if match is not None:
        return match.group(1)
    spaced_match = re.search(r"\b(\d{2}[A-Z]-\d)\s+(\d)\b", line)
    if spaced_match is not None:
        return f"{spaced_match.group(1)}{spaced_match.group(2)}"
    return None


def _extract_grupa_kety_net_weight_from_line(line: str) -> str | None:
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", line)
    if len(numbers) < 2:
        return None
    return _normalize_decimal_value(numbers[-2])


def _extract_grupa_kety_header_order(lines: list[str]) -> str | None:
    for line in lines:
        if "PO NUMBER" not in line and "ORDER NO" not in line:
            continue
        match = re.search(r"\bPO\s+NUMBER\s+([0-9]{1,6})\b", line)
        if match is not None:
            return match.group(1)
        match = re.search(r"\bORDER\s+NO\s+([0-9]{1,6})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _collect_grupa_kety_snippets(lines: list[str], candidate_line: str) -> list[str]:
    snippets: list[str] = []
    for line in lines:
        normalized = _normalize_line(line)
        if normalized == candidate_line:
            snippets.append(line)
            break

    for line in lines:
        normalized = _normalize_line(line)
        if any(marker in normalized for marker in ("EXTRUDED BAR", "EXTRUDED ROUND BAR", "PRET WYCISKANY", "ITEM BY BP", "CUSTOMER PART")):
            snippets.append(line)
        if any(marker in normalized for marker in ("ALLOY", "TEMPER", "LENGTH")):
            snippets.append(line)

    unique_snippets: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        key = snippet.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_snippets.append(snippet)
    return unique_snippets


def _normalize_line(line: str) -> str:
    return " ".join(line.upper().replace("_", " ").split())


def _parse_decimal_number(value: str | None) -> float | None:
    normalized = _normalize_decimal_value(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _format_weight_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _normalize_decimal_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        return None
    normalized = cleaned.replace(",", ".")
    if normalized.count(".") > 1:
        integer, decimal = normalized.rsplit(".", 1)
        normalized = integer.replace(".", "") + "." + decimal
    return normalized
