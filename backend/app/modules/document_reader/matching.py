from __future__ import annotations

import re

from app.modules.acquisition.models import AcquisitionRow, DocumentPage


def _string_or_none(value: str | int | None) -> str | None:
    if value is None:
        return None
    string_value = str(value).strip()
    return string_value or None


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


def _best_page_text(page: DocumentPage) -> str:
    pdf_text = _normalize_text(page.testo_estratto)
    ocr_text = _normalize_text(page.ocr_text)
    if ocr_text and _pdf_text_needs_ocr_fallback(pdf_text):
        return ocr_text
    return pdf_text or ocr_text or ""


def _page_lines(page: DocumentPage) -> list[str]:
    return [line.strip() for line in _best_page_text(page).splitlines() if line.strip()]


def _build_match(page_id: int, snippet: str, value: str) -> dict[str, str | int]:
    return {
        "page_id": page_id,
        "snippet": snippet,
        "standardized": value,
        "final": value,
    }


def detect_ddt_core_matches(
    pages: list[DocumentPage],
    *,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}

    supplier_detector = {
        "leichtmetall": _detect_leichtmetall_ddt_core_matches,
        "metalba": _detect_metalba_ddt_core_matches,
        "aww": _detect_aww_ddt_core_matches,
        "aluminium_bozen": _detect_aluminium_bozen_ddt_core_matches,
        "zalco": _detect_zalco_ddt_core_matches,
        "arconic_hannover": _detect_arconic_hannover_ddt_core_matches,
        "neuman": _detect_neuman_ddt_core_matches,
        "grupa_kety": _detect_grupa_kety_ddt_core_matches,
        "impol": _detect_impol_ddt_core_matches,
    }.get(supplier_key)
    if supplier_detector is not None:
        matches.update(supplier_detector(pages))

    for page in pages:
        lines = _page_lines(page)
        for line in lines:
            normalized_line = line.lower()
            if "ddt" not in matches:
                ddt_number = _extract_ddt_number_from_line(normalized_line)
                if ddt_number is not None:
                    matches["ddt"] = _build_match(page.id, line, ddt_number)
            if "cdq" not in matches:
                explicit_cdq = _extract_explicit_cdq_from_line(normalized_line)
                if explicit_cdq is not None:
                    matches["cdq"] = _build_match(page.id, line, explicit_cdq)
            if supplier_key != "aww" and "diametro" not in matches:
                diameter = _extract_diameter_from_line(normalized_line)
                if diameter is not None:
                    matches["diametro"] = _build_match(page.id, line, diameter)
            if supplier_key != "aww" and "peso" not in matches:
                weight = _extract_weight_from_line(normalized_line)
                if weight is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(weight))
    return matches


def extract_supplier_match_fields(
    pages: list[DocumentPage],
    supplier_key: str | None,
    document_type: str,
) -> dict[str, str]:
    if supplier_key is None:
        return {}
    lines: list[str] = []
    for page in pages:
        lines.extend(_page_lines(page))
    if not lines:
        return {}

    supplier_match_extractor = {
        "metalba": lambda current_lines, current_type: (
            {
                "vs_rif": (values := _extract_metalba_ddt_reference_values(current_lines))[0],
                "rif_ord_root": _normalize_commessa_root(values[1]),
            }
            if current_type == "ddt"
            else {
                "ordine_cliente": (values := _extract_metalba_certificate_reference_values(current_lines))[0],
                "commessa_root": _normalize_commessa_root(values[1]),
            }
        ),
        "aww": lambda current_lines, current_type: (
            {
                "your_part_number": _extract_value_near_anchor(current_lines, ("your part number",)),
                "part_number": _extract_code_pattern(current_lines, r"\bP3-\d{5}-\d{4}\b"),
                "order_confirmation_root": _normalize_order_confirmation_root(
                    _extract_value_near_anchor(current_lines, ("batch number (oc)", "batch number oc"))
                ),
            }
            if current_type == "ddt"
            else {
                "kunden_teile_nr": _extract_value_near_anchor(current_lines, ("kunden-teile-nr", "customer part number")),
                "artikel_nr": _extract_value_near_anchor(current_lines, ("artikel-nr", "article no", "article number")),
                "auftragsbestaetigung_root": _normalize_order_confirmation_root(
                    _extract_value_near_anchor(current_lines, ("auftragsbestätigung", "auftragsbestatigung", "order confirmation"))
                ),
            }
        ),
        "aluminium_bozen": lambda current_lines, current_type: {
            "article": _extract_code_pattern(current_lines, r"\b14BT[0-9A-Z-]+\b"),
            "customer_code": _extract_aluminium_bozen_customer_code(current_lines),
            "customer_order_normalized": _extract_aluminium_bozen_customer_order(current_lines, document_type=current_type),
        },
        "zalco": lambda current_lines, current_type: _extract_zalco_match_fields(current_lines, document_type=current_type),
        "arconic_hannover": lambda current_lines, current_type: _extract_arconic_hannover_match_fields(current_lines),
        "neuman": lambda current_lines, current_type: _extract_neuman_match_fields(current_lines),
        "grupa_kety": lambda current_lines, current_type: _extract_grupa_kety_match_fields(current_lines, document_type=current_type),
        "impol": lambda current_lines, current_type: _extract_impol_match_fields(current_lines, document_type=current_type),
    }.get(supplier_key)

    if supplier_match_extractor is None:
        return {}
    return supplier_match_extractor(lines, document_type)


def _extract_ddt_number_from_line(line: str) -> str | None:
    delivery_match = re.search(r"\b(?:delivery\s+note|beleg)\s*:?\s*([0-9]{5,})\b", line)
    if delivery_match is not None:
        return delivery_match.group(1)
    delivery_num_match = re.search(r"(?:delivery\s+note|documento\s+di\s+trasporto).*?\bnum\.?\s*([0-9]{2,})\b", line)
    if delivery_num_match is not None:
        return delivery_num_match.group(1)
    transport_match = re.search(r"\bddt\s*([0-9]{2}[-/][0-9]{5})\b", line)
    if transport_match is not None:
        return transport_match.group(1).replace("/", "-").upper()
    plain_transport_match = re.search(r"\bddt(?:\s*n[or°.]*)?[:\s-]*([0-9][0-9/-]{4,})\b", line)
    if plain_transport_match is not None:
        return plain_transport_match.group(1).replace("/", "-").upper()
    return None


def _extract_explicit_cdq_from_line(line: str) -> str | None:
    if "cdq" not in line:
        return None
    explicit = _extract_by_keywords(line, ("cdq",))
    if explicit is None or explicit in {"3.1", "31"}:
        return None
    return explicit


def _extract_diameter_from_line(line: str) -> str | None:
    patterns = (
        r"\bdiam(?:eter)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b",
        r"\bouter\s+di\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b",
        r"\bbarra\s+tonda\s+diam\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b",
        r"\bø\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b",
    )
    for pattern in patterns:
        match = re.search(pattern, line)
        if match is not None:
            return _normalize_decimal_value(match.group(1))
    return None


def _extract_by_keywords(line: str, keywords: tuple[str, ...]) -> str | None:
    if not any(keyword in line for keyword in keywords):
        return None
    pattern = re.compile(r"(?:[:=\-]|\b)([a-z0-9][a-z0-9/-]{2,})\s*$")
    tail_match = pattern.search(line)
    if tail_match is not None:
        return tail_match.group(1).upper()

    token_pattern = re.compile(r"([a-z0-9][a-z0-9/-]{2,})")
    tokens = token_pattern.findall(line)
    for token in reversed(tokens):
        if token not in {"cast", "charge", "batch", "colata", "heat", "cdq", "cert", "certificate"}:
            return token.upper()
    return None


def _extract_weight_from_line(line: str) -> str | None:
    if not any(keyword in line for keyword in ("net weight", "peso netto", "peso net", "netto", "quantity", "net kg", "totali", "gross weight", "gross kg")):
        return None
    matches = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?", line)
    if not matches:
        return None
    return matches[-1]


def _normalize_weight(value: str) -> str:
    return _normalize_decimal_value(value)


def _normalize_decimal_value(value: str) -> str:
    normalized = value.strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", ".")
    return normalized


def _detect_leichtmetall_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    batch_counts: dict[str, tuple[int, int, str]] = {}
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if "ddt" not in matches:
                match = re.search(r"\b(?:delivery\s+note|beleg)\s*:?\s*([0-9]{5,})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1))
            if "ordine" not in matches:
                match = re.search(r"\border\s+confirmation\s+([0-9][0-9./-]{3,})\b", lowered)
                if match is not None:
                    matches["ordine"] = _build_match(page.id, line, match.group(1).replace("/", "-"))
            if "diametro" not in matches:
                match = re.search(r"\bdiameter\s+([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
            if "peso" not in matches:
                match = re.search(r"\bquantity\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*kg\b", lowered)
                if match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))
            batch_match = re.search(r"\b(\d{5})\b\s+\d+\s*$", line)
            if batch_match is not None:
                token = batch_match.group(1)
                count, page_id, snippet = batch_counts.get(token, (0, page.id, line))
                batch_counts[token] = (count + 1, page_id, snippet)
    if "colata" not in matches and batch_counts:
        token, (count, page_id, snippet) = max(batch_counts.items(), key=lambda item: item[1][0])
        if count >= 2:
            matches["colata"] = _build_match(page_id, snippet, token)
    return matches


def _detect_metalba_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    cast_counts: dict[str, tuple[int, int, str]] = {}
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if "ddt" not in matches:
                match = re.search(r"\bddt\s*([0-9]{2}[-/][0-9]{5})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1).replace("/", "-").upper())
            if "diametro" not in matches:
                match = re.search(r"\bbarra\s+tonda\s+diam\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
            if "peso" not in matches:
                match = re.search(r"\bpeso\s+netto\s+kg\s*([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\b", lowered)
                if match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))
            cast_match = re.search(r"\b([0-9]{5}[a-z])\b", lowered)
            if cast_match is not None and "colate" not in lowered and "kg" not in lowered:
                token = cast_match.group(1).upper()
                count, page_id, snippet = cast_counts.get(token, (0, page.id, line))
                cast_counts[token] = (count + 1, page_id, snippet)
    if "colata" not in matches and cast_counts:
        token, (count, page_id, snippet) = max(cast_counts.items(), key=lambda item: item[1][0])
        if count >= 2:
            matches["colata"] = _build_match(page_id, snippet, token)
    return matches


def _detect_aww_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    position_count = 0
    for page in pages:
        for line in _page_lines(page):
            lowered = line.casefold()
            if re.match(r"^\d{3}\s+[a-z0-9-]{4,}", lowered):
                position_count += 1
            if "ddt" not in matches:
                match = re.search(r"\bdelivery\s+note\s+([0-9]{5,})\b", lowered)
                if match is not None:
                    matches["ddt"] = _build_match(page.id, line, match.group(1))
            if "ordine" not in matches:
                match = re.search(r"\border\s+confirmation\s*:\s*([0-9][0-9-]{5,})\b", lowered)
                if match is not None:
                    matches["ordine"] = _build_match(page.id, line, match.group(1))
    if position_count <= 1:
        for page in pages:
            for line in _page_lines(page):
                lowered = line.casefold()
                if "diametro" not in matches:
                    match = re.search(r"\bouter\s+di\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                    if match is not None:
                        matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(match.group(1)))
                if "peso" not in matches:
                    match = re.search(r"\bnet\s+weight\b.*?([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\b", lowered)
                    if match is not None:
                        matches["peso"] = _build_match(page.id, line, _normalize_weight(match.group(1)))
    return matches


def _detect_aluminium_bozen_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    packing_section_active = False
    current_cert_number: str | None = None
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()
            if "ddt" not in matches:
                ddt_match = _extract_ddt_number_from_line(lowered)
                if ddt_match is not None:
                    matches["ddt"] = _build_match(page.id, line, ddt_match)
            if "ordine" not in matches:
                order_match = re.search(r"\brif\.\s*ns\.\s*odv\s*n\.?\s*([0-9]+(?:[./][0-9]+)?)", lowered)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1).replace("/", "."))
            if "diametro" not in matches:
                diameter_match = re.search(r"\bbarra\s+tonda\s+([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
            if "colata" not in matches:
                cast_match = re.search(r"\bcast\s+nr\.?\s*([0-9]{6,}[A-Z0-9])\b", normalized, re.IGNORECASE)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1).upper())
            cert_match = re.search(r"\bcert\.\s*n[°o.]?\s*([0-9]{4,})\b", lowered)
            if cert_match is not None:
                current_cert_number = cert_match.group(1)
                if "numero_certificato_ddt" not in matches:
                    matches["numero_certificato_ddt"] = _build_match(page.id, line, current_cert_number)
                packing_section_active = True
                continue
            if packing_section_active:
                if current_cert_number and "numero_certificato_ddt" not in matches and current_cert_number in lowered:
                    matches["numero_certificato_ddt"] = _build_match(page.id, line, current_cert_number)
                if "rif. ordine cliente" in lowered or "articolo" in lowered or "lega stato fisico" in lowered:
                    continue
                if "totali" in lowered:
                    packing_section_active = False
                    continue
                row_match = re.search(
                    r"\b\d{4}-\d{6,}\s+\d+\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,][0-9]+)?)\s+\d+\s+([0-9]{6,}[A-Z0-9]?)\b",
                    normalized,
                    re.IGNORECASE,
                )
                if row_match is not None:
                    if "peso" not in matches:
                        matches["peso"] = _build_match(page.id, line, _normalize_weight(row_match.group(2)))
                    if "colata" not in matches:
                        matches["colata"] = _build_match(page.id, line, row_match.group(3).upper())
                    continue
            if "peso" not in matches:
                inline_weight_match = re.search(r"\bbarra\s+tonda\s+\d+(?:[.,]\d+)?\b.*?\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\)?\s*$", lowered)
                if inline_weight_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(inline_weight_match.group(1)))
    return matches


def _detect_zalco_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()
            if "ddt" not in matches:
                order_line_match = re.search(r"\border\b.*?\b(\d{8})\b.*?\b(0{0,4}\d{5})\b", lowered)
                if order_line_match is not None:
                    matches["ddt"] = _build_match(page.id, line, str(int(order_line_match.group(2))))
            if "ordine" not in matches:
                order_match = re.search(r"\border\b.*?\b(\d{8})\b", lowered)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))
            if "diametro" not in matches:
                diameter_match = re.search(r"\bformat\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
            if "peso" not in matches:
                weight_match = re.search(r"\bpoids\s*net\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if weight_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(weight_match.group(1)))
            if "colata" not in matches:
                cast_match = re.search(r"^\s*(?:\d{4}\s+)?(\d{5})\s+\d{3}\s+\d+\s+[0-9]+", normalized)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1))
    return matches


def _detect_arconic_hannover_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()
            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s+(\d{6,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))
            if "ordine" not in matches:
                customer_po_match = re.search(r"\bcustomer\s+purchase\s+order\s+([0-9][0-9A-Z/-]{1,})\b", normalized, re.IGNORECASE)
                if customer_po_match is not None:
                    matches["ordine"] = _build_match(page.id, line, customer_po_match.group(1).upper())
            if "diametro" not in matches:
                diameter_match = re.search(r"\b(?:die\s*/\s*dimension|die\s*dimension)\s*RD\s*([0-9]+(?:[.,][0-9]+)?)\b", normalized, re.IGNORECASE)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
            if "colata" not in matches:
                cast_match = re.search(r"\b(C\d{9,})\b", normalized, re.IGNORECASE)
                if cast_match is not None:
                    matches["colata"] = _build_match(page.id, line, cast_match.group(1).upper())
            if "peso" not in matches and "line total" in lowered:
                total_match = re.search(
                    r"\bline\s+total\b.*?\b\d+\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\s+([0-9]+(?:[.,]\d{3})*(?:[.,]\d+)?)\s+\d+\b",
                    normalized,
                    re.IGNORECASE,
                )
                if total_match is not None:
                    matches["peso"] = _build_match(page.id, line, _normalize_weight(total_match.group(2)))
    return matches


def _detect_neuman_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()
            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s+(\d{6,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))
            if "ordine" not in matches:
                order_match = re.search(r"\bcustomer\s+order\s+number\s*:\s*([0-9]{1,6})\b", normalized, re.IGNORECASE)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))
            if "diametro" not in matches:
                diameter_match = re.search(r"\brundstangen\s*:\s*@\s*([0-9]+(?:[.,][0-9]+)?)\s*mm\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
    return matches


def _detect_grupa_kety_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    heat_candidates: set[str] = set()
    for page in pages:
        for line in _page_lines(page):
            normalized = _normalize_mojibake_numeric_text(line)
            lowered = normalized.casefold()
            if "ddt" not in matches:
                delivery_match = re.search(r"\bdelivery\s+note\s*:?\s*(\d{4,})\b", lowered)
                if delivery_match is not None:
                    matches["ddt"] = _build_match(page.id, line, delivery_match.group(1))
            if "ordine" not in matches:
                order_match = re.search(r"\bpo\s+number\s+([0-9]{1,6})\b", normalized, re.IGNORECASE)
                if order_match is not None:
                    matches["ordine"] = _build_match(page.id, line, order_match.group(1))
            if "diametro" not in matches:
                diameter_match = re.search(r"\bextruded\s+round\s+bar\s+([0-9]+(?:[.,][0-9]+)?)\b", lowered)
                if diameter_match is not None:
                    matches["diametro"] = _build_match(page.id, line, _normalize_decimal_value(diameter_match.group(1)))
            heat_matches = re.findall(r"\b\d{2}[A-Z]-\d{4}\b", normalized, re.IGNORECASE)
            for token in heat_matches:
                heat_candidates.add(token.upper())
    if "colata" not in matches and len(heat_candidates) == 1:
        token = next(iter(heat_candidates))
        page = pages[0]
        matches["colata"] = _build_match(page.id, token, token)
    return matches


def _detect_impol_ddt_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    lines: list[str] = []
    first_page_id = pages[0].id if pages else 0
    for page in pages:
        page_lines = _page_lines(page)
        lines.extend(page_lines)
        for line in page_lines:
            normalized = _normalize_mojibake_numeric_text(line).upper()
            if "ddt" in matches:
                continue
            match = re.search(r"\bPACKING\s+LIST(?:[\s_]+)?(\d{1,6})\s*[-/]\s*(\d{1,2})\b", normalized)
            if match is not None:
                document_number = f"{int(match.group(1))}-{int(match.group(2))}"
                matches["ddt"] = _build_match(page.id, line, document_number)
    impol_fields = _extract_impol_match_fields(lines, document_type="ddt")
    if "ordine" not in matches and impol_fields.get("customer_order_no"):
        snippet = _find_impol_field_snippet(lines, "ordine", impol_fields["customer_order_no"])
        matches["ordine"] = _build_match(first_page_id, snippet, impol_fields["customer_order_no"])
    if "colata" not in matches and impol_fields.get("charge"):
        snippet = _find_impol_field_snippet(lines, "colata", impol_fields["charge"])
        matches["colata"] = _build_match(first_page_id, snippet, impol_fields["charge"])
    if "diametro" not in matches and impol_fields.get("diameter"):
        snippet = _find_impol_field_snippet(lines, "diametro", impol_fields["diameter"])
        matches["diametro"] = _build_match(first_page_id, snippet, impol_fields["diameter"])
    if "peso" not in matches and impol_fields.get("net_weight"):
        snippet = _find_impol_field_snippet(lines, "peso", impol_fields["net_weight"])
        matches["peso"] = _build_match(first_page_id, snippet, impol_fields["net_weight"])
    return matches


def _find_impol_field_snippet(lines: list[str], field_name: str, value: str) -> str:
    normalized_value = _normalize_mojibake_numeric_text(value).upper()
    for line in lines:
        normalized_line = _normalize_mojibake_numeric_text(line).upper()
        if field_name == "diametro" and "DIA" in normalized_line and normalized_value in normalized_line:
            return line
        if field_name == "peso" and "POS. TOTAL" in normalized_line:
            return line
        if field_name == "colata" and normalized_value in normalized_line:
            return line
        if field_name == "ordine" and normalized_value in normalized_line:
            return line
    return value


def merge_row_supplier_fields(
    document_fields: dict[str, str | None],
    row_fields: dict[str, str | None],
) -> dict[str, str | None]:
    merged = dict(document_fields)
    for field_name, field_value in row_fields.items():
        normalized_value = _string_or_none(field_value)
        if normalized_value is not None:
            merged[field_name] = normalized_value
    return merged


def detect_certificate_core_matches(
    pages: list[DocumentPage],
    *,
    supplier_key: str | None = None,
) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    supplier_detector = {
        "aluminium_bozen": _detect_aluminium_bozen_certificate_core_matches,
    }.get(supplier_key)
    if supplier_detector is not None:
        matches.update(supplier_detector(pages))

    for page in pages:
        lines = [line.strip() for line in _best_page_text(page).splitlines() if line.strip()]
        if "numero_certificato_certificato" not in matches:
            cert_payload = _extract_certificate_number_payload(lines, page.id)
            if cert_payload is not None:
                matches["numero_certificato_certificato"] = cert_payload
        if "colata_certificato" not in matches:
            cast_payload = _extract_certificate_cast_payload(lines, page.id)
            if cast_payload is not None:
                matches["colata_certificato"] = cast_payload
        if "peso_certificato" not in matches:
            weight_payload = _extract_certificate_weight_payload(lines, page.id)
            if weight_payload is not None:
                matches["peso_certificato"] = weight_payload
    return matches


def _detect_aluminium_bozen_certificate_core_matches(
    pages: list[DocumentPage],
) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
    for page in pages:
        lines = _page_lines(page)
        normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

        if "numero_certificato_certificato" not in matches:
            certificate_number = _extract_aluminium_bozen_certificate_number(lines, normalized_lines)
            if certificate_number is not None:
                matches["numero_certificato_certificato"] = _build_match(page.id, certificate_number[0], certificate_number[1])

        if "articolo_certificato" not in matches:
            article = _extract_value_near_anchor(lines, ("article",), pattern=r"\b14BT[0-9A-Z-]+\b")
            if article is not None:
                matches["articolo_certificato"] = _build_match(page.id, f"ARTICLE | {article}", article)

        if "codice_cliente_certificato" not in matches:
            customer_code = _extract_aluminium_bozen_customer_code(lines)
            if customer_code is not None:
                matches["codice_cliente_certificato"] = _build_match(page.id, customer_code, customer_code)

        if "ordine_cliente_certificato" not in matches:
            customer_order = _extract_aluminium_bozen_customer_order(lines, document_type="certificato")
            if customer_order is not None:
                snippet = _find_line_containing_token(lines, "CUSTOMER") or customer_order
                matches["ordine_cliente_certificato"] = _build_match(page.id, snippet, customer_order)

        if "lega_certificato" not in matches:
            alloy_payload = _extract_aluminium_bozen_certificate_alloy(lines, normalized_lines)
            if alloy_payload is not None:
                matches["lega_certificato"] = _build_match(page.id, alloy_payload[0], alloy_payload[1])

        if "diametro_certificato" not in matches:
            diameter_payload = _extract_aluminium_bozen_certificate_diameter(lines, normalized_lines)
            if diameter_payload is not None:
                matches["diametro_certificato"] = _build_match(page.id, diameter_payload[0], diameter_payload[1])

        if "colata_certificato" not in matches:
            cast_payload = _extract_aluminium_bozen_certificate_cast(lines, normalized_lines)
            if cast_payload is not None:
                matches["colata_certificato"] = _build_match(page.id, cast_payload[0], cast_payload[1])

        if "peso_certificato" not in matches:
            weight_payload = _extract_aluminium_bozen_certificate_weight(lines, normalized_lines)
            if weight_payload is not None:
                matches["peso_certificato"] = _build_match(page.id, weight_payload[0], weight_payload[1])

    return matches


def normalize_impol_packing_list_root(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\b(\d{1,6})\s*[-/]\s*\d{1,2}\b", cleaned)
    if match is not None:
        return str(int(match.group(1)))
    match = re.search(r"\b(\d{1,6})\b", cleaned)
    if match is not None:
        return str(int(match.group(1)))
    return None


def extract_row_supplier_match_fields(
    *,
    row: AcquisitionRow,
    ddt_values: dict[str, str | None],
    supplier_key: str | None,
) -> dict[str, str | None]:
    if supplier_key == "grupa_kety":
        return {
            "delivery_note_no": _string_or_none(row.ddt),
            "lot_number": _string_or_none(ddt_values.get("lot_batch_no")),
            "order_no": _string_or_none(row.ordine) or _string_or_none(ddt_values.get("ordine")),
            "heat": _string_or_none(ddt_values.get("heat_no")),
            "customer_part_number": _string_or_none(ddt_values.get("product_code")),
        }

    if supplier_key == "impol":
        return {
            "packing_list_no": normalize_impol_packing_list_root(row.ddt) or _string_or_none(ddt_values.get("ddt")),
            "customer_order_no": _string_or_none(row.ordine) or _string_or_none(ddt_values.get("ordine")),
            "supplier_order_no": _string_or_none(ddt_values.get("supplier_order_no")),
            "product_code": _string_or_none(ddt_values.get("product_code")),
            "charge": _string_or_none(row.colata) or _string_or_none(ddt_values.get("colata")),
            "diameter": _string_or_none(row.diametro) or _string_or_none(ddt_values.get("diametro")),
            "net_weight": _string_or_none(row.peso) or _string_or_none(ddt_values.get("peso")),
        }

    if supplier_key == "aluminium_bozen":
        return {
            "article": _string_or_none(ddt_values.get("article_code")),
            "customer_code": _string_or_none(ddt_values.get("customer_code")),
            "customer_order_normalized": _string_or_none(ddt_values.get("customer_order_no")),
        }

    return {}


def score_supplier_field_matches(
    *,
    supplier_key: str | None,
    row: AcquisitionRow,
    ddt_supplier_fields: dict[str, str | None],
    certificate_supplier_fields: dict[str, str | None],
) -> list[tuple[int, str]]:
    reasons: list[tuple[int, str]] = []

    def add_reason(points: int, label: str) -> None:
        reasons.append((points, label))

    if supplier_key == "metalba":
        if same_token(ddt_supplier_fields.get("vs_rif"), certificate_supplier_fields.get("ordine_cliente")):
            add_reason(95, "Vs. Rif. / Ordine Cliente coerenti")
        if same_token(ddt_supplier_fields.get("rif_ord_root"), certificate_supplier_fields.get("commessa_root")):
            add_reason(110, "Rif. Ord. / Commessa coerenti")
    elif supplier_key == "aww":
        if same_token(ddt_supplier_fields.get("your_part_number"), certificate_supplier_fields.get("kunden_teile_nr")):
            add_reason(110, "Your part number coerente")
        if same_token(ddt_supplier_fields.get("part_number"), certificate_supplier_fields.get("artikel_nr")):
            add_reason(100, "Part number / Artikel-Nr. coerenti")
        if same_token(ddt_supplier_fields.get("order_confirmation_root"), certificate_supplier_fields.get("auftragsbestaetigung_root")):
            add_reason(95, "Order confirmation root coerente")
    elif supplier_key == "aluminium_bozen":
        if same_token(ddt_supplier_fields.get("article"), certificate_supplier_fields.get("article")):
            add_reason(100, "Article coerente")
        if same_token(ddt_supplier_fields.get("customer_code"), certificate_supplier_fields.get("customer_code")):
            add_reason(100, "Codice cliente coerente")
        if same_token(ddt_supplier_fields.get("customer_order_normalized"), certificate_supplier_fields.get("customer_order_normalized")):
            add_reason(45, "Ordine cliente normalizzato coerente")
    elif supplier_key == "zalco":
        if same_token(ddt_supplier_fields.get("tally_sheet_no"), certificate_supplier_fields.get("tally_sheet_no")):
            add_reason(120, "Tally sheet coerente")
        if same_token(ddt_supplier_fields.get("cast_no"), certificate_supplier_fields.get("cast_no")):
            add_reason(85, "Cast coerente")
        if same_token(ddt_supplier_fields.get("symbol"), certificate_supplier_fields.get("symbol")):
            add_reason(85, "Symbole coerente")
        if same_token(ddt_supplier_fields.get("code_art"), certificate_supplier_fields.get("code_art")):
            add_reason(85, "Code art coerente")
    elif supplier_key == "arconic_hannover":
        if same_token(ddt_supplier_fields.get("delivery_note_no"), certificate_supplier_fields.get("delivery_note_no")):
            add_reason(120, "Delivery note coerente")
        if same_token(ddt_supplier_fields.get("sales_order_number"), certificate_supplier_fields.get("sales_order_number")):
            add_reason(95, "Sales order coerente")
        if same_token(ddt_supplier_fields.get("customer_po"), certificate_supplier_fields.get("customer_po")):
            add_reason(95, "Customer P/O coerente")
        if same_token(ddt_supplier_fields.get("arconic_item_number"), certificate_supplier_fields.get("arconic_item_number")):
            add_reason(100, "Arconic item coerente")
        if same_token(ddt_supplier_fields.get("cast_job_number"), certificate_supplier_fields.get("cast_job_number")):
            add_reason(110, "Cast/Job coerente")
    elif supplier_key == "neuman":
        if same_token(ddt_supplier_fields.get("delivery_note_no"), certificate_supplier_fields.get("delivery_note_no")):
            add_reason(120, "Delivery note coerente")
        if same_token(ddt_supplier_fields.get("lot_number"), certificate_supplier_fields.get("lot_number")):
            add_reason(110, "Lot coerente")
        if same_token(ddt_supplier_fields.get("customer_material_number"), certificate_supplier_fields.get("customer_material_number")):
            add_reason(110, "Customer material number coerente")
        if same_token(ddt_supplier_fields.get("customer_order_number"), certificate_supplier_fields.get("customer_order_number")):
            add_reason(80, "Customer order number coerente")
    elif supplier_key == "grupa_kety":
        if same_token(ddt_supplier_fields.get("delivery_note_no"), certificate_supplier_fields.get("delivery_note_no")):
            add_reason(120, "Delivery note coerente")
        if same_token(ddt_supplier_fields.get("lot_number"), certificate_supplier_fields.get("lot_number")):
            add_reason(120, "Lot coerente")
        if same_token(ddt_supplier_fields.get("order_no"), certificate_supplier_fields.get("order_no")):
            add_reason(90, "Order no coerente")
        if same_token(ddt_supplier_fields.get("heat"), certificate_supplier_fields.get("heat")):
            add_reason(100, "Heat coerente")
        if same_token(ddt_supplier_fields.get("customer_part_number"), certificate_supplier_fields.get("customer_part_number")):
            add_reason(90, "Customer part coerente")
    elif supplier_key == "impol":
        row_packing_list_root = normalize_impol_packing_list_root(row.ddt) or ddt_supplier_fields.get("packing_list_no")
        if same_token(row_packing_list_root, certificate_supplier_fields.get("packing_list_no")):
            add_reason(120, "Packing list coerente")
        if same_token(row.ordine, certificate_supplier_fields.get("customer_order_no")):
            add_reason(100, "Customer order coerente")
        elif same_token(ddt_supplier_fields.get("customer_order_no"), certificate_supplier_fields.get("customer_order_no")):
            add_reason(100, "Customer order coerente")
        if same_token(ddt_supplier_fields.get("supplier_order_no"), certificate_supplier_fields.get("supplier_order_no")):
            add_reason(95, "Supplier order coerente")
        if same_token(ddt_supplier_fields.get("product_code"), certificate_supplier_fields.get("product_code")):
            add_reason(100, "Product code coerente")
        if same_token(row.colata, certificate_supplier_fields.get("charge")):
            add_reason(110, "Charge coerente")
        elif same_token(ddt_supplier_fields.get("charge"), certificate_supplier_fields.get("charge")):
            add_reason(110, "Charge coerente")

    return reasons


def normalize_match_token(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
    return normalized or None


def same_token(left: str | None, right: str | None) -> bool:
    return normalize_match_token(left) is not None and normalize_match_token(left) == normalize_match_token(right)


def weights_are_compatible(row_weight: str | None, certificate_weight: str | None) -> bool:
    left = _parse_weight_number(row_weight)
    right = _parse_weight_number(certificate_weight)
    if left is None or right is None:
        return False
    tolerance = max(0.02, max(abs(left), abs(right)) * 0.02)
    return abs(left - right) <= tolerance


def document_contains_token(pages: list[DocumentPage], token: str | None) -> bool:
    cleaned_token = normalize_match_token(token)
    if cleaned_token is None:
        return False
    for page in pages:
        haystack = normalize_match_token(_best_page_text(page))
        if haystack and cleaned_token in haystack:
            return True
    return False


def _parse_weight_number(value: str | None) -> float | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", cleaned.replace(" ", ""))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _extract_certificate_number(line: str) -> str | None:
    pattern = re.compile(r"(?:cert(?:ificate)?|cdq)[^\w]{0,6}(?:n|no|nr|n°)?[^\w]{0,6}([a-z0-9][a-z0-9/-]{2,})")
    match = pattern.search(line)
    if match is None:
        return None
    return match.group(1).upper()


def _extract_certificate_number_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    tally_sheet_payload = _extract_tally_sheet_number_payload(lines, page_id)
    if tally_sheet_payload is not None:
        return tally_sheet_payload

    anchored_patterns = (
        r"\bCERT\.?\s*NO\.?\s*([0-9]{4,}[A-Z]?)\b",
        r"\bNO\.?\s*CERT\.?\s*([0-9]{4,}[A-Z]?)\b",
        r"\bNR\.?\s*CERT\.?\s*([0-9]{4,}[A-Z]?)\b",
        r"\bCDQ\b[^\dA-Z]{0,6}([0-9]{4,}[A-Z]?)\b",
    )
    for line in lines:
        normalized_line = _normalize_mojibake_numeric_text(line).upper()
        for pattern in anchored_patterns:
            match = re.search(pattern, normalized_line)
            if match is not None:
                value = match.group(1)
                if value not in {"10204", "0000"}:
                    return {"page_id": page_id, "snippet": line, "standardized": value, "final": value}

    direct = _extract_anchor_value_from_lines(
        lines,
        anchors=(
            "cert.no",
            "cert no",
            "n°.cert",
            "n° cert",
            "nr.cert",
            "nr cert",
            "no.cert",
            "no cert",
            "cdq",
        ),
        pattern=r"\b[0-9]{4,}[A-Z]?\b",
        exclude_tokens={"10204", "31", "3", "1"},
        lookahead=12,
    )
    if direct is not None:
        snippet, value = direct
        return {"page_id": page_id, "snippet": snippet, "standardized": value, "final": value}

    for line in lines:
        normalized_line = line.lower()
        cert_number = _extract_certificate_number(normalized_line)
        if (
            cert_number is not None
            and cert_number not in {"IFICATE", "CERTIFICATE"}
            and any(char.isdigit() for char in cert_number)
        ):
            return {"page_id": page_id, "snippet": line, "standardized": cert_number, "final": cert_number}
    return None


def _extract_certificate_cast_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    explicit_cast = _extract_explicit_cast_number_payload(lines, page_id)
    if explicit_cast is not None:
        return explicit_cast

    extracted = _extract_anchor_value_from_lines(
        lines,
        anchors=("charge/ cast no", "charge/cast no", "cast no", "cast nr", "cast batch nr", "cast batch no", "heat no", "colata", "batch no", "batch nr", "coulee"),
        pattern=r"\b[A-Z0-9]{4,}[A-Z]?\b",
        exclude_tokens={"CHARGE", "CAST", "BATCH", "HEAT", "NO", "COULEE"},
        lookahead=4,
    )
    if extracted is None:
        return None
    snippet, value = extracted
    if value.upper() in {"COLATA", "CHARGE", "CAST", "BATCH"}:
        return None
    if not any(char.isdigit() for char in value):
        return None
    return {"page_id": page_id, "snippet": snippet, "standardized": value, "final": value}


def _extract_certificate_weight_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    weight_patterns = (
        r"(?:gewicht|weight)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*kg",
        r"(?:peso netto|net weight)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*kg",
        r"(?:poids net|netto)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*kg",
    )
    for line in lines:
        lowered = line.casefold()
        if (
            "weight" not in lowered
            and "peso netto" not in lowered
            and "net weight" not in lowered
            and "gewicht" not in lowered
            and "poids net" not in lowered
        ):
            continue
        for pattern in weight_patterns:
            weight_match = re.search(pattern, lowered)
            if weight_match is not None:
                value = _normalize_weight(weight_match.group(1))
                return {"page_id": page_id, "snippet": line, "standardized": value, "final": value}
    return None


def _extract_anchor_value_from_lines(
    lines: list[str],
    *,
    anchors: tuple[str, ...],
    pattern: str,
    exclude_tokens: set[str] | None = None,
    lookahead: int = 4,
) -> tuple[str, str] | None:
    compiled = re.compile(pattern, re.IGNORECASE)
    excluded = {token.upper() for token in (exclude_tokens or set())}

    def _first_candidate(value_line: str) -> str | None:
        for match in compiled.finditer(value_line):
            token = match.group(0).strip().upper()
            if token in excluded:
                continue
            return token
        return None

    for index, line in enumerate(lines):
        lowered = line.casefold()
        if not any(anchor in lowered for anchor in anchors):
            continue

        same_line = _first_candidate(line)
        if same_line is not None:
            return line, same_line

        for candidate in lines[index + 1 : min(index + 1 + lookahead, len(lines))]:
            extracted = _first_candidate(candidate)
            if extracted is not None:
                return f"{line} | {candidate}", extracted
    return None


def _extract_tally_sheet_number_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if "tally sheet" not in lowered and "no. avis" not in lowered and "no. ais" not in lowered:
            continue

        same_line_match = re.search(r"\b(0{0,4}\d{5})\b", line)
        if same_line_match is not None:
            value = str(int(same_line_match.group(1)))
            return {"page_id": page_id, "snippet": line, "standardized": value, "final": value}

        for candidate in lines[index + 1 : min(index + 5, len(lines))]:
            candidate_match = re.search(r"\b(0{0,4}\d{5})\b", candidate)
            if candidate_match is not None:
                value = str(int(candidate_match.group(1)))
                return {"page_id": page_id, "snippet": f"{line} | {candidate}", "standardized": value, "final": value}
    return None


def _extract_explicit_cast_number_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if "cast nr" not in lowered and "cast no" not in lowered and "coulee" not in lowered and "colata" not in lowered:
            continue

        same_line_match = re.search(r"\b(\d{5,}[A-Z]?)\b", line.upper())
        if same_line_match is not None:
            value = same_line_match.group(1)
            return {"page_id": page_id, "snippet": line, "standardized": value, "final": value}

        for candidate in lines[index + 1 : min(index + 5, len(lines))]:
            candidate_match = re.search(r"^\s*(?:\d{4}\s+)?(\d{5,}[A-Z]?)\b", candidate.upper())
            if candidate_match is not None:
                value = candidate_match.group(1)
                return {"page_id": page_id, "snippet": f"{line} | {candidate}", "standardized": value, "final": value}
    return None


def _extract_value_near_anchor(
    lines: list[str],
    anchors: tuple[str, ...],
    *,
    pattern: str | None = None,
) -> str | None:
    compiled = re.compile(pattern) if pattern else None
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if not any(anchor in lowered for anchor in anchors):
            continue

        same_line_candidate = line
        if compiled is not None:
            match = compiled.search(same_line_candidate)
            if match is not None:
                return match.group(0).strip()
        else:
            extracted = _extract_last_code_token(same_line_candidate)
            if extracted is not None:
                return extracted

        for candidate in lines[index + 1 : min(index + 4, len(lines))]:
            if compiled is not None:
                match = compiled.search(candidate)
                if match is not None:
                    return match.group(0).strip()
            else:
                extracted = _extract_last_code_token(candidate)
                if extracted is not None:
                    return extracted
    return None


def _extract_last_code_token(line: str) -> str | None:
    tokens = re.findall(r"[A-Z0-9][A-Z0-9./-]{2,}", _normalize_mojibake_numeric_text(line).upper())
    for token in reversed(tokens):
        if token not in {"COMMESSA", "ORDINE", "CLIENTE", "CUSTOMER", "PART", "NUMBER", "RIF", "VS"}:
            return token
    return None


def _normalize_commessa_root(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.match(r"(\d+/\d+)", cleaned)
    if match is not None:
        return match.group(1)
    return cleaned.split("/", 1)[0]


def _normalize_order_confirmation_root(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    match = re.search(r"\d{6,}", cleaned)
    if match is None:
        return None
    return match.group(0)


def _extract_code_pattern(lines: list[str], pattern: str) -> str | None:
    compiled = re.compile(pattern)
    for line in lines:
        match = compiled.search(line.upper())
        if match is not None:
            return match.group(0)
    return None


def _extract_aluminium_bozen_customer_code(lines: list[str]) -> str | None:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line).upper()
        match = re.search(r"\bA\d[0-9A-Z]{4,}\b", normalized)
        if match is not None:
            return _normalize_aluminium_bozen_customer_code(match.group(0))
    return None


def _extract_aluminium_bozen_customer_order(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            if "VS. ODV" not in line and "VS ODV" not in line and "RIF. ORDINE CLIENTE" not in line:
                continue
            normalized = _normalize_customer_order_tokens(line)
            if normalized is not None and "|" in normalized:
                return normalized
        return None

    for index, line in enumerate(normalized_lines):
        if "CUSTOMER" in line and "ORDER" in line:
            for candidate in normalized_lines[index + 1 : min(index + 5, len(normalized_lines))]:
                normalized = _normalize_customer_order_tokens(candidate)
                if normalized is not None and "|" in normalized:
                    return normalized

    for line in normalized_lines:
        normalized = _normalize_customer_order_tokens(line)
        if normalized is not None and "|" in normalized:
            return normalized
    return None


def _extract_aluminium_bozen_certificate_number(
    lines: list[str],
    normalized_lines: list[str],
) -> tuple[str, str] | None:
    for index, line in enumerate(normalized_lines):
        if "CERT.NO" not in line and "CERT NO" not in line and "CERTNC" not in line:
            continue
        window = normalized_lines[index : min(index + 4, len(normalized_lines))]
        raw_window = lines[index : min(index + 4, len(lines))]
        previous_four_digit_token: str | None = None
        for offset, (raw_candidate, candidate) in enumerate(zip(raw_window, window, strict=False)):
            for source in (raw_candidate.upper(), candidate):
                for token in re.findall(r"\b\d{5,7}[A-Z]?\b", source):
                    if token in {"10204"}:
                        continue
                    if re.fullmatch(r"20\d{2}", token):
                        continue
                    return " | ".join(raw_window[: offset + 1]), token
                for token in re.findall(r"\b\d{4}\b", source):
                    if re.fullmatch(r"20\d{2}", token):
                        continue
                    if previous_four_digit_token is not None and token.startswith(previous_four_digit_token[1:]):
                        return " | ".join(raw_window[: offset + 1]), f"{previous_four_digit_token[0]}{token}"
                    previous_four_digit_token = token
    return None


def _normalize_aluminium_bozen_customer_code(value: str) -> str:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return value
    token = cleaned.upper()
    if not token.startswith("A"):
        return token
    normalized_chars = [token[0]]
    for char in token[1:]:
        if char in {"O", "Q", "D"}:
            normalized_chars.append("0")
        elif char == "I":
            normalized_chars.append("1")
        else:
            normalized_chars.append(char)
    return "".join(normalized_chars)


def _extract_aluminium_bozen_certificate_alloy(
    lines: list[str],
    normalized_lines: list[str],
) -> tuple[str, str] | None:
    for index, line in enumerate(normalized_lines):
        if (
            "ALLOY" not in line
            and "PHYS.STATE" not in line
            and "SECTION DESC" not in line
            and "DESCRIZIONE PROFILO CLIENTE" not in line
            and "LEGIERUNG" not in line
        ):
            continue
        window = [line, *normalized_lines[index + 1 : min(index + 12, len(normalized_lines))]]
        raw_window = [lines[index], *lines[index + 1 : min(index + 12, len(lines))]]
        for offset, candidate in enumerate(window):
            match = re.search(r"\b([1-9][0-9]{3}[A-Z]{0,3})\s+(HF\s*/\s*F|H\s*/\s*F|G\s*/\s*F|GF|HF|F|T\d+[A-Z0-9/-]*)\b", candidate)
            if match is not None:
                value = f"{match.group(1)} {match.group(2).replace(' / ', ' ').replace('/', ' ')}"
                value = re.sub(r"\s+", " ", value).strip()
                snippet = " | ".join(raw_window[: offset + 1])
                return snippet, value
    return None


def _extract_aluminium_bozen_certificate_diameter(
    lines: list[str],
    normalized_lines: list[str],
) -> tuple[str, str] | None:
    def _normalize_diameter_candidate(raw_value: str) -> str | None:
        normalized = _normalize_decimal_value(raw_value)
        if normalized is None:
            return None
        try:
            numeric_value = float(normalized.replace(",", "."))
        except ValueError:
            return None
        if not 0 < numeric_value <= 400:
            return None
        return normalized

    for index, line in enumerate(normalized_lines):
        if "PROFIL CLIENT" in line or "SECTION DESC" in line:
            same_line_profile_match = re.search(r"\bBARRA\s+TONDA\s+([0-9]{2,3}(?:[.,][0-9]+)?)\b", line)
            if same_line_profile_match is not None:
                normalized = _normalize_diameter_candidate(same_line_profile_match.group(1))
                if normalized is not None:
                    return lines[index], normalized
            same_line = re.search(r"\b([0-9]{2,3}(?:[.,][0-9]+)?)\b", line)
            if same_line is not None:
                normalized = _normalize_diameter_candidate(same_line.group(1))
                if normalized is not None:
                    return lines[index], normalized
            for offset, candidate in enumerate(normalized_lines[index + 1 : min(index + 12, len(normalized_lines))], start=1):
                profile_match = re.search(r"\bBARRA\s+TONDA\s+([0-9]{2,3}(?:[.,][0-9]+)?)\b", candidate)
                if profile_match is not None:
                    normalized = _normalize_diameter_candidate(profile_match.group(1))
                    if normalized is not None:
                        return f"{lines[index]} | {lines[index + offset]}", normalized
                profile_nr_match = re.search(r"\b([0-9]{2,3}(?:[.,][0-9]+)?)\s+LEGIERUNG\b", candidate)
                if profile_nr_match is not None:
                    normalized = _normalize_diameter_candidate(profile_nr_match.group(1))
                    if normalized is not None:
                        return f"{lines[index]} | {lines[index + offset]}", normalized
                isolated_match = re.fullmatch(r"\s*([0-9]{2,3}(?:[.,][0-9]+)?)\s*", candidate)
                if isolated_match is not None:
                    normalized = _normalize_diameter_candidate(isolated_match.group(1))
                    if normalized is not None:
                        return f"{lines[index]} | {lines[index + offset]}", normalized

    for index, line in enumerate(normalized_lines):
        customer_code_match = re.search(r"\bA\d[0-9A-Z]{4,}\b", line)
        if customer_code_match is None:
            continue
        for offset, candidate in enumerate(normalized_lines[index : min(index + 5, len(normalized_lines))]):
            isolated_match = re.fullmatch(r"\s*([0-9]{2,3}(?:[.,][0-9]+)?)\s*", candidate)
            if isolated_match is not None:
                normalized = _normalize_diameter_candidate(isolated_match.group(1))
                if normalized is not None:
                    raw_snippet = lines[index]
                    if offset:
                        raw_snippet = f"{lines[index]} | {lines[index + offset]}"
                    return raw_snippet, normalized
    return None


def _extract_aluminium_bozen_certificate_cast(
    lines: list[str],
    normalized_lines: list[str],
) -> tuple[str, str] | None:
    def _extract_cast_candidate(source: str) -> str | None:
        for pattern in (
            r"\b([A-Z]\d{5,}[A-Z]?)\b",
            r"\b(\d{5,}[A-Z]\d)\b",
            r"\b(\d{5,}[A-Z])\b",
            r"\b(\d{5,})\b",
        ):
            match = re.search(pattern, source.upper())
            if match is not None:
                token = match.group(1).strip().upper()
                return token
        return None

    for index, line in enumerate(normalized_lines):
        if "CAST BATCH" not in line and "CHARGE" not in line and "COLATA" not in line:
            continue
        same_line_raw = _extract_cast_candidate(lines[index])
        if same_line_raw is not None:
            return lines[index], same_line_raw
        same_line = _extract_cast_candidate(line)
        if same_line is not None:
            return lines[index], same_line
        for offset, candidate in enumerate(normalized_lines[index + 1 : min(index + 8, len(normalized_lines))], start=1):
            raw_candidate = lines[index + offset]
            candidate_match = _extract_cast_candidate(raw_candidate) or _extract_cast_candidate(candidate)
            if candidate_match is not None:
                return f"{lines[index]} | {lines[index + offset]}", candidate_match
    return None


def _extract_aluminium_bozen_certificate_weight(
    lines: list[str],
    normalized_lines: list[str],
) -> tuple[str, str] | None:
    for index, line in enumerate(normalized_lines):
        if "NET WEIGHT" not in line and "NETGEWICHT" not in line and "POIDS NET" not in line:
            continue
        same_line = re.search(r"\b([0-9]{1,3}(?:[.,][0-9]{3})|[0-9]+[.,][0-9]{3})\b", line)
        if same_line is not None:
            normalized = _normalize_weight(same_line.group(1))
            if normalized is not None:
                return lines[index], normalized
        for offset, candidate in enumerate(normalized_lines[index + 1 : min(index + 4, len(normalized_lines))], start=1):
            candidate_match = re.search(r"\b([0-9]{1,3}(?:[.,][0-9]{3})|[0-9]+[.,][0-9]{3})\b", candidate)
            if candidate_match is not None:
                normalized = _normalize_weight(candidate_match.group(1))
                if normalized is not None:
                    return f"{lines[index]} | {lines[index + offset]}", normalized
    return None


def _find_line_containing_token(lines: list[str], token: str) -> str | None:
    normalized_token = token.upper()
    for line in lines:
        if normalized_token in _normalize_mojibake_numeric_text(line).upper():
            return line
    return None


def _extract_zalco_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "tally_sheet_no": _extract_zalco_tally_sheet_number(lines, document_type=document_type),
        "cast_no": _extract_zalco_cast_number(lines),
        "symbol": _extract_zalco_symbol(lines),
        "code_art": _extract_zalco_code_art(lines),
    }


def _extract_zalco_tally_sheet_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bORDER\b.*?\b\d{8}\b.*?\b(0{0,4}\d{5})\b", line)
            if match is not None:
                return str(int(match.group(1)))

    for index, line in enumerate(normalized_lines):
        if "TALLY SHEET" not in line and "NO. AVIS" not in line and "NO. AIS" not in line:
            continue
        match = re.search(r"\b(0{0,4}\d{5})\b", line)
        if match is not None:
            return str(int(match.group(1)))
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"\b(0{0,4}\d{5})\b", candidate)
            if candidate_match is not None:
                return str(int(candidate_match.group(1)))
    return None


def _extract_zalco_cast_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for index, line in enumerate(normalized_lines):
        if "CAST NR" not in line and "COULEE" not in line:
            continue
        match = re.search(r"\b(\d{5})\b", line)
        if match is not None:
            return match.group(1)
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"^\s*(?:\d{4}\s+)?(\d{5})\b", candidate)
            if candidate_match is not None:
                return candidate_match.group(1)
    return None


def _extract_zalco_symbol(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for index, line in enumerate(normalized_lines):
        if "SYMBOLE" in line:
            same_line_match = re.search(r"\bSYMBOLE\s+([0-9]{5,})\b", line)
            if same_line_match is not None:
                return same_line_match.group(1)
            for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
                candidate_match = re.search(r"\b([0-9]{5,})\b", candidate)
                if candidate_match is not None:
                    return candidate_match.group(1)

    for index, line in enumerate(normalized_lines):
        if "CUSTOMER ALLOY CODE" not in line:
            continue
        for candidate in normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]:
            candidate_match = re.search(r"\b([0-9]{5,})\b", candidate)
            if candidate_match is not None:
                return candidate_match.group(1)
    return None


def _extract_zalco_code_art(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        match = re.search(r"\bCO(?:DE|PE)(?:\s+ART)?\s*:?\s*([0-9]{4,})\b", line)
        if match is not None:
            return match.group(1)
    return None


def _extract_arconic_hannover_match_fields(lines: list[str]) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_arconic_delivery_note(lines),
        "sales_order_number": _extract_value_near_anchor(lines, ("sales order number",), pattern=r"\b\d{6,}\b"),
        "customer_po": _extract_value_near_anchor(lines, ("customer purchase order", "customer p/o"), pattern=r"\b[0-9][0-9A-Z/-]{1,}\b"),
        "arconic_item_number": _extract_value_near_anchor(lines, ("arconic item number", "item no."), pattern=r"\bBG[0-9A-Z]+\b"),
        "cast_job_number": _extract_arconic_cast_job_number(lines),
    }


def _extract_arconic_delivery_note(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(
            r"\bdelivery\s+note(?:\s+no\.?)?\s+(\d{6,})\b",
            _normalize_mojibake_numeric_text(line),
            re.IGNORECASE,
        )
        if match is not None:
            return match.group(1)
    return None


def _extract_arconic_cast_job_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    for index, line in enumerate(normalized_lines):
        if "CAST/JOB NUMBER" in line:
            window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
            normalized = _normalize_arconic_cast_job_tokens(window)
            if normalized is not None:
                return normalized

    for line in normalized_lines:
        if "CAST NUMBER" in line or "PACKAGE" in line or "LINE TOTAL" in line:
            normalized = _normalize_arconic_cast_job_tokens([line])
            if normalized is not None:
                return normalized

    for line in normalized_lines:
        normalized = _normalize_arconic_cast_job_tokens([line])
        if normalized is not None and "|" in normalized:
            return normalized
    return None


def _normalize_arconic_cast_job_tokens(lines: list[str]) -> str | None:
    cast_token: str | None = None
    job_token: str | None = None
    for line in lines:
        if cast_token is None:
            cast_match = re.search(r"\b(C\d{9,})\b", line)
            if cast_match is not None:
                cast_token = cast_match.group(1)
        if job_token is None:
            job_match = re.search(r"\b(\d{8})\b", line)
            if job_match is not None:
                job_token = job_match.group(1)
    if cast_token and job_token:
        return f"{cast_token}|{job_token}"
    return cast_token or job_token


def _extract_neuman_match_fields(lines: list[str]) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_neuman_delivery_note(lines),
        "lot_number": _extract_neuman_lot_number(lines),
        "customer_material_number": _extract_value_near_anchor(
            lines,
            ("customer material number", "art-nr."),
            pattern=r"\bA[0-9A-Z]{5,}\b",
        ),
        "customer_order_number": _extract_value_near_anchor(
            lines,
            ("customer order number",),
            pattern=r"\b[0-9]{1,6}\b",
        ),
    }


def _extract_neuman_delivery_note(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\bdelivery\s+note(?:\s*:)?\s*(\d{6,})\b", _normalize_mojibake_numeric_text(line), re.IGNORECASE)
        if match is not None:
            return match.group(1)
    return None


def _extract_neuman_lot_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    lot_candidates: list[str] = []
    for index, line in enumerate(normalized_lines):
        if "LOT" not in line:
            continue
        lot_candidates.extend(re.findall(r"\b(\d{5})\b", line))
        for candidate in normalized_lines[index + 1 : min(index + 3, len(normalized_lines))]:
            lot_candidates.extend(re.findall(r"\b(\d{5})\b", candidate))
    unique_candidates = sorted(set(lot_candidates))
    if len(unique_candidates) == 1:
        return unique_candidates[0]
    return None


def _extract_grupa_kety_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "delivery_note_no": _extract_grupa_kety_delivery_note(lines, document_type=document_type),
        "lot_number": _extract_grupa_kety_lot_number(lines, document_type=document_type),
        "order_no": _extract_grupa_kety_order_no(lines),
        "heat": _extract_grupa_kety_heat(lines),
        "customer_part_number": _extract_grupa_kety_customer_part_number(lines),
    }


def _extract_impol_match_fields(lines: list[str], *, document_type: str) -> dict[str, str]:
    return {
        "packing_list_no": _extract_impol_packing_list_number(lines, document_type=document_type),
        "customer_order_no": _extract_impol_customer_order_number(lines, document_type=document_type),
        "supplier_order_no": _extract_impol_supplier_order_number(lines, document_type=document_type),
        "product_code": _extract_impol_product_code(lines, document_type=document_type),
        "charge": _extract_impol_charge(lines, document_type=document_type),
        "diameter": _extract_impol_diameter(lines),
        "net_weight": _extract_impol_net_weight(lines, document_type=document_type),
    }


def _extract_impol_packing_list_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bPACKING\s+LIST(?:[\s_]+)?(\d{1,6})\s*[-/]\s*(\d{1,2})\b", line)
            if match is not None:
                return str(int(match.group(1)))

    for line in normalized_lines:
        match = re.search(r"\bPACKING\s+LIST\s+NO\.?\s*:?\s*(\d{1,6})\b", line)
        if match is not None:
            return str(int(match.group(1)))
    return None


def _extract_impol_customer_order_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(lines, ("customer order no.", "customer order no", "customer order"), pattern=r"\b\d{1,6}\b")

    candidates: set[str] = set()
    for line in normalized_lines:
        if "YOUR ORDER NO" in line:
            for token in re.findall(r"\b\d{1,6}\b", line):
                candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_supplier_order_number(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(
            lines,
            ("supplier order no.", "supplier order no", "supplier order"),
            pattern=r"\b\d{3,6}/\d{1,2}\b",
        )

    candidates: set[str] = set()
    for line in normalized_lines:
        if "PRODUCT CODE" in line or "PRODUCT DESCRIPTION" in line or "YOUR ORDER NO" in line:
            continue
        for token in re.findall(r"\b\d{3,6}/\d{1,2}\b", line):
            candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_product_code(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        return _extract_value_near_anchor(
            lines,
            ("impol product code",),
            pattern=r"\b\d{6}\b",
        )

    candidates: set[str] = set()
    for line in normalized_lines:
        if "PRODUCT CODE" in line:
            continue
        for match in re.findall(r"\b(\d{6})/\d\b", line):
            candidates.add(match)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_impol_charge(lines: list[str], *, document_type: str) -> str | None:
    candidates = _collect_impol_charge_candidates(lines, document_type=document_type)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _collect_impol_charge_candidates(lines: list[str], *, document_type: str) -> set[str]:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()

    for line in normalized_lines:
        if "CHEMICAL COMPOSITION" in line or "MECHANICAL PROPERTIES" in line:
            continue

        if document_type == "ddt":
            for match in re.findall(r"\b(\d{6})\s*\(\d+/\d+\)", line):
                candidates.add(match)
            weight_row_match = re.match(
                r"\s*\d+\s+[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?\s+[0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?\s+(\d{6})\b",
                line,
            )
            if weight_row_match is not None:
                candidates.add(weight_row_match.group(1))
        else:
            match = re.match(r"\s*(\d{6})(?:\(\d+/\d+\))?\b", line)
            if match is not None:
                candidates.add(match.group(1))

    return candidates


def _extract_impol_diameter(lines: list[str]) -> str | None:
    candidates = _collect_impol_diameter_candidates(lines)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _collect_impol_diameter_candidates(lines: list[str]) -> set[str]:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()
    for line in normalized_lines:
        for match in re.findall(r"\bDIA\s*([0-9]+(?:[.,][0-9]+)?)\s*[X×]\s*\d+\s*MM\b", line):
            normalized = _normalize_decimal_value(match)
            if normalized is not None:
                candidates.add(normalized)
    return candidates


def _extract_impol_net_weight(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "certificato":
        for line in normalized_lines:
            match = re.search(r"\bNETTO\s*:?\s*([0-9]+(?:[.,][0-9]+)?)\s*KG\b", line)
            if match is not None:
                return _normalize_weight(match.group(1))
        return None

    diameter_candidates = _collect_impol_diameter_candidates(lines)
    charge_candidates = _collect_impol_charge_candidates(lines, document_type=document_type)
    if len(diameter_candidates) > 1 or len(charge_candidates) > 1:
        return None

    candidates: set[str] = set()
    for line in normalized_lines:
        if "POS. TOTAL" not in line:
            continue
        numbers = re.findall(r"([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)", line)
        if not numbers:
            continue
        normalized = _normalize_weight(numbers[-1])
        if normalized is not None:
            candidates.add(normalized)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_delivery_note(lines: list[str], *, document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]

    if document_type == "ddt":
        for line in normalized_lines:
            match = re.search(r"\bDELIVERY\s+NOTE\s*:?\s*(\d{4,})\b", line)
            if match is not None:
                return match.group(1)

    for index, line in enumerate(normalized_lines):
        if "PACKING SLIP" not in line and "LOT" not in line and "DOWOD WYSYLKOWY" not in line:
            continue
        window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
        pair = _extract_grupa_kety_packing_slip_lot_pair(window)
        if pair is not None:
            return pair[0]
    return None


def _extract_grupa_kety_lot_number(lines: list[str], document_type: str) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()

    if document_type == "ddt":
        for line in normalized_lines:
            for token in re.findall(r"\b100\d{5}(?:/\d{2})?\b", line):
                candidates.add(token.split("/", 1)[0])
    else:
        for index, line in enumerate(normalized_lines):
            if "PACKING SLIP" not in line and "LOT" not in line and "DOWOD WYSYLKOWY" not in line:
                continue
            window = [line, *normalized_lines[index + 1 : min(index + 4, len(normalized_lines))]]
            pair = _extract_grupa_kety_packing_slip_lot_pair(window)
            if pair is not None:
                candidates.add(pair[1])
            for candidate in window:
                for token in re.findall(r"\b100\d{5}(?:/\d{2})?\b", candidate):
                    candidates.add(token.split("/", 1)[0])

    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_order_no(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        if "PO NUMBER" in line:
            match = re.search(r"\bPO\s+NUMBER\s+([0-9]{1,6})\b", line)
            if match is not None:
                return match.group(1)
        if "ORDER NO" in line and "SALES ORDER" not in line:
            match = re.search(r"\bORDER\s+NO\s+([0-9]{1,6})\b", line)
            if match is not None:
                return match.group(1)
    for index, line in enumerate(normalized_lines):
        if "ORDER NO" not in line and "NR ZAMOWIENIA KLIENTA" not in line:
            continue
        for candidate in normalized_lines[index + 1 : min(index + 3, len(normalized_lines))]:
            match = re.match(r"\s*([0-9]{1,6})\b", candidate)
            if match is not None:
                return match.group(1)
    return None


def _extract_grupa_kety_heat(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    candidates: set[str] = set()
    for line in normalized_lines:
        for token in re.findall(r"\b\d{2}[A-Z]-\d{4}\b", line):
            candidates.add(token)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_grupa_kety_customer_part_number(lines: list[str]) -> str | None:
    normalized_lines = [_normalize_mojibake_numeric_text(line).upper() for line in lines]
    for line in normalized_lines:
        if "CUSTOMER PART" in line:
            match = re.search(r"\b(PP[0-9A-Z ./:-]+?)\s+PO\s+NUMBER\b", line)
            if match is not None:
                return re.sub(r"\s+", " ", match.group(1).strip())
        if "NR ZAMOWIENIA KLIENTA" in line or "ORDER NO" in line:
            match = re.search(r"\b(PP[0-9A-Z ./:-]+?)\s+E\d{6,}", line)
            if match is not None:
                return re.sub(r"\s+", " ", match.group(1).strip())
    return None


def _extract_grupa_kety_packing_slip_lot_pair(lines: list[str]) -> tuple[str, str] | None:
    for line in lines:
        match = re.search(r"\b(\d{4,6})\s*/\s*(100\d{5})\b", line)
        if match is not None:
            return match.group(1), match.group(2)
    return None


def _normalize_customer_order_tokens(value: str | None) -> str | None:
    cleaned = _string_or_none(value)
    if cleaned is None:
        return None
    cleaned_upper = cleaned.upper()
    leading_date_match = re.search(r"(20\d{2}-\d{2}-\d{2})\D{0,4}(\d{1,4})\b", cleaned_upper)
    if leading_date_match is not None:
        return f"{leading_date_match.group(2)}|{leading_date_match.group(1)}"

    trailing_date_match = re.search(r"\b(\d{1,4})\D{0,4}(20\d{2}-\d{2}-\d{2})", cleaned_upper)
    if trailing_date_match is not None:
        return f"{trailing_date_match.group(1)}|{trailing_date_match.group(2)}"

    tokens = re.findall(r"[A-Z0-9]+", cleaned.upper())
    if not tokens:
        return None
    if re.search(r"20\d{2}-\d{2}-\d{2}", cleaned):
        date_match = re.search(r"20\d{2}-\d{2}-\d{2}", cleaned)
        date_value = date_match.group(0) if date_match else None
        other_tokens = [
            token
            for token in tokens
            if token not in {"VS", "ODV", "RIF", "ORDINE", "CLIENTE", "CUSTOMER", "ORDER", "NO", "N"}
            and token not in set(re.findall(r"\d+", date_value or ""))
        ]
        if date_value:
            prefix = next((token for token in other_tokens if re.fullmatch(r"\d{1,4}", token)), "".join(other_tokens))
            return f"{prefix}|{date_value}" if prefix else date_value
    if len(tokens) >= 4 and re.fullmatch(r"20\d{2}", tokens[1]):
        date_value = f"{tokens[1]}-{tokens[2]}-{tokens[3]}"
        prefix = next((token for token in tokens if re.fullmatch(r"\d{1,4}", token)), tokens[0])
        return f"{prefix}|{date_value}"
    return "".join(tokens)


def _extract_metalba_ddt_reference_values(lines: list[str]) -> tuple[str | None, str | None]:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line.upper())
        if "DDT" not in normalized:
            continue
        tokens = re.findall(r"\d{2}/\d{2,5}", normalized)
        if len(tokens) >= 2:
            return tokens[0], tokens[1]
    return None, None


def _extract_metalba_certificate_reference_values(lines: list[str]) -> tuple[str | None, str | None]:
    for line in lines:
        normalized = _normalize_mojibake_numeric_text(line.upper())
        if "BARRA TONDA" not in normalized and "ESTRUSO" not in normalized:
            continue
        matches = re.findall(r"\d{2}/\d{4}(?:/\d+)?|\d{2}/\d{2}", normalized)
        if len(matches) >= 2:
            commessa = next((value for value in matches if value.count("/") >= 2 or re.fullmatch(r"\d{2}/\d{4}", value)), None)
            ordine_cliente = next((value for value in matches if re.fullmatch(r"\d{2}/\d{2}", value)), None)
            if ordine_cliente or commessa:
                return ordine_cliente, commessa
    return None, None


def _normalize_mojibake_numeric_text(value: str) -> str:
    translation = str.maketrans(
        {
            "ð": "0",
            "ï": "1",
            "î": "2",
            "í": "3",
            "ì": "4",
            "ë": "5",
            "ê": "6",
            "é": "7",
            "è": "8",
            "ç": "9",
            "ò": ".",
            "ô": ",",
            "ó": "-",
        }
    )
    return value.translate(translation)
