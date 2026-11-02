"""Shared DDT safety checks, not supplier identity or matching rules.

Physical rows/packages must have an identity before they can be deduplicated.
Equal weights alone are never an identity. No balancing by invented remainders.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException

SUPPORTED_SUPPLIERS = frozenset({"metalba", "leichtmetall", "neuman", "grupa_kety",
                               "aluminium_bozen", "impol", "aww", "arconic_hannover", "zalco"})


class DdtPackingReviewRequired(HTTPException):
    def __init__(self, reason: str):
        super().__init__(409, f"DDT: lettura da verificare. {reason}")


def require_complete_pages(document) -> None:
    pages = document.pages
    count = document.numero_pagine or len(pages)
    if (not pages or len(pages) != count
            or {p.numero_pagina for p in pages} != set(range(1, count + 1))
            or any(not p.immagine_pagina_storage_key for p in pages)):
        raise DdtPackingReviewRequired("Una o più pagine non sono disponibili; nessuna lettura parziale applicata.")


def unique_page_crops(crops: dict) -> dict:
    """Keep the full masked page once, retaining canonical row-group labels."""
    selected = {}
    for label, crop in crops.items():
        key = (crop.get("page_number"), crop.get("storage_key"))
        if key not in selected or crop.get("role") == "row_groups_page":
            selected[key] = (label, crop)
    return {label: crop for label, crop in selected.values()}


def weight(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = re.sub(r"(?i)\s*kg\s*$", "", str(value)).replace(" ", "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)*", text):
        return None
    # Continental or English thousands/decimal notation, as printed.
    if "," in text and "." in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        text = re.sub(r"[.,]", "", text)
    else:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def formatted(value: Decimal) -> str:
    return str(int(value)) if value % 1 == 0 else format(value, "f").rstrip("0").rstrip(".")


def component_total(rows: list[dict]) -> str | None:
    """New AI contract: components are physical rows, never summary totals.

    None means legacy/no components. Partially supplied components are unsafe.
    IDs are scoped to the logical material group by the caller.
    """
    if not any(row.get("weight_components") is not None for row in rows):
        return None
    if any(not isinstance(row.get("weight_components"), list) or not row["weight_components"] for row in rows):
        raise DdtPackingReviewRequired("Dettagli dei pesi presenti solo per una parte del gruppo.")
    unique = {}
    for row in rows:
        for part in row["weight_components"]:
            if not isinstance(part, dict):
                raise DdtPackingReviewRequired("Dettaglio peso non valido.")
            identifier = str(part.get("package_id_raw") or "").strip().upper()
            page, location = part.get("page_number"), part.get("physical_row_index")
            if type(page) is not int or page < 1:
                raise DdtPackingReviewRequired("Pagina del dettaglio peso non valida.")
            identity = ("id", identifier) if identifier else ("position", page, location)
            if not identifier and (type(location) is not int or location < 1):
                raise DdtPackingReviewRequired("Dettaglio senza identificativo né posizione nella pagina.")
            number = weight(part.get("net_weight_raw"))
            if number is None or number <= 0:
                raise DdtPackingReviewRequired("Peso netto del dettaglio mancante o non valido.")
            if identity in unique and unique[identity] != number:
                raise DdtPackingReviewRequired("Lo stesso collo o sottoriga riporta pesi discordanti.")
            unique[identity] = number
    return formatted(sum(unique.values(), Decimal(0)))


def validate_reading_contract(text: str, expected_pages: set[int]) -> None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise DdtPackingReviewRequired("Risposta di lettura non valida.") from None
    pages = data.get("pages_read") if isinstance(data, dict) else None
    if (not isinstance(pages, list) or any(type(p) is not int for p in pages)
            or set(pages) != expected_pages):
        raise DdtPackingReviewRequired("La risposta non copre tutte le pagine del documento.")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise DdtPackingReviewRequired("Righe del documento assenti o non valide.")
    owners = {}
    for row in rows:
        if not isinstance(row.get("weight_components"), list) or not row["weight_components"]:
            raise DdtPackingReviewRequired("Mancano i dettagli dei pesi per verificare il gruppo.")
        group = tuple(str(row.get(key) or "").strip().upper() for key in (
            "batch_raw", "lot_raw", "heat_raw", "certificate_number_raw", "alloy_raw", "material_raw",
            "diameter_raw", "purchase_number_raw", "customer_order_raw", "article_number_raw",
        ))
        for part in row["weight_components"]:
            if not isinstance(part, dict) or part.get("page_number") not in expected_pages:
                raise DdtPackingReviewRequired("Un dettaglio peso proviene da una pagina non disponibile.")
            identifier = str(part.get("package_id_raw") or "").strip().upper()
            identity = ("id", identifier) if identifier else ("position", part.get("page_number"), part.get("physical_row_index"))
            if identity in owners and owners[identity] != group:
                raise DdtPackingReviewRequired("Lo stesso collo/sottoriga è attribuito a gruppi materiale diversi.")
            owners[identity] = group
    computed = Decimal(component_total(rows))  # already canonical, never parse thousands twice
    printed = data.get("document_net_weight_raw")
    if printed is not None:
        total = weight(printed)
        if total is None or abs(total - computed) > Decimal("0.01"):
            raise DdtPackingReviewRequired("La somma dei dettagli non coincide con il netto totale stampato del DDT.")


COMPONENT_INSTRUCTION = (
    " Leggi TUTTE le pagine: aggiungi pages_read con i numeri delle pagine lette e "
    "document_net_weight_raw con il netto totale stampato del DDT (null se assente, mai il lordo). "
    "Per ogni gruppo aggiungi weight_components, una voce per ciascun collo/sottoriga fisica "
    "che contribuisce al netto; non includere riepiloghi, lordi o totali insieme ai dettagli. "
    "Ogni voce ha package_id_raw (HU/identificativo collo se stampato, altrimenti null), "
    "page_number, physical_row_index (numero progressivo della riga fisica nella pagina), net_weight_raw. "
    "Due colli distinti con lo stesso peso restano due voci; lo stesso collo ripetuto resta uno. "
    "Non distribuire differenze di peso fra gruppi. Se è stampato solo il totale del gruppo, "
    "trascrivi quel totale come unico componente con la sua posizione. "
)
