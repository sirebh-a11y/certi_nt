"""Bozen: the packing group, not the bar length, defines an Incoming row."""
import json
import re
from datetime import date
from decimal import Decimal

from .ddt_packing import DdtPackingReviewRequired, component_total, validate_reading_contract


def one_order_date_missing(left, right):
    """Only canonical order numbers, exactly one valid ISO date. Never infer a date."""
    a, b = sorted((str(left or "").strip(), str(right or "").strip()), key=len)
    if not re.fullmatch(r"[0-9]{1,6}", a):
        return False
    dated = re.fullmatch(r"([0-9]{1,6})-(20[0-9]{2}-[0-9]{2}-[0-9]{2})", b)
    if not dated or dated[1] != a:
        return False
    try:
        date.fromisoformat(dated[2])
    except ValueError:
        return False
    return True


def same_material_for_undated_order(ddt, certificate):
    """Require documentary evidence on BOTH sides; no tolerances, no shared-row defaults."""
    for field in ("cdq", "colata", "lega", "diametro", "peso", "article_code"):
        a, b = ddt.value(field), certificate.value(field)
        if not a or not b:
            return False
        if field in {"diametro", "peso"}:
            if not all(re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", x) for x in (a, b)):
                return False
            x, y = (Decimal(v.replace(",", ".")) for v in (a, b))
            if x != y or x <= 0:
                return False
        elif " ".join(a.upper().split()) != " ".join(b.upper().split()):
            return False
    return True  # the existing conflict check also checks profile codes when available


def _token(value):
    if isinstance(value, bool) or (not isinstance(value, (str, int)) and value is not None):
        raise DdtPackingReviewRequired("Campo Bozen in formato non valido.")
    return " ".join(str(value or "").upper().split())


def identity_suffix(payload_text):
    # Historical completion signatures are never migrated/recomputed.
    if not payload_text or '"bozen_packing_v2"' not in payload_text:
        return ()
    try:
        row = json.loads(payload_text)
    except (TypeError, ValueError):
        return ()
    if isinstance(row, dict) and row.get("bozen_packing_v2") is True:
        return ("bozen-v2", _token(row.get("certificate_no_raw")))
    return ()


def material_codes(*fields):
    # DDT and certificate can present the two codes in opposite columns.
    codes = " ".join(map(_token, fields))
    result = []
    for pattern in (r"\b[0-9]{2}[A-Z]{2}[0-9A-Z-]{4,}\b", r"\bA[0-9][0-9A-Z]{4,}\b"):
        found = set(re.findall(pattern, codes))
        if len(found) > 1:
            raise DdtPackingReviewRequired("Codici articolo o profilo Bozen discordanti.")
        result.append(next(iter(found), None))
    return tuple(result)


def read_groups(text, expected_pages, normalize_order):
    try:
        raw = json.loads(re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip()))
    except (TypeError, ValueError, AttributeError):
        raise DdtPackingReviewRequired("Risposta Bozen non leggibile.") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        raise DdtPackingReviewRequired("Righe Bozen mancanti.")
    rows = raw["rows"]
    groups = {}
    owners = set()
    unidentified_package = False
    check_rows = []
    for row in rows:
        if not isinstance(row, dict):
            raise DdtPackingReviewRequired("Riga Bozen non leggibile.")
        article, profile = material_codes(row.get("article_code_raw"), row.get("profile_code_raw"))
        ref, order, cdq, heat, alloy, diameter = (
            _token(row.get(k)) for k in ("packing_ref_raw", "customer_order_raw", "certificate_no_raw",
                                         "cast_raw", "alloy_raw", "diameter_raw"))
        if not any((article, profile, heat, cdq)) or not (alloy or diameter):
            raise DdtPackingReviewRequired("Gruppo Bozen senza riferimenti materiale sufficienti.")
        key = (ref, normalize_order(order), cdq, heat, alloy, diameter, article, profile)
        # Do not infer an association for missing fields. A single legible
        # delivery position can survive without a certificate or a packing list.
        parts = row.get("weight_components")
        if not isinstance(parts, list) or not parts:
            raise DdtPackingReviewRequired("Mancano i dettagli dei pesi del gruppo Bozen.")
        if (key in groups or len(parts) > 1) and (
            not all(key) or not re.fullmatch(r"\d{4,7}[A-Z]?", cdq) or cdq == "10204"
        ):
            raise DdtPackingReviewRequired("Sottorighe Bozen senza un gruppo packing univoco.")
        groups.setdefault(key, []).append(row)
        # Use the common coverage, cross-group ownership and net-total checks,
        # with the FULL Bozen identity, not the default supplier field names.
        check_rows.append({"material_raw": json.dumps(key), "weight_components": row.get("weight_components")})
        for part in parts:
            if (not isinstance(part, dict) or type(part.get("page_number")) is not int
                    or (not _token(part.get("package_id_raw")) and type(part.get("physical_row_index")) is not int)):
                raise DdtPackingReviewRequired("Posizione di un collo Bozen non valida.")
            ident = _token(part.get("package_id_raw"))
            if ident:
                owners.add(ident)
            else:
                unidentified_package = True
    pages = raw.get("pages_read")
    if not isinstance(pages, list) or not all(type(p) is int for p in pages):
        raise DdtPackingReviewRequired("Pagine Bozen non identificate.")
    # An incomplete repeated header may be a continuation, not a new material.
    # If the known fields do not discriminate it, never turn it into a new row.
    keys = list(groups)
    for i, first in enumerate(keys):
        for second in keys[i + 1:]:
            if not any(a and b and a != b for a, b in zip(first, second)):
                raise DdtPackingReviewRequired("Due gruppi Bozen senza riferimenti sufficienti per distinguerli.")
    validate_reading_contract(json.dumps({**raw, "rows": check_rows}), expected_pages)
    count = raw.get("package_count")
    if count is not None and (type(count) is not int or count <= 0 or unidentified_package or len(owners) != count):
        raise DdtPackingReviewRequired("I numeri dei colli non concordano con il totale stampato.")
    result = []
    for key, group in groups.items():
        article, profile = key[-2:]
        result.append({**group[0], "row_index": len(result) + 1, "bozen_packing_v2": True,
            "article_code_raw": article, "profile_code_raw": profile,
            "net_weight_raw": component_total(group),
            "weight_components": [p for row in group for p in row["weight_components"]],
            "source_crops": list(dict.fromkeys(s for row in group if isinstance(row.get("source_crops"), list)
                                              for s in row["source_crops"] if isinstance(s, str)))})
    return _token(raw.get("ddt_number_raw")) or None, result, text
