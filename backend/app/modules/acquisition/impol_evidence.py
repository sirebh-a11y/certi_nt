"""Resolve Impol note quotations without inventing a source page."""
import re
import unicodedata

PAGE_REVIEW_EVIDENCE = "testo_pagina_da_verificare"


def normalized_quote(value):
    text = unicodedata.normalize("NFKD", str(value or "")).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def contains_quote(text, quote):
    if quote in text:
        return True
    # Tolerate one OCR letter substitution in a long literal quote only.
    # Numbers and US class letters must still match exactly (STD / STO is common).
    if len(quote) < 40:
        return False
    half = len(quote) // 2
    candidates = set()
    for anchor, offset in ((quote[:half], 0), (quote[half:], half)):
        for found in re.finditer(re.escape(anchor), text):
            candidates.add(found.start()-offset)
    for start in candidates:
        if start < 0:
            continue
        window = text[start:start+len(quote)]
        if len(window) != len(quote) or sum(a != b for a,b in zip(window,quote)) > 1:
            continue
        if re.findall(r"\d+", window) != re.findall(r"\d+", quote):
            continue
        if re.findall(r"CLASS([AB])", window) != re.findall(r"CLASS([AB])", quote):
            continue
        return True
    return False


def locate_quote(quote, page_images):
    # Multiple literal excerpts may be joined by the existing AI prompt with |.
    parts = [normalized_quote(part) for part in str(quote or "").split("|") if part.strip()]
    if not parts or any(len(part) < 12 for part in parts):
        return None, "da_verificare"
    matches = set()
    for crop in page_images.values():
        page_id = crop.get("page_id")
        text = normalized_quote(crop.get("source_text"))
        if page_id and text and all(contains_quote(text, part) for part in parts):
            matches.add(int(page_id))
    if len(matches) == 1:
        return matches.pop(), "verificata"
    return None, "ambigua" if matches else "da_verificare"


def assign_note_pages(payload, page_images):
    """Change provenance only; preserve raw, normalized and final values."""
    for block in ("notes", "mechanical_requirement"):
        for match in payload.get(block, {}).values():
            page_id, status = locate_quote(match.get("snippet"), page_images)
            match["page_id"] = page_id
            match["source_page_status"] = status
    return payload


def evidence_type(match):
    return PAGE_REVIEW_EVIDENCE if match.get("source_page_status") in {"ambigua", "da_verificare"} else "testo"
