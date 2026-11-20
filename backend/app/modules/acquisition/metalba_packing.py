"""Metalba-only reconstruction of printed packing rows. No matching or DB writes.

The model transcribes packages; arithmetic and identity checks stay in the app.
Never distribute an unexplained remainder across casts to make totals balance.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from fastapi import HTTPException


class MetalbaPackingReviewRequired(HTTPException):
    def __init__(self, reason: str, *, pages=(), package_id=None):
        super().__init__(status_code=409, detail=f"DDT Metalba: lettura da verificare. {reason}")
        self.pages = tuple(sorted({p for p in pages if type(p) is int and p > 0}))
        self.package_id = package_id


def token(value: object) -> str | None:
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text and text.lower() not in {"null", "none"} else None


def cast_token(value: object) -> str | None:
    text = token(value)
    return re.sub(r"[\s-]+", "", text.upper()) if text else None


def casts_conflict(left: object, right: object) -> bool:
    a, b = cast_token(left), cast_token(right)
    return bool(a and b and a != b)


def number(value: object) -> Decimal | None:
    """Printed Metalba Italian numbers, accepting ungrouped AI transcriptions."""
    text = token(value)
    if text is None:
        return None
    text = re.sub(r"\s*kg\s*$", "", text, flags=re.I)
    if " " in text:
        # Allow printed thousands groups, never concatenate an annotation and a weight.
        if not re.fullmatch(r"\d{1,3}(?: \d{3})+(?:,\d+)?", text):
            return None
        text = text.replace(" ", "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", text):
        return None
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+", text):
        text = text.replace(",", "")  # Explicit English thousands AND decimal mark.
    elif "," in text:
        if text.count(",") != 1:
            return None
        integer, decimal = text.split(",")
        if "." in integer and not re.fullmatch(r"\d{1,3}(?:\.\d{3})+", integer):
            return None
        text = integer.replace(".", "") + "." + decimal
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    elif text.count(".") > 1:
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def formatted(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".") if value % 1 else str(int(value))


def _integer(value: object) -> int | None:
    text = token(value)
    if text is None or re.search(r"kg\s*$", text, re.I):
        return None
    parsed = number(re.sub(r"\s*(?:pezzi|pcs|colli)\s*$", "", text, flags=re.I))
    return int(parsed) if parsed is not None and parsed % 1 == 0 else None


def _check_package_material(pack: dict, row: dict) -> None:
    """Reject printed contradictions, without requiring absent packing fields."""
    from .metalba_alloy import same_source_alloy
    def compact(value):
        return re.sub(r"[^A-Z0-9]", "", (token(value) or "").upper())
    for field in ("customer_code_raw", "vs_rif_raw"):
        left, right = token(pack.get(field)), token(row.get(field))
        if left and right and compact(left) != compact(right):
            raise MetalbaPackingReviewRequired("Un collo riporta articolo, ordine o lunghezza diversi dalla posizione associata.")
    left, right = token(pack.get("length_raw")), token(row.get("length_raw"))
    if left and right:
        def length(text):
            match = re.search(r"\d+(?:[.,]\d+)*", text)
            return number(match[0]) if match else None
        if length(left) is None or length(left) != length(right):
            raise MetalbaPackingReviewRequired("La lunghezza del collo è diversa dalla posizione associata.")
    left, right = token(pack.get("alloy_raw")), token(row.get("alloy_raw"))
    if left and right and not same_source_alloy(left, right):
        raise MetalbaPackingReviewRequired("La lega del collo è diversa dalla posizione associata.")
    left, right = token(pack.get("diameter_raw")), token(row.get("diameter_raw"))
    if left and right:
        def measure(text):
            match = re.search(r"\d+(?:[.,]\d+)?", text)
            return Decimal(match[0].replace(",", ".")) if match else None
        if measure(left) is None or measure(left) != measure(right):
            raise MetalbaPackingReviewRequired("Il diametro del collo è diverso dalla posizione associata.")


def require_complete_pages(document) -> None:
    pages = document.pages
    count = document.numero_pagine or len(pages)
    if (not pages or len(pages) != count
            or {p.numero_pagina for p in pages} != set(range(1, count + 1))
            or any(not p.immagine_pagina_storage_key for p in pages)):
        raise MetalbaPackingReviewRequired("Una o più pagine non sono disponibili: nessuna riga parziale applicata.")


def reconstruct_rows(
    payload: dict, *, expected_pages: set[int] | None = None, packing_expected: bool = False,
    printed_summary: tuple[int, Decimal] | None = None,
) -> list[dict]:
    """Accept legacy row payloads offline; live callers require page coverage.

    New packing contracts contain commercial rows and individually transcribed
    packages. An index references a commercial row, never a certificate.
    """
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise MetalbaPackingReviewRequired("Righe materiale assenti o non valide.")
    if expected_pages is not None:
        seen = payload.get("pages_read")
        if (not isinstance(seen, list) or any(type(p) is not int for p in seen)
                or set(seen) != expected_pages):
            raise MetalbaPackingReviewRequired("La risposta non copre tutte le pagine del DDT.")
        if type(payload.get("packing_list_present")) is not bool:
            raise MetalbaPackingReviewRequired("Manca la verifica della lista imballi.")
    packing = payload.get("packing_list_present") is True
    if packing_expected and not packing:
        raise MetalbaPackingReviewRequired("La lista imballi presente nel documento non è stata letta.")
    if not packing:
        if payload.get("packages"):
            raise MetalbaPackingReviewRequired("Colli presenti ma lista imballi dichiarata assente.")
        if payload.get("packing_list_present") is False:
            # New ordinary multi-position DDTs also need a stable position key;
            # legacy payloads without this contract keep their original shape.
            return [dict(row, commercial_row_index=row.get("row_index", i), packing_list_present=False,
                         pages_read=payload.get("pages_read")) for i, row in enumerate(rows, 1)]
        return rows

    material = {}
    for ordinal, row in enumerate(rows, 1):
        index = row.get("row_index", ordinal)
        if type(index) is not int or index < 1 or index in material:
            raise MetalbaPackingReviewRequired("Riferimenti alle righe materiale ambigui.")
        material[index] = row
    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages or len(packages) > 20000:
        raise MetalbaPackingReviewRequired("Colli della lista imballi assenti o non validi.")

    unique: dict[tuple, tuple[tuple, dict]] = {}
    grouped: dict[tuple[int, str], dict] = {}
    for pack in packages:
        if not isinstance(pack, dict):
            raise MetalbaPackingReviewRequired("Una riga della lista imballi non è valida.")
        index = pack.get("material_row_index")
        if index is None and len(material) == 1:
            index = next(iter(material))
        if type(index) is not int or index not in material:
            raise MetalbaPackingReviewRequired("Un collo non è riconducibile a una riga materiale precisa.")
        _check_package_material(pack, material[index])
        cast = cast_token(pack.get("colata_raw"))
        weight = number(pack.get("net_weight_raw"))
        pieces = _integer(pack.get("pieces_raw"))
        page = pack.get("page_number")
        location = pack.get("packing_row_index")
        package_id = token(pack.get("package_id_raw"))
        safe_id = package_id if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", package_id or "") else None
        where = safe_id or (f"riga {location}" if type(location) is int else "senza ID")
        bad_fields = []
        if not cast or not re.fullmatch(r"[A-Z0-9]{3,64}", cast) or not re.search(r"\d", cast):
            bad_fields.append("colata")
        if weight is None or weight <= 0:
            bad_fields.append("peso netto")
        if bad_fields:
            raise MetalbaPackingReviewRequired(
                f"Collo {where}: verificare {' e '.join(bad_fields)} nella relativa colonna stampata.",
                pages=[page], package_id=safe_id)
        if type(page) is not int or page < 1 or (expected_pages is not None and page not in expected_pages):
            raise MetalbaPackingReviewRequired("Pagina di provenienza di un collo mancante o non valida.")
        if package_id:
            identity = ("id", package_id.upper().replace(" ", ""))
        elif type(location) is int and location > 0:
            identity = ("position", page, location)
        else:
            raise MetalbaPackingReviewRequired("Un collo non ha identificativo né posizione verificabile nella pagina.")
        fingerprint = (index, cast, weight)
        previous = unique.get(identity)
        if previous:
            if previous[0] != fingerprint:
                raise MetalbaPackingReviewRequired("Lo stesso collo è riportato con dati discordanti.")
            continue
        unique[identity] = (fingerprint, pack)
        group = grouped.setdefault((index, cast), {"weight": Decimal(0), "packages": [], "pieces": 0})
        group["weight"] += weight
        group["packages"].append(pack)
        group["pieces"] = None if pieces is None or group["pieces"] is None else group["pieces"] + pieces

    totals = payload.get("packing_totals") or {}
    if not isinstance(totals, dict):
        raise MetalbaPackingReviewRequired("Riepilogo lista imballi non valido.")
    total_weight = sum((g["weight"] for g in grouped.values()), Decimal(0))
    def net_total(raw):
        parsed = number(raw)
        # A lone comma can mean decimal OR thousands in a model transcription.
        # Resolve ONLY for an entire verified single-position shipment, never for a package.
        value = token(raw) or ""
        if (len(material) == 1 and printed_summary == (len(unique), total_weight)
                and re.fullmatch(r"\d{1,3},\d{3}", value) and parsed != total_weight
                and Decimal(value.replace(",", "")) == total_weight):
            return total_weight
        return parsed
    total_pieces = sum((g["pieces"] or 0 for g in grouped.values()))
    all_pieces_read = all(g["pieces"] is not None for g in grouped.values())
    header_totals = []
    for index, row in material.items():
        selected = [g for (key, _), g in grouped.items() if key == index]
        if not selected:
            raise MetalbaPackingReviewRequired("Una riga materiale non è coperta dalla lista imballi.")
        header = net_total(row.get("net_weight_raw"))
        if token(row.get("net_weight_raw")) is not None and header is None:
            raise MetalbaPackingReviewRequired("Peso della riga materiale non valido.")
        if header is not None:
            header_totals.append(header)
            if abs(sum((g["weight"] for g in selected), Decimal(0)) - header) > Decimal("0.01"):
                subtotal = sum(g["weight"] for g in selected)
                raise MetalbaPackingReviewRequired(
                    f"Posizione {index}: somma dei netti {formatted(subtotal)} kg, netto riga {formatted(header)} kg. "
                    "Verificare la colonna Peso Netto dei colli e il netto della posizione.",
                    pages=[p["page_number"] for g in selected for p in g["packages"]])
    printed_total = net_total(totals.get("net_weight_raw"))
    if token(totals.get("net_weight_raw")) is not None and printed_total is None:
        raise MetalbaPackingReviewRequired("Peso totale della lista imballi non valido.")
    if printed_total is None and len(header_totals) != len(material):
        raise MetalbaPackingReviewRequired("Manca un peso totale verificabile per controllare la lettura dei colli.")
    if printed_total is not None and abs(total_weight - printed_total) > Decimal("0.01"):
        raise MetalbaPackingReviewRequired(
            f"Somma dei netti {formatted(total_weight)} kg, totale DDT {formatted(printed_total)} kg. "
            "Verificare la colonna Peso Netto e il riepilogo.", pages=[p["page_number"] for _, p in unique.values()])
    count = totals.get("package_count_raw")
    if token(count) is not None and _integer(count) != len(unique):
        raise MetalbaPackingReviewRequired("Numero colli diverso dal riepilogo stampato.",
                                          pages=[p["page_number"] for _, p in unique.values()])
    # Pieces are source evidence only, not used for Incoming identity, weight or matching.
    printed_pieces = totals.get("pieces_raw")
    piece_discrepancy = token(printed_pieces) is not None and (
        not all_pieces_read or _integer(printed_pieces) != total_pieces)

    result = []
    for (index, cast), group in grouped.items():
        row = dict(material[index])
        row.update(row_index=len(result) + 1, commercial_row_index=index, colata_raw=cast,
                   net_weight_raw=formatted(group["weight"]), packing_packages=group["packages"],
                   packing_piece_total=group["pieces"], packing_totals=totals, packing_piece_discrepancy=piece_discrepancy,
                   pages_read=payload.get("pages_read"), packing_list_present=True,
                   packing_cast_count=sum(1 for material_index, _ in grouped if material_index == index))
        row["source_crops"] = list(dict.fromkeys(
            [v for v in (row.get("source_crops") or []) if isinstance(v, str)]
            + [f"page{p['page_number']}_row_groups_page" for p in group["packages"]]))
        result.append(row)
    return result
