"""Independent checks for Metalba packing images. Never fill fields from OCR."""
from __future__ import annotations

from decimal import Decimal
import re

from .metalba_packing import MetalbaPackingReviewRequired, cast_token, number

# Match only the printed tail of a TK line: net, gross, pieces, cast. Text/handwriting
# to the LEFT of the net column is irrelevant. An incomplete line is not evidence.
_TK = re.compile(r"^\s*(TK[0-9]{5,14})\s", re.I)
_KG = r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}"
_TAIL = re.compile(rf"\s({_KG})\s+({_KG})\s+({_KG})\s+([0-9A-Z]{{3,32}})\s*$", re.I)
_SUMMARY = re.compile(rf"\bNR\.?\s+COLLI\s*:\s*(\d+)\s+TOTALI\s*:\s*({_KG})\s+({_KG})\s+({_KG})\s*$", re.I)
Key = tuple[int, str]
Reading = tuple[Decimal, str]


def printed_summary(pages):
    """Read only clearly labelled count/net/gross columns, not a bare OCR number."""
    values = set()
    for _, lines in pages:
        for line in lines:
            if m := _SUMMARY.search(line):
                net, gross = number(m[2]), number(m[3])
                if net is not None and gross is not None and 0 < net <= gross:
                    values.add((int(m[1]), net))
    return next(iter(values)) if len(values) == 1 else None


def printed_packages(pages) -> dict[Key, Reading]:
    seen = {}
    ambiguous = set()
    for page, lines in pages:
        for line in lines:
            tk, cols = _TK.match(line), _TAIL.search(line)
            if not tk or not cols:
                continue
            val, gross = number(cols[1]), number(cols[2])
            if val is None or gross is None or not 0 < val <= gross or not re.search(r"\d", cols[4]):
                continue
            key, fields = (page, tk[1].upper()), (val, cols[4].upper())
            if key in seen and seen[key] != fields:
                ambiguous.add(key)
            seen[key] = fields
    return {k: v for k, v in seen.items() if k not in ambiguous}


def check_printed_packages(rows, printed, *, first_disputes, retry):
    """An OCR discrepancy requests a blind visual reread, never an OCR substitution.

    A second reading must agree with the print witness or independently repeat
    the original field, for the SAME physical package. No third value/no lost TK.
    """
    current = {}
    for row in rows:
        for p in row.get("packing_packages", ()):
            key = (p["page_number"], str(p.get("package_id_raw") or "").strip().upper())
            if key in printed:
                current[key] = (number(p.get("net_weight_raw")), cast_token(p.get("colata_raw")))
    if retry and any(key not in current for key, field in first_disputes):
        raise MetalbaPackingReviewRequired("Il collo da verificare non è identificabile nella seconda lettura.")
    conflicts = {}
    for key, values in current.items():
        for index, val in enumerate(values):
            if val != printed[key][index] and (not retry or first_disputes.get((key, index)) != val):
                conflicts[key, index] = val
    if conflicts:
        if not retry:
            first_disputes.update(conflicts)
        keys = {k for k, _ in conflicts}
        fields = " e ".join(name for i, name in enumerate(("peso netto", "colata"))
                             if any(n == i for _, n in conflicts))
        labels = ", ".join(k[1] for k in sorted(keys)[:5])
        raise MetalbaPackingReviewRequired(
            f"Letture discordanti: rileggere {fields} per {labels} nella colonna stampata.",
            pages={k[0] for k in keys}, package_id=next(iter(keys))[1] if len(keys) == 1 else None)


def remember_first_fields(packages, printed, first_disputes):
    """A failed weight sum does not erase an independently readable cast (and vice versa).
    Never use an invalid or contradictory first field to corroborate a second reading.
    """
    observed = {}
    for p in packages if isinstance(packages, list) else ():
        if not isinstance(p, dict) or type(p.get("page_number")) is not int:
            continue
        key = (p["page_number"], str(p.get("package_id_raw") or "").strip().upper())
        if key not in printed:
            continue
        for i, value in enumerate((number(p.get("net_weight_raw")), cast_token(p.get("colata_raw")))):
            observed.setdefault((key, i), set()).add(value)
    for (key, i), values in observed.items():
        if len(values) == 1:
            val = next(iter(values))
            # None cannot confirm any valid field on retry, but its known TK must
            # not disappear merely because the second response replaced a row.
            if val != printed[key][i]:
                first_disputes[key, i] = val


def zoom_box(words, width, height, package_id=None):
    """Locate rows in the already masked image, not at fixed template coordinates."""
    tks = [w for w in words if re.fullmatch(r"TK\d{5,14}", w["text"], re.I)]
    target = [w for w in tks if w["text"].upper() == package_id] if package_id else []
    if target:
        rows = target
    elif tks:
        rows = tks + [w for w in words if w["text"].upper().strip(":") in {"NETTO", "COLATA", "TOTALI"}]
    else:
        return None  # Original complete masked page is still available.
    pad = max(16, max(w["bottom"] - w["top"] for w in rows) * 2)
    return (0, max(0, min(w["top"] for w in rows) - pad), width,
            min(height, max(w["bottom"] for w in rows) + pad))
