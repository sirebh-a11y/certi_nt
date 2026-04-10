from __future__ import annotations

import re

from app.core.config import settings
from app.modules.acquisition.models import AcquisitionRow, Document
from app.modules.document_reader.decision_engine import build_default_decision_rules
from app.modules.document_reader.registry import resolve_supplier_template
from app.modules.document_reader.schemas import (
    OpenAIDoubleCheckEstimateResponse,
    ReaderPlanResponse,
    ReaderRowSplitHintResponse,
    ReaderTableInsightResponse,
    ReaderTemplateSummaryResponse,
)
from app.modules.document_reader.table_analysis import analyze_measurement_table

GPT54_INPUT_USD_PER_1M = 2.50
LOW_DETAIL_IMAGE_TOKENS = 85


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
        ddt_table_insights=ddt_insights,
        certificate_table_insights=certificate_insights,
        openai_double_check=_build_openai_estimate(template, planned_crops),
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
    text = page.testo_estratto or page.ocr_text or ""
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
