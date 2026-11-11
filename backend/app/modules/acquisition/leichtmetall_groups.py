"""Leichtmetall cast lists, not ranges. Pure rules shared by every match path.

No PDF/file-name guessing, AI calls or database writes belong here. DDT weights
are net kg per material group; certificate weight is the total of its members.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


EVIDENCE_TYPE = "leichtmetall_group_link_v1"


@dataclass(frozen=True)
class CastIdentity:
    text: str
    members: tuple[str, ...] = ()

    @property
    def grouped(self):
        return len(self.members) > 1


def cast_identity(value) -> CastIdentity | None:
    if value is None or not str(value).strip():
        return None
    # Quotes/backticks are OCR punctuation, not list separators. In particular
    # 95131.33`.35 remains the explicit list 95131, 95133, 95135.
    text = re.sub(r"[`'\"“”‘’]", "", str(value)).strip().upper()
    text = re.sub(r"\s*\.\s*", ".", text)
    if not re.fullmatch(r"\d{5,6}(?:\.(?:\d{2}|\d{5,6}))*", text):
        return CastIdentity(text)  # uncertain: NEVER fall back to its first cast
    parts = text.split(".")
    if parts[0] == "10204":
        return CastIdentity(text)
    members = tuple(parts[0][:-2] + p if len(p) == 2 else p for p in parts)
    if len(set(members)) != len(members) or any(len(p) != len(parts[0]) for p in members):
        return CastIdentity(text)
    return CastIdentity(text, members)


def cast_text(value) -> str | None:
    identity = cast_identity(value)
    if identity and (identity.members or is_group_reference(identity.text)):
        return identity.text
    return None


def is_group_reference(value) -> bool:
    identity = cast_identity(value)
    return bool(identity and (identity.grouped or re.fullmatch(
        r"\d{5,6}(?:(?:\s*[./,;:+\-·•|–—]\s*|\s+(?:and|und)\s+)\d+)+",
        identity.text, flags=re.IGNORECASE)))


def kg(value) -> Decimal | None:
    """Read printed kg (5,047 / 5.047) and canonical kg, without unit guessing."""
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    text = re.sub(r"KG$", "", text)
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        text = text.replace(",", "").replace(".", "")
    elif re.fullmatch(r"\d+(?:[.,]\d{1,2})?", text):
        text = text.replace(",", ".")
    else:
        return None
    try:
        result = Decimal(text)
        return result if result.is_finite() and result > 0 else None
    except InvalidOperation:
        return None


def token(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def order_token(value):
    # PO 332.2+3 is not PO 332.23. Spaces may vary, the printed structure may not.
    text = re.sub(r"\s+", "", str(value or "").upper())
    # Real DDT AI reading: 332, 2 + 3 vs certificate 332. 2 + 3. Preserve
    # components and '+', only normalize the numeric punctuation variant.
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


def diameter(value):
    try:
        number = Decimal(str(value).replace(",", "."))
        return number if number.is_finite() and number > 0 else None
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class DdtMember:
    row_id: int
    batch: str | None
    weight: str | None
    alloy: str | None
    diameter: str | None
    order: str | None
    complete: bool = False
    certificate_ref: str | None = None
    other_certificate_ref: str | None = None


@dataclass(frozen=True)
class Coverage:
    identity: str | None = None
    row_ids: tuple[int, ...] = ()
    reason: str | None = None

    @property
    def valid(self):
        return bool(self.row_ids) and self.reason is None


def coverage(*, members: tuple[DdtMember, ...], target_id: int | None,
             certificate: dict) -> Coverage:
    identity = cast_identity(certificate.get("colata") or certificate.get("cdq"))
    number = cast_identity(certificate.get("cdq"))
    if not identity or not identity.grouped:
        return Coverage(reason="Elenco lotti del certificato non verificabile")
    if number and number.members != identity.members:
        return Coverage(reason="Numero certificato e colata discordanti")
    alloy = token(certificate.get("lega"))
    diam = diameter(certificate.get("diametro"))
    order = order_token(certificate.get("ordine"))
    if not alloy or diam is None:
        return Coverage(reason="Materiale del certificato incompleto")
    selected = tuple(m for m in members if m.batch in identity.members
        and token(m.alloy) == alloy and diameter(m.diameter) == diam
        and (not order or order_token(m.order) == order))
    if {m.batch for m in selected} != set(identity.members):
        return Coverage(reason="Mancano lotti del certificato nel DDT")
    if len(selected) != len(identity.members) or len({m.row_id for m in selected}) != len(selected):
        return Coverage(reason="Lotti DDT non univoci")
    if target_id not in {m.row_id for m in selected}:
        return Coverage(reason="Lotto DDT non coperto dal certificato")
    if not all(m.complete for m in selected):
        return Coverage(reason="Dettaglio DDT incompleto o modificato")
    for member in selected:
        for value in (member.certificate_ref, member.other_certificate_ref):
            ref = cast_identity(value)
            if ref and ref.text != member.batch and ref.members != identity.members:
                return Coverage(reason="Riferimento certificato DDT discordante")
    orders = {order_token(m.order) for m in selected}
    if len(orders) != 1 or (order and orders != {order}):
        return Coverage(reason="Ordine discordante o ambiguo")
    weights = [kg(m.weight) for m in selected]
    if any(w is None for w in weights):
        return Coverage(reason="Pesi netti dei lotti incompleti")
    total = kg(certificate.get("peso"))
    if certificate.get("peso") and total is None:
        return Coverage(reason="Peso del certificato non interpretabile")
    if total is not None:
        # Same strict scale as side confirmation: max(1 kg, 0.1%), not the
        # permissive generic single-row tolerance. Never sum distinct DDTs.
        actual = sum(weights, Decimal(0))
        if abs(actual - total) > max(Decimal(1), total * Decimal("0.001")):
            return Coverage(reason="Somma pesi dei lotti diversa dal totale certificato")
    elif not order or orders != {order}:
        return Coverage(reason="Mancano sia il totale verificabile sia l'ordine")
    return Coverage(identity.text, tuple(sorted(m.row_id for m in selected)))


def recover_cached_identity(payload, reader_key):
    """Pure, narrow replay of a saved raw identity; no cache invalidation/AI."""
    if reader_key != "leichtmetall" or not isinstance(payload, dict):
        return payload
    import json
    from copy import deepcopy
    try:
        core = json.loads(payload.get("debug_raw_output") or "{}").get("core") or {}
        raw = core.get("charge_cast_no") or core.get("colata")
        identity = cast_identity(raw)
        if not identity or not is_group_reference(raw):
            return payload
        current = (payload.get("match_values") or {}).get("numero_certificato_certificato")
        # Only undo the historical first-token truncation, never an intentional
        # correction or an unrelated identity.
        first = re.match(r"\d{5,6}", identity.text)
        old_first = first.group() if first else None
        if current not in {old_first, identity.text}:
            return payload
        result = deepcopy(payload)
        for key in ("numero_certificato_certificato", "colata_certificato"):
            old = (result.get("match_values") or {}).get(key)
            if old not in {None, old_first, identity.text}:
                return payload
            result.setdefault("match_values", {})[key] = identity.text
            if key in (result.get("core_fields") or {}):
                result["core_fields"][key]["value"] = identity.text
        result.setdefault("supplier_fields", {})["charge_cast_no"] = identity.text
        return result
    except (ValueError, TypeError, AttributeError):
        return payload
