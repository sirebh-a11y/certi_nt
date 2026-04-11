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

    if ascii_alnum_count == 0 and extended_latin_count >= 4:
        return True
    if extended_latin_count >= 6 and ascii_alnum_count < 12:
        return True
    if word_count <= 3 and extended_latin_count > ascii_alnum_count:
        return True
    return False


def _best_page_text(page: DocumentPage) -> str:
    pdf_text = _normalize_text(page.testo_estratto)
    ocr_text = _normalize_text(page.ocr_text)
    if ocr_text and _pdf_text_needs_ocr_fallback(pdf_text):
        return ocr_text
    return pdf_text or ocr_text or ""


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


def detect_certificate_core_matches(pages: list[DocumentPage]) -> dict[str, dict[str, str | int]]:
    matches: dict[str, dict[str, str | int]] = {}
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

    return {}


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
        if cert_number is not None and cert_number not in {"IFICATE", "CERTIFICATE"}:
            return {"page_id": page_id, "snippet": line, "standardized": cert_number, "final": cert_number}
    return None


def _extract_certificate_cast_payload(lines: list[str], page_id: int) -> dict[str, str | int] | None:
    explicit_cast = _extract_explicit_cast_number_payload(lines, page_id)
    if explicit_cast is not None:
        return explicit_cast

    extracted = _extract_anchor_value_from_lines(
        lines,
        anchors=("charge/ cast no", "charge/cast no", "cast no", "cast nr", "heat no", "colata", "batch no", "coulee"),
        pattern=r"\b[A-Z0-9]{4,}[A-Z]?\b",
        exclude_tokens={"CHARGE", "CAST", "BATCH", "HEAT", "NO", "COULEE"},
        lookahead=4,
    )
    if extracted is None:
        return None
    snippet, value = extracted
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
