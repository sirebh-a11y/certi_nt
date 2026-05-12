from __future__ import annotations

import re
from pathlib import Path

import pytesseract
from PIL import Image

from app.core.config import settings
from app.modules.acquisition.models import AcquisitionRow, Document
from app.modules.document_reader.decision_engine import build_default_decision_rules
from app.modules.document_reader.registry import resolve_supplier_template
from app.modules.document_reader.schemas import (
    ReaderDocumentPartResponse,
    DocumentRowSplitPlanResponse,
    OpenAIDoubleCheckEstimateResponse,
    ReaderPlanResponse,
    ReaderRowSplitCandidateResponse,
    ReaderRowSplitHintResponse,
    ReaderTableInsightResponse,
    ReaderTemplateSummaryResponse,
)
from app.modules.document_reader.table_analysis import analyze_measurement_table

DOCUMENT_VISION_INPUT_USD_PER_1M = 2.50
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
    mojibake_markers = len(re.findall(r"[ßÝÛÒÑÞÔ×ØÐ]", normalized))

    if ascii_alnum_count == 0 and extended_latin_count >= 4:
        return True
    if extended_latin_count >= 6 and ascii_alnum_count < 12:
        return True
    if word_count <= 3 and extended_latin_count > ascii_alnum_count:
        return True
    if mojibake_markers >= 12 and mojibake_markers * 3 >= max(ascii_alnum_count, 1):
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
    ddt_part_hints = _build_document_part_hints(row.ddt_document, template, "ddt")
    certificate_part_hints = _build_document_part_hints(row.certificate_document, template, "certificato")
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
        ddt_part_hints=ddt_part_hints,
        certificate_part_hints=certificate_part_hints,
        ddt_table_insights=ddt_insights,
        certificate_table_insights=certificate_insights,
        openai_double_check=_build_openai_estimate(template, planned_crops),
    )


def build_document_row_split_plan(document: Document) -> DocumentRowSplitPlanResponse:
    template = _resolve_document_template(document)
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
        document_part_hints=_build_document_part_hints(document, template, "ddt"),
    )


def _resolve_document_template(document: Document):
    template = resolve_supplier_template(
        document.supplier.ragione_sociale if document.supplier is not None else None,
        document.nome_file_originale,
    )
    if template is not None:
        return template

    lines: list[str] = []
    for page in document.pages[:3]:
        lines.extend(_page_lines(page))
    if not lines:
        return None

    if _looks_like_aluminium_bozen_document(lines):
        return resolve_supplier_template("aluminium bozen")
    if _looks_like_impol_document(lines):
        return resolve_supplier_template("impol")

    return None


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


def _build_document_part_hints(document: Document | None, template, document_type: str) -> list[ReaderDocumentPartResponse]:
    if document is None or template is None:
        return []

    if template.supplier_key == "aluminium_bozen":
        if document_type == "ddt":
            return _build_aluminium_bozen_ddt_part_hints(document)
        if document_type == "certificato":
            return _build_aluminium_bozen_certificate_part_hints(document)

    return []


def _build_aluminium_bozen_ddt_part_hints(document: Document) -> list[ReaderDocumentPartResponse]:
    first_page = document.pages[0] if document.pages else None
    lines = _page_lines(first_page) if first_page is not None else []
    return [
        ReaderDocumentPartResponse(
            document_type="ddt",
            part_key="header_num",
            label="Header DDT / Num.",
            kind="header",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("DELIVERY NOTE", "DOCUMENTO DI TRASPORTO", "NUM.")),
            bbox_hint=[0.0, 0.0, 1.0, 0.20],
            notes=["Qui si trova il numero DDT e l'identita del documento."],
        ),
        ReaderDocumentPartResponse(
            document_type="ddt",
            part_key="material_rows",
            label="Righe materiale",
            kind="material_rows",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("BARRA TONDA", "CAST NR.", "RIF. NS. ODV")),
            bbox_hint=[0.0, 0.18, 1.0, 0.72],
            notes=["Da qui leggiamo ordine, articolo, lega, diametro, colata e peso di riga."],
        ),
        ReaderDocumentPartResponse(
            document_type="ddt",
            part_key="packing_list",
            label="Packing list / colli",
            kind="packing_list",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("COD. COLATA", "COD. ART. CLIENTE", "LEGA STATO FISICO")),
            bbox_hint=[0.0, 0.58, 1.0, 1.0],
            notes=["Usato come supporto per pesi e colli quando la riga materiale e' spezzata."],
        ),
    ]


def _build_aluminium_bozen_certificate_part_hints(document: Document) -> list[ReaderDocumentPartResponse]:
    first_page = document.pages[0] if document.pages else None
    lines = _page_lines(first_page) if first_page is not None else []
    return [
        ReaderDocumentPartResponse(
            document_type="certificato",
            part_key="certificate_header",
            label="Header certificato",
            kind="header",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("CERT.NO.", "CERT NO.", "INSPECTION CERTIFICATE")),
            bbox_hint=[0.0, 0.0, 1.0, 0.18],
            notes=["Qui si trovano numero certificato e data certificato."],
        ),
        ReaderDocumentPartResponse(
            document_type="certificato",
            part_key="identity_block",
            label="Dati articolo / cliente / materiale",
            kind="identity",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("CUSTOMER ARTICLE", "SECTION DESC", "CAST BATCH", "CUSTOMER'S ORDER")),
            bbox_hint=[0.0, 0.16, 1.0, 0.46],
            notes=["Qui si trovano articolo, customer code, ordine cliente, diametro, lega e colata."],
        ),
        ReaderDocumentPartResponse(
            document_type="certificato",
            part_key="chemistry_table",
            label="Tabella chimica",
            kind="table",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("CHEMICAL ANALYSIS", "CHEMICAL COMPOSITION", "ANALISI CHIMICA", "COMPOSIZIONE CHIMICA")),
            bbox_hint=[0.0, 0.40, 1.0, 0.68],
            notes=["Da qui leggiamo solo i valori misurati, non min/max."],
        ),
        ReaderDocumentPartResponse(
            document_type="certificato",
            part_key="properties_table",
            label="Tabella proprieta meccaniche",
            kind="table",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("MECHANICAL PROPERTIES", "CARATTERISTICHE MECCANICHE")),
            bbox_hint=[0.0, 0.60, 1.0, 0.84],
            notes=["Da qui leggiamo la riga misurata, escludendo norme e min/max."],
        ),
        ReaderDocumentPartResponse(
            document_type="certificato",
            part_key="notes_block",
            label="Note e conformita",
            kind="notes",
            page_id=first_page.id if first_page else None,
            snippet=_find_first_matching_line(lines, ("RADIOACTIVE", "ROHS", "ASTM", "AMS", "UNLESS OTHERWISE AGREED")),
            bbox_hint=[0.0, 0.80, 1.0, 1.0],
            notes=["Qui leggiamo note qualitative e note normative utili."],
        ),
    ]


def _find_first_matching_line(lines: list[str], tokens: tuple[str, ...]) -> str | None:
    for line in lines:
        normalized_line = _normalize_line(line)
        if any(token in normalized_line for token in tokens):
            return line
    return lines[0] if lines else None


def _select_table_window(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if any(marker in lowered for marker in ("chemical", "chimica", "mechanical", "meccan", "charge no", "charge nr", "soll min", "set value max")):
            return lines[index : min(index + 14, len(lines))]
    return []


def _looks_like_aluminium_bozen_document(lines: list[str]) -> bool:
    normalized_lines = [_normalize_line(line) for line in lines]
    joined = "\n".join(normalized_lines)
    has_delivery_header = "DELIVERY NOTE" in joined or "DOCUMENTO DI TRASPORTO" in joined
    has_material_row = any("BARRA TONDA" in line for line in normalized_lines)
    has_cast = "CAST NR." in joined or "CAST NR" in joined
    has_internal_order = "RIF. NS. ODV" in joined
    has_packing_signals = any(
        marker in joined
        for marker in ("RIF. ORDINE AB ODV", "COD. COLATA", "COD. ART. CLIENTE", "LEGA STATO FISICO")
    )
    return (has_delivery_header and has_material_row and (has_cast or has_internal_order)) or has_packing_signals


def _looks_like_impol_document(lines: list[str]) -> bool:
    normalized_lines = [_normalize_line(line) for line in lines]
    joined = "\n".join(normalized_lines)
    has_impol_identity = any(
        marker in joined
        for marker in ("IMPOL D.O.O", "IMPOL GROUP", "INFO@IMPOL.SI", "WWW.IMPOL.SI", "SLOVENSKA BISTRICA")
    )
    has_ddt_signals = any(
        marker in joined
        for marker in ("PACKING LIST", "RECEIVER", "DELIVERY TERMS", "TRUCK / CONTAINER", "YOUR ORDER NO")
    )
    has_certificate_signals = any(
        marker in joined
        for marker in ("INSPECTION CERTIFICATE", "EN 10204", "CHEMICAL COMPOSITION", "MECHANICAL PROPERTIES")
    )
    return has_impol_identity and (has_ddt_signals or has_certificate_signals)


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
    estimated_input_cost_usd = round((estimated_input_tokens / 1_000_000) * DOCUMENT_VISION_INPUT_USD_PER_1M, 6)
    notes = [
        "Stima su detail=low per crop mirati.",
        "Costo output escluso: dipende da prompt e JSON restituito.",
        "In sviluppo/test il double check OpenAI resta bloccato senza consenso esplicito.",
    ]
    if template is not None:
        notes.append(f"Blocchi consigliati: {', '.join(template.openai_double_check_blocks)}")
    return OpenAIDoubleCheckEstimateResponse(
        model_default=settings.document_vision_model,
        escalation_model=settings.document_vision_model,
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
    if template.supplier_key == "leichtmetall":
        return _build_leichtmetall_row_split_hint(document, lines)
    if template.supplier_key == "neuman":
        return _build_neuman_row_split_hint(document, lines)
    if template.supplier_key == "grupa_kety":
        return _build_grupa_kety_row_split_hint(lines)
    if template.supplier_key == "aluminium_bozen":
        return _build_aluminium_bozen_row_split_hint(document, lines)

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


def _build_leichtmetall_row_split_hint(document: Document | None, lines: list[str]) -> ReaderRowSplitHintResponse:
    candidate_count = len(_build_leichtmetall_row_split_candidates(document, "leichtmetall"))
    if candidate_count > 1:
        return ReaderRowSplitHintResponse(
            needed=True,
            estimated_rows=candidate_count,
            reason="Il DDT Leichtmetall contiene piu gruppi batch/cdq e va scisso in piu righe acquisition.",
            signals=[f"candidate={candidate_count}"],
        )
    return ReaderRowSplitHintResponse(needed=False, estimated_rows=max(candidate_count, 1), signals=[])


def _build_neuman_row_split_hint(document: Document | None, lines: list[str]) -> ReaderRowSplitHintResponse:
    candidate_count = len(_build_neuman_row_split_candidates(document, "neuman"))
    if candidate_count > 1:
        return ReaderRowSplitHintResponse(
            needed=True,
            estimated_rows=candidate_count,
            reason="Il DDT Neuman contiene piu gruppi lotto/prodotto e va scisso in piu righe acquisition.",
            signals=[f"candidate={candidate_count}"],
        )
    return ReaderRowSplitHintResponse(needed=False, estimated_rows=max(candidate_count, 1), signals=[])


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
    if template.supplier_key == "metalba":
        return _build_metalba_row_split_candidates(lines, template.supplier_key)
    if template.supplier_key == "leichtmetall":
        return _build_leichtmetall_row_split_candidates(document, template.supplier_key)
    if template.supplier_key == "neuman":
        return _build_neuman_row_split_candidates(document, template.supplier_key)
    if template.supplier_key == "grupa_kety":
        return _build_grupa_kety_row_split_candidates(lines, template.supplier_key)
    if template.supplier_key == "aluminium_bozen":
        return _build_aluminium_bozen_row_split_candidates(document, lines, template.supplier_key)
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


def _build_aluminium_bozen_row_split_hint(document: Document | None, lines: list[str]) -> ReaderRowSplitHintResponse:
    candidate_count = len(_build_aluminium_bozen_row_split_candidates(document, lines, "aluminium_bozen"))
    if candidate_count > 1:
        return ReaderRowSplitHintResponse(
            needed=True,
            estimated_rows=candidate_count,
            reason="Il DDT Aluminium Bozen contiene piu righe materiale e va scisso per riga.",
            signals=[f"candidate={candidate_count}"],
        )
    return ReaderRowSplitHintResponse(needed=False, estimated_rows=max(candidate_count, 1), signals=[])


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


def _build_aluminium_bozen_row_split_candidates(
    document: Document | None,
    lines: list[str],
    supplier_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    normalized_lines = [_normalize_line(line) for line in lines]
    ddt_number = _extract_aluminium_bozen_ddt_number(document, normalized_lines)
    current_order: str | None = None
    current_lega: str | None = None
    raw_candidates: list[ReaderRowSplitCandidateResponse] = []

    for index, (original_line, normalized_line) in enumerate(zip(lines, normalized_lines)):
        order_value = _extract_aluminium_bozen_order(normalized_line)
        if order_value is not None:
            current_order = order_value

        lega_value = _extract_aluminium_bozen_lega_from_line(normalized_line)
        if lega_value is not None:
            current_lega = lega_value

        if not _is_aluminium_bozen_material_line(normalized_line):
            continue

        diametro = _extract_aluminium_bozen_diameter_from_line(normalized_line) or _extract_aluminium_bozen_diameter_from_window(normalized_lines, index)
        peso_netto = _extract_aluminium_bozen_weight_from_line(normalized_line)
        colata = _extract_aluminium_bozen_cast_from_window(normalized_lines, index)
        lega = _extract_aluminium_bozen_lega_from_window(normalized_lines, index) or current_lega
        order = _extract_aluminium_bozen_order_from_window(normalized_lines, index) or current_order
        customer_order = _extract_aluminium_bozen_customer_order_from_window(normalized_lines, index)

        snippets = [snippet for snippet in _collect_aluminium_bozen_snippets(lines, index) if snippet.strip()][:6]
        candidate = ReaderRowSplitCandidateResponse(
            candidate_index=len(raw_candidates) + 1,
            supplier_key=supplier_key,
            ddt_number=ddt_number,
            cdq=_extract_aluminium_bozen_cdq_from_window(normalized_lines, index),
            profile_code=_extract_aluminium_bozen_profile_code_from_line(normalized_line),
            article_code=_extract_aluminium_bozen_article_from_line(normalized_line),
            lega=lega,
            diametro=diametro,
            peso_netto=peso_netto,
            colata=colata,
            customer_order_no=customer_order,
            supplier_order_no=order,
            snippets=snippets,
        )

        if any(getattr(candidate, field) is not None for field in ("ddt_number", "lega", "diametro", "peso_netto", "colata", "supplier_order_no")):
            raw_candidates.append(candidate)

    return _merge_aluminium_bozen_candidates(raw_candidates, lines, ddt_number, supplier_key)


def _is_aluminium_bozen_material_line(line: str) -> bool:
    if any(marker in line for marker in ("DES. ART. CLIENTE", "LEGA STATO FISICO", "RIF. ORDINE AB ODV", "COD. COLATA")):
        return False
    article = _extract_aluminium_bozen_article_from_line(line)
    profile_code = _extract_aluminium_bozen_profile_code_from_line(line)
    material_label = _extract_aluminium_bozen_material_label_from_line(line)
    diameter = _extract_aluminium_bozen_diameter_from_line(line)
    weight = _extract_aluminium_bozen_weight_from_line(line)
    lega = _extract_aluminium_bozen_lega_from_line(line)
    explicit_anchor = "BARRA TONDA" in line

    if explicit_anchor and diameter is not None:
        return True
    if explicit_anchor and (article is not None or profile_code is not None):
        return True
    if material_label is not None and profile_code is not None and article is not None and diameter is not None:
        return True
    if article is not None and profile_code is not None and diameter is not None and (weight is not None or lega is not None):
        return True
    return False


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
        strong_signal_count = sum(
            1
            for field in ("lega", "colata", "supplier_order_no", "product_code")
            if getattr(candidate, field) is not None
        )
        support_signal_count = sum(
            1
            for field in ("diametro", "peso_netto", "customer_order_no")
            if getattr(candidate, field) is not None
        )
        if strong_signal_count >= 1 and (strong_signal_count + support_signal_count) >= 2:
            candidates.append(candidate)

    return candidates


def _build_metalba_row_split_candidates(lines: list[str], supplier_key: str) -> list[ReaderRowSplitCandidateResponse]:
    normalized_lines = [_normalize_line(line) for line in lines]

    ddt_number = _extract_metalba_ddt_number(normalized_lines)
    customer_order_no = _extract_metalba_vs_rif(normalized_lines)
    rif_ord = _extract_metalba_rif_ord(normalized_lines)
    alloy = _extract_metalba_candidate_alloy(normalized_lines)
    diameter = _extract_metalba_candidate_diameter(normalized_lines)
    weight = _extract_metalba_candidate_weight(normalized_lines)
    customer_code = _extract_metalba_customer_code(normalized_lines)
    colata = _extract_metalba_candidate_cast(normalized_lines)
    snippets = [snippet for snippet in lines if snippet.strip()][:8]

    candidate = ReaderRowSplitCandidateResponse(
        candidate_index=1,
        supplier_key=supplier_key,
        ddt_number=ddt_number,
        lega=alloy,
        diametro=diameter,
        peso_netto=weight,
        colata=colata,
        customer_order_no=customer_order_no,
        customer_code=customer_code,
        snippets=snippets,
        ai_row_payload_raw=(
            f'{{"vs_rif_raw":"{customer_order_no or ""}","rif_ord_raw":"{rif_ord or ""}",'
            f'"customer_code_raw":"{customer_code or ""}","alloy_raw":"{alloy or ""}",'
            f'"diameter_raw":"{diameter or ""}","net_weight_raw":"{weight or ""}",'
            f'"cast_raw":"{colata or ""}"}}'
        ),
    )

    strong_signal_count = sum(
        1 for field_name in ("customer_order_no", "lega", "diametro", "peso_netto") if getattr(candidate, field_name) is not None
    )
    if strong_signal_count < 3:
        return []
    return [candidate]


def _build_neuman_row_split_candidates(
    document: Document | None,
    supplier_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if document is None or not document.pages:
        return []

    all_lines = [line for page in document.pages for line in _page_lines(page)]
    normalized_all_lines = [_normalize_line(line) for line in all_lines]

    ddt_number = _extract_neuman_delivery_note_number(normalized_all_lines)
    customer_order_no = _extract_neuman_customer_order_number(normalized_all_lines)

    section_ranges = _extract_neuman_section_ranges(normalized_all_lines)
    if not section_ranges:
        section_ranges = [(0, len(all_lines))]

    candidates: list[ReaderRowSplitCandidateResponse] = []
    for start_index, end_index in section_ranges:
        section_raw = all_lines[start_index:end_index]
        section_normalized = normalized_all_lines[start_index:end_index]
        article_code = _extract_neuman_article_number(section_normalized)
        lega = _extract_neuman_alloy(section_normalized) or _extract_neuman_alloy(normalized_all_lines)
        diametro = _extract_neuman_diameter(section_normalized) or _extract_neuman_diameter(normalized_all_lines)
        section_order = _extract_neuman_customer_order_number(section_normalized) or customer_order_no
        lot_groups = _extract_neuman_lot_groups(section_raw, section_normalized)

        for lot_token, payload in lot_groups.items():
            snippets = list(payload.get("snippets", []))[:6]
            candidates.append(
                ReaderRowSplitCandidateResponse(
                    candidate_index=len(candidates) + 1,
                    supplier_key=supplier_key,
                    ddt_number=ddt_number,
                    cdq=lot_token,
                    article_code=article_code,
                    lega=lega,
                    diametro=diametro,
                    peso_netto=_normalize_text(str(payload.get("weight"))) if payload.get("weight") is not None else None,
                    colata=lot_token,
                    lot_batch_no=lot_token,
                    customer_order_no=section_order,
                    snippets=snippets,
                )
            )

    if candidates:
        return candidates

    if not any((ddt_number, customer_order_no)):
        return []

    return [
        ReaderRowSplitCandidateResponse(
            candidate_index=1,
            supplier_key=supplier_key,
            ddt_number=ddt_number,
            customer_order_no=customer_order_no,
            lega=_extract_neuman_alloy(normalized_all_lines),
            diametro=_extract_neuman_diameter(normalized_all_lines),
            snippets=all_lines[:6],
        )
    ]


def _extract_neuman_section_ranges(lines: list[str]) -> list[tuple[int, int]]:
    anchors = [index for index, line in enumerate(lines) if _is_neuman_product_anchor_line(line)]
    if not anchors:
        return []
    ranges: list[tuple[int, int]] = []
    for offset, start_index in enumerate(anchors):
        end_index = anchors[offset + 1] if offset + 1 < len(anchors) else len(lines)
        ranges.append((start_index, end_index))
    return ranges


def _is_neuman_product_anchor_line(line: str) -> bool:
    if "RUNDSTANGEN" in line and ("@" in line or "Ø" in line or " MM" in line):
        return True
    return False


def _extract_neuman_delivery_note_number(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bDELIVERY\s+NOTE\s+(\d{6,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_neuman_customer_order_number(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if "CUSTOMER ORDER NUMBER" not in line:
            continue
        same_line_match = re.search(r"\bCUSTOMER\s+ORDER\s+NUMBER\s*:?\s*([0-9]{1,6})\b", line)
        if same_line_match is not None:
            return same_line_match.group(1)
        for candidate in lines[index : min(index + 4, len(lines))]:
            inline_match = re.search(r"\b([0-9]{1,6})\s+OF\s+\d{2}\.\d{2}\.\d{4}\b", candidate)
            if inline_match is not None:
                return inline_match.group(1)
    return None


def _extract_neuman_article_number(lines: list[str]) -> str | None:
    for line in lines:
        if "ART-NR" not in line and "ARTIKELNR" not in line:
            continue
        match = re.search(r"\b(A\d[0-9A-Z]{4,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_neuman_alloy(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bWERKSTOFF\s*:?\s*EN\s+AW\s*([0-9]{4}[A-Z]{0,3})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_neuman_diameter(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"[@Ø]\s*([0-9]+(?:[.,][0-9]+)?)\s*MM\b", line)
        if match is not None:
            return _normalize_decimal_value(match.group(1))
    for line in lines:
        if "RUNDSTANGEN" not in line:
            continue
        match = re.search(r"RUNDSTANGEN.*?\b([0-9]{2,3}(?:[.,][0-9]+)?)\s*MM\b", line)
        if match is not None:
            return _normalize_decimal_value(match.group(1))
    return None


def _extract_neuman_lot_groups(
    raw_lines: list[str],
    normalized_lines: list[str],
) -> dict[str, dict[str, object]]:
    lot_totals: dict[str, dict[str, object]] = {}
    hu_totals: dict[str, dict[str, object]] = {}
    section_net_weights: list[int] = []
    section_lot_tokens: set[str] = set()

    for raw_line, normalized_line in zip(raw_lines, normalized_lines, strict=False):
        if "LOT COUNT" in normalized_line or "LINE COUNT" in normalized_line or "TOTAL COLLI" in normalized_line:
            continue
        lot_match = re.search(r"\bLOT\s*:?\s*(\d{5})\b", normalized_line)
        weight_match = re.search(r"\bNET\s*:?\s*([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\s*KG\b", normalized_line)
        if weight_match is not None:
            generic_weight = _parse_neuman_document_weight(weight_match.group(1))
            if generic_weight is not None:
                section_net_weights.append(int(round(generic_weight)))
        if lot_match is None or weight_match is None:
            if lot_match is not None:
                section_lot_tokens.add(lot_match.group(1))
            continue
        lot_token = lot_match.group(1)
        section_lot_tokens.add(lot_token)
        parsed_direct_weight = _parse_neuman_document_weight(weight_match.group(1))
        if parsed_direct_weight is None:
            continue
        normalized_weight = str(int(round(parsed_direct_weight)))
        if "HU:" in normalized_line:
            parsed_weight = int(round(parsed_direct_weight))
            if parsed_weight is None:
                continue
            entry = hu_totals.setdefault(lot_token, {"weight_total": 0, "snippets": []})
            entry["weight_total"] = int(entry["weight_total"]) + parsed_weight
            entry["snippets"] = _merge_snippets(entry["snippets"], [raw_line])
            continue
        lot_totals[lot_token] = {
            "weight": normalized_weight,
            "snippets": [raw_line],
        }

    if lot_totals:
        return lot_totals

    normalized_groups: dict[str, dict[str, object]] = {}
    for lot_token, payload in hu_totals.items():
        normalized_groups[lot_token] = {
            "weight": str(int(payload.get("weight_total", 0))),
            "snippets": list(payload.get("snippets", [])),
        }
    if not normalized_groups and len(section_lot_tokens) == 1 and section_net_weights:
        only_lot = next(iter(section_lot_tokens))
        normalized_groups[only_lot] = {
            "weight": str(max(section_net_weights)),
            "snippets": raw_lines[:6],
        }
    return normalized_groups


def _parse_neuman_split_weight(value: str | None) -> int | None:
    parsed = _parse_neuman_document_weight(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _parse_neuman_document_weight(value: str | None) -> float | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    token = normalized.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        try:
            return float(re.sub(r"[.,]", "", token))
        except ValueError:
            return None
    if re.fullmatch(r"\d+[.,]\d{3}", token):
        try:
            return float(token.replace(",", "."))
        except ValueError:
            return None
    if re.fullmatch(r"\d+", token):
        return float(token)
    return None


def _build_leichtmetall_row_split_candidates(
    document: Document | None,
    supplier_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if document is None or not document.pages:
        return []

    first_page = next((page for page in document.pages if page.numero_pagina == 1), document.pages[0])
    first_page_lines = _page_lines(first_page)
    normalized_first_page_lines = [_normalize_line(line) for line in first_page_lines]
    all_lines = [line for page in document.pages for line in _page_lines(page)]
    normalized_all_lines = [_normalize_line(line) for line in all_lines]

    ddt_number = _extract_leichtmetall_ddt_number(normalized_all_lines)
    purchase_number = _extract_leichtmetall_purchase_number(normalized_first_page_lines) or _extract_leichtmetall_purchase_number(normalized_all_lines)
    order_confirmation = _extract_leichtmetall_order_confirmation(normalized_first_page_lines) or _extract_leichtmetall_order_confirmation(normalized_all_lines)
    lega = _extract_leichtmetall_alloy(normalized_first_page_lines) or _extract_leichtmetall_alloy(normalized_all_lines)
    diametro = _extract_leichtmetall_diameter(normalized_first_page_lines) or _extract_leichtmetall_diameter(normalized_all_lines)
    quantity = _extract_leichtmetall_header_weight(normalized_first_page_lines) or _extract_leichtmetall_header_weight(normalized_all_lines)

    batch_groups = _extract_leichtmetall_batch_groups(document)
    if batch_groups:
        if quantity is not None:
            header_total = _parse_leichtmetall_weight_token(quantity)
            if header_total is not None:
                if len(batch_groups) == 1:
                    only_batch_payload = next(iter(batch_groups.values()))
                    only_batch_payload["weight_total"] = header_total
                else:
                    grouped_total = sum(int(payload.get("weight_total", 0)) for payload in batch_groups.values())
                    if 0 < grouped_total < header_total:
                        dominant_batch_payload = max(
                            batch_groups.values(),
                            key=lambda payload: (
                                int(payload.get("weight_total", 0)),
                                len(list(payload.get("snippets", []))),
                            ),
                        )
                        dominant_batch_payload["weight_total"] = int(dominant_batch_payload.get("weight_total", 0)) + (
                            header_total - grouped_total
                        )
        candidates: list[ReaderRowSplitCandidateResponse] = []
        for index, (batch, payload) in enumerate(batch_groups.items(), start=1):
            weight_total = int(payload.get("weight_total", 0))
            snippets = list(payload.get("snippets", []))
            candidates.append(
                ReaderRowSplitCandidateResponse(
                    candidate_index=index,
                    supplier_key=supplier_key,
                    ddt_number=ddt_number,
                    cdq=batch,
                    lega=lega,
                    diametro=diametro,
                    peso_netto=_format_leichtmetall_weight(weight_total) if weight_total > 0 else quantity,
                    colata=batch,
                    lot_batch_no=batch,
                    customer_order_no=purchase_number,
                    supplier_order_no=order_confirmation,
                    snippets=snippets[:6],
                )
            )
        return candidates

    if not any((ddt_number, purchase_number, lega, diametro, quantity)):
        return []

    return [
        ReaderRowSplitCandidateResponse(
            candidate_index=1,
            supplier_key=supplier_key,
            ddt_number=ddt_number,
            lega=lega,
            diametro=diametro,
            peso_netto=quantity,
            customer_order_no=purchase_number,
            supplier_order_no=order_confirmation,
            snippets=first_page_lines[:6],
        )
    ]


def _extract_leichtmetall_ddt_number(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\b(?:DELIVERY NOTE|BELEG)\s*:?\s*([0-9]{5,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_leichtmetall_purchase_number(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bPURCHASE\s+NUMBER\s*:?\s*([0-9][0-9.+/\-\s]{1,})\b", line)
        if match is not None:
            return _normalize_leichtmetall_order_token(match.group(1))
    return None


def _extract_leichtmetall_order_confirmation(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bORDER\s+CONFIRMATION\s*:?\s*([0-9][0-9./-]{3,})\b", line)
        if match is not None:
            return match.group(1).replace("/", "-")
    return None


def _extract_leichtmetall_alloy(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bALLOY\s+(?:EN\s+AW-?)?([0-9]{4}[A-Z]?)\b", line)
        if match is not None:
            return _normalize_leichtmetall_alloy(match.group(1))
    return None


def _extract_leichtmetall_diameter(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bDIAMETER\s+([0-9]+(?:[.,][0-9]+)?)\s*MM\b", line)
        if match is not None:
            return _normalize_decimal_value(match.group(1))
    return None


def _extract_leichtmetall_header_weight(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bQUANTITY\s*:?\s*([0-9]{1,3}(?:[.,][0-9]{3})+|\d+)\s*KG\b", line)
        if match is not None:
            return _normalize_leichtmetall_weight(match.group(1))
    return None


def _extract_leichtmetall_batch_groups(document: Document) -> dict[str, dict[str, object]]:
    batch_groups: dict[str, dict[str, object]] = {}
    candidate_pages = [page for page in document.pages if page.numero_pagina > 1] or document.pages

    for page in candidate_pages:
        for raw_line in _page_lines(page):
            line = _normalize_line(raw_line)
            if any(marker in line for marker in ("HANNOVER GMBH", "UST.ID.NR", "SWIFT:", "COBA DE FF")):
                continue
            batch = _extract_leichtmetall_batch_from_line(line)
            if batch is None:
                continue
            weight = _extract_leichtmetall_page2_row_weight(line, batch)
            if weight is None:
                continue
            entry = batch_groups.setdefault(batch, {"weight_total": 0, "snippets": []})
            entry["weight_total"] = int(entry["weight_total"]) + weight
            entry["snippets"] = _merge_snippets(entry["snippets"], [raw_line])

    return batch_groups


def _extract_leichtmetall_batch_from_line(line: str) -> str | None:
    matches = list(re.finditer(r"\b(\d{5})\b", line))
    if matches:
        return matches[-1].group(1)
    return None


def _extract_leichtmetall_page2_row_weight(line: str, batch: str) -> int | None:
    batch_match = None
    for match in re.finditer(rf"\b{re.escape(batch)}\b", line):
        batch_match = match
    if batch_match is None:
        return None
    prefix = line[: batch_match.start()]
    numeric_tokens = re.findall(r"\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?", prefix)
    for token in reversed(numeric_tokens):
        parsed = _parse_leichtmetall_weight_token(token)
        if parsed is not None:
            return parsed
    return None


def _parse_leichtmetall_weight_token(value: str | None) -> int | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    token = normalized.replace(" ", "")
    plain_digits = re.sub(r"[.,]", "", token)
    if len(plain_digits) > 5:
        return None
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        return int(re.sub(r"[.,]", "", token))
    if re.fullmatch(r"\d+", token):
        return int(token)
    if re.fullmatch(r"\d+[.,]\d+", token):
        integer_part, decimal_part = re.split(r"[.,]", token, maxsplit=1)
        if len(decimal_part) == 3:
            return int(integer_part + decimal_part)
    return None


def _format_leichtmetall_weight(value: int) -> str:
    return str(value)


def _normalize_leichtmetall_weight(value: str | None) -> str | None:
    parsed = _parse_leichtmetall_weight_token(value)
    if parsed is None:
        return None
    return _format_leichtmetall_weight(parsed)


def _normalize_leichtmetall_alloy(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    return normalized


def _normalize_leichtmetall_order_token(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    parts = [part for part in re.split(r"\s*\+\s*", normalized) if part]
    return " + ".join(parts) if parts else None


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


def _extract_metalba_ddt_number(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bDDT\s*([0-9]{2}[-/][0-9]{5})\b", line)
        if match is not None:
            return match.group(1).replace("/", "-")
    return None


def _extract_metalba_vs_rif(lines: list[str]) -> str | None:
    for line in lines:
        matches = re.findall(r"\b\d{1,3}/\d{2}\b", line)
        if matches and ("VS. RIF" in line or "DDT" in line or "LISTA IMBALLI" in line):
            return matches[0]
    return None


def _extract_metalba_rif_ord(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\b(\d{2}/\d{4})\b", line)
        if match is not None and ("RIF. ORD" in line or "DDT" in line or "LISTA IMBALLI" in line):
            return match.group(1)
    return None


def _extract_metalba_candidate_alloy(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bESTRUSO\s+A\.A\.\s*([1-9][0-9]{3}[A-Z]?)\s+(F|T\d+[A-Z0-9/-]*)\b", line)
        if match is not None:
            return f"{match.group(1)} {match.group(2)}"
    return None


def _extract_metalba_candidate_diameter(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bBARRA\s+TONDA\s+DIAM\s*([0-9]+(?:[.,][0-9]+)?)\s*MM\b", line)
        if match is not None:
            return match.group(1).replace(",", ".")
    return None


def _extract_metalba_candidate_weight(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bPESO\s+NETTO\s+KG\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)\b", line)
        if match is not None:
            return _normalize_split_weight(match.group(1))
    for line in lines:
        if "TOTALI" not in line:
            continue
        matches = re.findall(r"[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?", line)
        if matches:
            return _normalize_split_weight(matches[0])
    return None


def _extract_metalba_customer_code(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bVOSTRO\s+CODICE\s*:?\s*(A[0-9A-Z]{5,})\b", line)
        if match is not None:
            return match.group(1)
    for line in lines:
        match = re.search(r"\b(A[0-9A-Z]{5,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_metalba_candidate_cast(lines: list[str]) -> str | None:
    cast_candidates: list[str] = []
    for line in lines:
        for token in re.findall(r"\b\d{5}[A-Z]\b", line):
            cast_candidates.append(token)
    return cast_candidates[-1] if cast_candidates else None


def _normalize_split_weight(value: str) -> str:
    token = value.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?", token):
        if token.count(",") == 1 and token.rfind(",") > token.rfind("."):
            integer_part, decimal_part = token.rsplit(",", 1)
            if len(decimal_part) == 2:
                integer_part = integer_part.replace(".", "").replace(",", "")
                return integer_part
        return re.sub(r"[.,]", "", token)
    return token.replace(",", ".")


def _extract_aluminium_bozen_ddt_number(document: Document | None, lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bNUM\.\s*([0-9]{2,6})\b", line)
        if match is not None and "DELIVERY NOTE" in line:
            return match.group(1)
    for line in lines:
        match = re.search(r"\bDELIVERY NOTE.*?\bNUM\.\s*([0-9]{2,6})\b", line)
        if match is not None:
            return match.group(1)
    if document is not None:
        header_value = _extract_aluminium_bozen_ddt_number_from_header_ocr(document)
        if header_value is not None:
            return header_value
        stem = Path(document.nome_file_originale).stem
        has_delivery_header = any("DELIVERY NOTE" in line or "DOCUMENTO DI TRASPORTO" in line for line in lines)
        if has_delivery_header and re.fullmatch(r"\d{2,6}", stem):
            return stem
    return None


def _extract_aluminium_bozen_ddt_number_from_header_ocr(document: Document) -> str | None:
    first_page = next((page for page in document.pages if page.numero_pagina == 1 and page.immagine_pagina_storage_key), None)
    if first_page is None or not first_page.immagine_pagina_storage_key:
        return None

    image_path = Path(settings.document_storage_root) / Path(first_page.immagine_pagina_storage_key)
    if not image_path.exists():
        return None

    try:
        with Image.open(image_path) as image:
            width, height = image.size
            crop_specs = (
                ((0, int(height * 0.30), width, int(height * 0.40)), "--psm 6"),
                ((int(width * 0.45), int(height * 0.30), width, int(height * 0.40)), "--psm 11"),
            )
    except (OSError, pytesseract.TesseractNotFoundError):
        return None

    saw_delivery_header = False
    for crop_box, config in crop_specs:
        try:
            with Image.open(image_path) as image:
                crop = image.crop(crop_box)
                text = pytesseract.image_to_string(crop, lang="eng+ita", config=config)
        except (OSError, pytesseract.TesseractNotFoundError):
            continue

        normalized_text = _normalize_line(text)
        if "DELIVERY NOTE" in normalized_text or "DOCUMENTO DI TRASPORTO" in normalized_text:
            saw_delivery_header = True
        direct = re.search(r"\bNUM\.?\s*([0-9]{2,6})\b", normalized_text)
        if direct is not None:
            return direct.group(1)
    if saw_delivery_header:
        stem = Path(document.nome_file_originale).stem
        if re.fullmatch(r"\d{2,6}", stem):
            return stem
    return None


def _extract_aluminium_bozen_order(line: str) -> str | None:
    match = re.search(r"\bRIF\.\s*NS\.\s*ODV\s*N\.?\s*([0-9]+(?:[./][0-9]+)?)\b", line)
    if match is not None:
        return match.group(1).replace("/", ".")
    return None


def _extract_aluminium_bozen_order_from_window(lines: list[str], index: int) -> str | None:
    preferred_indices = list(range(index, max(-1, index - 6), -1)) + list(range(index + 1, min(len(lines), index + 4)))
    for candidate_index in preferred_indices:
        if candidate_index < 0 or candidate_index >= len(lines):
            continue
        order = _extract_aluminium_bozen_order(lines[candidate_index])
        if order is not None:
            return order
    return None


def _extract_aluminium_bozen_customer_order_from_line(line: str) -> str | None:
    normalized = line.upper()
    normalized = normalized.replace("/", "-")
    normalized = re.sub(r"(?<=\d)\.(?=\d)", "-", normalized)
    trailing_date_match = re.search(
        r"\b(?:VS\.?\s*ODV|RIF\.\s*ORDINE\s*CLIENTE)\b[^0-9]*([0-9]{1,6})\D+([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
        normalized,
    )
    if trailing_date_match is not None:
        return f"{int(trailing_date_match.group(1))}-{trailing_date_match.group(2)}"

    leading_date_match = re.search(
        r"\b(?:VS\.?\s*ODV|RIF\.\s*ORDINE\s*CLIENTE)\b[^0-9]*([0-9]{4}-[0-9]{2}-[0-9]{2})\D+([0-9]{1,6})\b",
        normalized,
    )
    if leading_date_match is not None:
        return f"{int(leading_date_match.group(2))}-{leading_date_match.group(1)}"
    return None


def _extract_aluminium_bozen_customer_order_from_window(lines: list[str], index: int) -> str | None:
    preferred_indices = list(range(index, max(-1, index - 8), -1)) + list(range(index + 1, min(len(lines), index + 6)))
    for candidate_index in preferred_indices:
        if candidate_index < 0 or candidate_index >= len(lines):
            continue
        customer_order = _extract_aluminium_bozen_customer_order_from_line(lines[candidate_index])
        if customer_order is not None:
            return customer_order
    return None


def _extract_aluminium_bozen_profile_code_from_line(line: str) -> str | None:
    match = re.match(r"^\s*([A-Z0-9][A-Z0-9]{5,})\b", line)
    if match is not None:
        token = match.group(1)
        if not token.startswith(("CAST", "NUM", "RIF")):
            return token
    return None


def _extract_aluminium_bozen_article_from_line(line: str) -> str | None:
    match = re.search(r"\(([0-9A-Z-]{6,})\)", line)
    if match is not None:
        return match.group(1)
    return None


def _extract_aluminium_bozen_material_label_from_line(line: str) -> str | None:
    compact_line = " ".join(line.split())
    profile_code = _extract_aluminium_bozen_profile_code_from_line(compact_line)
    if profile_code is None:
        return None
    without_code = compact_line[len(profile_code) :].strip()
    article_match = re.search(r"\([0-9A-Z-]{6,}\)", without_code)
    if article_match is not None:
        without_code = without_code[: article_match.start()].strip()
    without_code = re.sub(r"\b[0-9]+(?:[.,][0-9]+)?\b.*$", "", without_code).strip()
    if not without_code:
        return None
    word_count = len(re.findall(r"[A-Z]+", without_code))
    if word_count < 2:
        return None
    if without_code in {"ALL. AND PHYSICAL STATUS", "DES. ART. CLIENTE"}:
        return None
    return without_code


def _extract_aluminium_bozen_lega_from_line(line: str) -> str | None:
    match = re.search(r"\b([0-9]{4}[A-Z]*)\s*(?:HF\s*/\s*F|H\s*/\s*F|G\s*/\s*F|GF\b|HF\b|/F\b|F\b)", line)
    if match is not None:
        return f"{match.group(1)} F"
    return None


def _extract_aluminium_bozen_lega_from_window(lines: list[str], index: int) -> str | None:
    preferred_indices = list(range(index, min(len(lines), index + 4))) + list(range(max(0, index - 3), index))
    for candidate_index in preferred_indices:
        line = lines[candidate_index]
        lega = _extract_aluminium_bozen_lega_from_line(line)
        if lega is not None:
            return lega
    return None


def _extract_aluminium_bozen_diameter_from_line(line: str) -> str | None:
    match = re.search(r"\bBARRA TONDA\s+([0-9]+(?:[.,][0-9]+)?)\b", line)
    if match is not None:
        return _normalize_decimal_value(match.group(1))
    structural = re.search(
        r"^\s*[A-Z0-9][A-Z0-9]{5,}\s+[A-Z][A-Z\s]+?\s+([0-9]+(?:[.,][0-9]+)?)\s+\([0-9A-Z-]{6,}\)",
        line,
    )
    if structural is not None:
        return _normalize_decimal_value(structural.group(1))
    fallback = re.search(r"\b([0-9]+(?:[.,][0-9]+)?)\s*\([0-9A-Z-]{6,}\)", line)
    if fallback is not None:
        return _normalize_decimal_value(fallback.group(1))
    return None


def _extract_aluminium_bozen_diameter_from_window(lines: list[str], index: int) -> str | None:
    preferred_indices = [index, *range(max(0, index - 2), index), *range(index + 1, min(len(lines), index + 3))]
    for candidate_index in preferred_indices:
        diameter = _extract_aluminium_bozen_diameter_from_line(lines[candidate_index])
        if diameter is not None:
            return diameter
    return None


def _extract_aluminium_bozen_weight_from_line(line: str) -> str | None:
    match = re.search(r"\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\)?\s*$", line)
    if match is not None:
        parsed = _parse_aluminium_bozen_weight_token(match.group(1))
        if parsed is not None:
            return _format_aluminium_bozen_weight(parsed)
    return None


def _extract_aluminium_bozen_cast_from_window(lines: list[str], index: int) -> str | None:
    preferred_indices = list(range(index, min(len(lines), index + 5))) + list(range(max(0, index - 4), index))
    for candidate_index in preferred_indices:
        line = lines[candidate_index]
        match = re.search(r"\bCAST\s+NR\.?\s*([0-9]{5,}[A-Z0-9]*)\b", line)
        if match is not None:
            return match.group(1)
    return None


def _collect_aluminium_bozen_snippets(lines: list[str], index: int) -> list[str]:
    start_index = max(0, index - 3)
    end_index = min(len(lines), index + 3)
    return lines[start_index:end_index]


def _merge_aluminium_bozen_candidates(
    candidates: list[ReaderRowSplitCandidateResponse],
    lines: list[str],
    ddt_number: str | None,
    supplier_key: str,
) -> list[ReaderRowSplitCandidateResponse]:
    if not candidates:
        return []

    packing_weights = _extract_aluminium_bozen_packing_weights(lines)
    packing_cdqs = _extract_aluminium_bozen_packing_cdqs(lines)
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}

    for candidate in candidates:
        key = (
            candidate.article_code or candidate.profile_code or candidate.supplier_order_no or "",
            candidate.lega or "",
            candidate.diametro or "",
        )
        entry = grouped.setdefault(
            key,
            {
                "candidate": ReaderRowSplitCandidateResponse(
                    candidate_index=0,
                    supplier_key=supplier_key,
                    ddt_number=ddt_number or candidate.ddt_number,
                    cdq=candidate.cdq,
                    profile_code=candidate.profile_code,
                    article_code=candidate.article_code,
                    lega=candidate.lega,
                    diametro=candidate.diametro,
                    peso_netto=None,
                    colata=candidate.colata,
                    supplier_order_no=candidate.supplier_order_no,
                    snippets=[],
                ),
                "weight_total": 0,
                "weight_count": 0,
                "snippets": [],
                "casts": [],
                "orders": [],
                "cdqs": [],
                "customer_orders": [],
                "profile_codes": [],
            },
        )

        weight_value = _parse_aluminium_bozen_weight(candidate.peso_netto)
        if weight_value is not None:
            entry["weight_total"] = int(entry["weight_total"]) + weight_value
            entry["weight_count"] = int(entry["weight_count"]) + 1
        entry["snippets"] = _merge_snippets(entry["snippets"], candidate.snippets)
        if candidate.colata:
            entry["casts"].append(candidate.colata)
        if candidate.supplier_order_no:
            entry["orders"].append(candidate.supplier_order_no)
        if candidate.cdq:
            entry["cdqs"].append(candidate.cdq)
        if candidate.customer_order_no:
            entry["customer_orders"].append(candidate.customer_order_no)
        if candidate.profile_code:
            entry["profile_codes"].append(candidate.profile_code)

    merged: list[ReaderRowSplitCandidateResponse] = []
    for index, (_, entry) in enumerate(grouped.items(), start=1):
        candidate = entry["candidate"]
        packed_weight = packing_weights.get(candidate.supplier_order_no or "")
        if int(entry["weight_count"]) > 0:
            candidate.peso_netto = _format_aluminium_bozen_weight(int(entry["weight_total"]))
        elif packed_weight is not None:
            candidate.peso_netto = packed_weight
        candidate.colata = _choose_best_aluminium_bozen_cast(entry["casts"], candidate.colata)
        candidate.supplier_order_no = _choose_best_aluminium_bozen_order(entry["orders"], candidate.supplier_order_no)
        candidate.cdq = packing_cdqs.get(candidate.supplier_order_no or "") or _choose_best_aluminium_bozen_cdq(
            entry["cdqs"], candidate.cdq
        )
        candidate.customer_order_no = _choose_best_aluminium_bozen_customer_order(
            entry["customer_orders"], candidate.customer_order_no
        )
        candidate.profile_code = _choose_best_aluminium_bozen_profile_code(entry["profile_codes"], candidate.profile_code)
        candidate.snippets = list(entry["snippets"])[:6]
        candidate.candidate_index = index
        merged.append(candidate)
    return _drop_weaker_aluminium_bozen_candidates(merged)


def _extract_aluminium_bozen_packing_weights(lines: list[str]) -> dict[str, str]:
    weights_by_order: dict[str, int] = {}
    current_order: str | None = None
    in_section = False

    for raw_line in lines:
        line = _normalize_line(raw_line)
        section_match = re.search(r"\bRIF\. ORDINE AB ODV\s+\d{4}\.([0-9]+(?:\.[0-9]+)?)\b", line)
        if section_match is not None:
            current_order = section_match.group(1)
            in_section = False
            continue
        if current_order is None:
            continue
        if "COLLO" in line and "P.NETTO KG" in line:
            in_section = True
            continue
        if "RIF. ORDINE AB ODV" in line:
            in_section = False
            continue
        if not in_section:
            continue
        net_weight = _extract_aluminium_bozen_packing_row_net(line)
        if net_weight is None:
            continue
        weights_by_order[current_order] = weights_by_order.get(current_order, 0) + net_weight

    return {order: _format_aluminium_bozen_weight(total) for order, total in weights_by_order.items()}


def _extract_aluminium_bozen_packing_cdqs(lines: list[str]) -> dict[str, str]:
    cdq_by_order: dict[str, str] = {}
    current_order: str | None = None

    for raw_line in lines:
        line = _normalize_line(raw_line)
        section_match = re.search(r"\bRIF\. ORDINE AB ODV\s+\d{4}\.([0-9]+(?:\.[0-9]+)?)\b", line)
        if section_match is not None:
            current_order = section_match.group(1)
        cert_number = _extract_aluminium_bozen_cert_number_from_line(line)
        if current_order is not None and cert_number is not None:
            cdq_by_order[current_order] = cert_number
        if current_order is None:
            continue

    return cdq_by_order


def _extract_aluminium_bozen_packing_row_net(line: str) -> int | None:
    id_match = re.search(r"\b\d{4}-\d{7}\b", line)
    if id_match is None:
        return None
    cast_match = re.search(r"\b([0-9A-Z]{5,})\b\s*$", line)
    if cast_match is None:
        return None

    prefix = line[id_match.end() : cast_match.start()]
    numeric_tokens = re.findall(r"\d+(?:[.,]\d+)?", prefix)
    if len(numeric_tokens) < 3:
        return None

    net_candidate = numeric_tokens[-2]
    return _parse_aluminium_bozen_weight_token(net_candidate)


def _extract_aluminium_bozen_cdq_from_window(lines: list[str], index: int) -> str | None:
    for candidate_index in range(max(0, index - 4), min(len(lines), index + 5)):
        line = lines[candidate_index]
        cert_number = _extract_aluminium_bozen_cert_number_from_line(line)
        if cert_number is not None:
            return cert_number
    return None


def _extract_aluminium_bozen_cert_number_from_line(line: str) -> str | None:
    anchor_match = re.search(r"\bCERT(?:\.|\s|$)", line)
    if anchor_match is None:
        return None
    match = re.search(r"\b([0-9]{4,8})\b", line[anchor_match.end() :])
    if match is None:
        return None
    return match.group(1)


def _merge_snippets(current: list[str], incoming: list[str]) -> list[str]:
    merged = list(current)
    seen = {snippet.strip() for snippet in merged if snippet.strip()}
    for snippet in incoming:
        key = snippet.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(snippet)
    return merged


def _parse_aluminium_bozen_weight(value: str | None) -> int | None:
    cleaned = _normalize_text(value)
    if cleaned is None:
        return None
    return _parse_aluminium_bozen_weight_token(cleaned)


def _parse_aluminium_bozen_weight_token(value: str | None) -> int | None:
    if value is None:
        return None
    token = value.strip().replace(" ", "")
    if not token:
        return None
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        return int(re.sub(r"[.,]", "", token))
    if re.fullmatch(r"\d+", token):
        return int(token)
    if re.fullmatch(r"\d+[.,]\d+", token):
        normalized = token.replace(",", ".")
        try:
            return int(round(float(normalized) * 1000))
        except ValueError:
            return None
    return None


def _format_aluminium_bozen_weight(value: int) -> str:
    if value < 1000:
        return str(value)
    chunks: list[str] = []
    remaining = value
    while remaining >= 1000:
        chunks.append(f"{remaining % 1000:03d}")
        remaining //= 1000
    chunks.append(str(remaining))
    return ".".join(reversed(chunks))


def _choose_best_aluminium_bozen_cast(casts: list[str], fallback: str | None) -> str | None:
    if not casts:
        return fallback
    normalized_counts: dict[str, int] = {}
    preferred_by_key: dict[str, str] = {}
    for cast in casts:
        normalized = cast.replace("0", "O")
        normalized_counts[normalized] = normalized_counts.get(normalized, 0) + 1
        current = preferred_by_key.get(normalized)
        if current is None or _cast_quality_score(cast) > _cast_quality_score(current):
            preferred_by_key[normalized] = cast
    best_key = max(normalized_counts.items(), key=lambda item: (item[1], _cast_quality_score(preferred_by_key[item[0]])))[0]
    return preferred_by_key[best_key]


def _choose_best_aluminium_bozen_order(orders: list[str], fallback: str | None) -> str | None:
    if not orders:
        return fallback
    counts: dict[str, int] = {}
    for order in orders:
        counts[order] = counts.get(order, 0) + 1
    return max(counts.items(), key=lambda item: (item[1], len(item[0])))[0]


def _choose_best_aluminium_bozen_profile_code(profile_codes: list[str], fallback: str | None) -> str | None:
    if not profile_codes:
        return fallback
    counts: dict[str, int] = {}
    for profile_code in profile_codes:
        counts[profile_code] = counts.get(profile_code, 0) + 1
    return max(counts.items(), key=lambda item: (item[1], len(item[0])))[0]


def _choose_best_aluminium_bozen_customer_order(customer_orders: list[str], fallback: str | None) -> str | None:
    if not customer_orders:
        return fallback
    counts: dict[str, int] = {}
    for customer_order in customer_orders:
        counts[customer_order] = counts.get(customer_order, 0) + 1
    return max(counts.items(), key=lambda item: (item[1], len(item[0])))[0]


def _choose_best_aluminium_bozen_cdq(cdqs: list[str], fallback: str | None) -> str | None:
    if not cdqs:
        return fallback
    counts: dict[str, int] = {}
    for cdq in cdqs:
        normalized = _normalize_text(cdq)
        if normalized is None or not re.fullmatch(r"\d{4,8}", normalized):
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    if counts:
        return max(counts.items(), key=lambda item: (item[1], len(item[0])))[0]
    return fallback


def _cast_quality_score(value: str) -> tuple[int, int]:
    alpha_count = sum(1 for char in value if char.isalpha())
    return (alpha_count, len(value))


def _drop_weaker_aluminium_bozen_candidates(
    candidates: list[ReaderRowSplitCandidateResponse],
) -> list[ReaderRowSplitCandidateResponse]:
    filtered: list[ReaderRowSplitCandidateResponse] = []
    for candidate in candidates:
        if candidate.supplier_order_no:
            stronger_same_order = next(
                (
                    other
                    for other in candidates
                    if other is not candidate
                    and other.supplier_order_no == candidate.supplier_order_no
                    and (other.diametro or other.colata)
                    and not (candidate.diametro or candidate.colata)
                ),
                None,
            )
            if stronger_same_order is not None:
                continue
        filtered.append(candidate)
    for index, candidate in enumerate(filtered, start=1):
        candidate.candidate_index = index
    return filtered


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
