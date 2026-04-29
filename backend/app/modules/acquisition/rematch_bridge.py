from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping


BridgeValues = Mapping[str, str | None]


class RematchDecision(str, Enum):
    NONE = "none"
    CANDIDATE = "candidate"
    STRONG = "strong"


@dataclass(frozen=True)
class RematchBridge:
    side: str
    supplier_id: int | None = None
    supplier_name: str | None = None
    row_id: int | None = None
    document_id: int | None = None
    values: dict[str, str | None] = field(default_factory=dict)

    def value(self, field_name: str) -> str | None:
        value = self.values.get(field_name)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


@dataclass(frozen=True)
class RematchScore:
    decision: RematchDecision
    score: int
    matched_fields: tuple[str, ...]
    blockers: tuple[str, ...]
    reasons: tuple[str, ...]


def build_ddt_bridge(
    *,
    row_values: BridgeValues,
    read_values: BridgeValues | None = None,
    supplier_id: int | None = None,
    supplier_name: str | None = None,
    row_id: int | None = None,
    document_id: int | None = None,
) -> RematchBridge:
    return _build_bridge(
        side="ddt",
        row_values=row_values,
        read_values=read_values or {},
        field_sources={
            "fornitore": ("fornitore", "fornitore_raw", "fornitore_nome"),
            "lega": ("lega", "lega_base"),
            "diametro": ("diametro",),
            "cdq": ("numero_certificato_ddt", "cdq"),
            "colata": ("colata",),
            "ddt": ("ddt",),
            "peso": ("peso",),
            "ordine": ("customer_order_no", "ordine"),
        },
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        row_id=row_id,
        document_id=document_id,
    )


def build_certificate_bridge(
    *,
    row_values: BridgeValues,
    read_values: BridgeValues | None = None,
    supplier_id: int | None = None,
    supplier_name: str | None = None,
    row_id: int | None = None,
    document_id: int | None = None,
) -> RematchBridge:
    return _build_bridge(
        side="certificato",
        row_values=row_values,
        read_values=read_values or {},
        field_sources={
            "fornitore": ("fornitore", "fornitore_raw", "fornitore_nome"),
            "lega": ("lega_certificato", "lega_base"),
            "diametro": ("diametro_certificato", "diametro"),
            "cdq": ("numero_certificato_certificato", "cdq"),
            "colata": ("colata_certificato", "colata"),
            "ddt": ("ddt_certificato", "ddt"),
            "peso": ("peso_certificato", "peso"),
            "ordine": ("ordine_cliente_certificato", "ordine"),
        },
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        row_id=row_id,
        document_id=document_id,
    )


def score_bridge_match(ddt_bridge: RematchBridge, certificate_bridge: RematchBridge) -> RematchScore:
    supplier_blocker = _supplier_blocker(ddt_bridge, certificate_bridge)
    if supplier_blocker is not None:
        return RematchScore(
            decision=RematchDecision.NONE,
            score=0,
            matched_fields=(),
            blockers=(supplier_blocker,),
            reasons=(),
        )

    blockers = list(_hard_blockers(ddt_bridge, certificate_bridge))
    if blockers:
        return RematchScore(
            decision=RematchDecision.NONE,
            score=0,
            matched_fields=(),
            blockers=tuple(blockers),
            reasons=(),
        )

    matched_fields: list[str] = []
    reasons: list[str] = []
    score = 0
    weights = {
        "cdq": 150,
        "colata": 100,
        "diametro": 85,
        "peso": 75,
        "ordine": 65,
        "lega": 45,
        "ddt": 30,
    }
    for field_name, points in weights.items():
        if _field_matches(field_name, ddt_bridge.value(field_name), certificate_bridge.value(field_name)):
            matched_fields.append(field_name)
            score += points
            reasons.append(f"{field_name} coerente")

    matched = set(matched_fields)
    strong_patterns = (
        {"cdq"},
        {"colata", "diametro", "peso"},
        {"ordine", "lega", "diametro", "colata"},
    )
    has_strong_pattern = any(pattern.issubset(matched) for pattern in strong_patterns)

    # Lega alone, or only weak supports, must never create a rematch proposal.
    material_support_count = len(matched & {"colata", "diametro", "peso", "ordine", "cdq"})
    if not has_strong_pattern and material_support_count < 3:
        return RematchScore(
            decision=RematchDecision.NONE,
            score=score,
            matched_fields=tuple(matched_fields),
            blockers=(),
            reasons=tuple(reasons),
        )

    if has_strong_pattern and score >= 220:
        decision = RematchDecision.STRONG
    elif score >= 180 and material_support_count >= 3:
        decision = RematchDecision.CANDIDATE
    else:
        decision = RematchDecision.NONE

    return RematchScore(
        decision=decision,
        score=score,
        matched_fields=tuple(matched_fields),
        blockers=(),
        reasons=tuple(reasons),
    )


def _build_bridge(
    *,
    side: str,
    row_values: BridgeValues,
    read_values: BridgeValues,
    field_sources: Mapping[str, tuple[str, ...]],
    supplier_id: int | None,
    supplier_name: str | None,
    row_id: int | None,
    document_id: int | None,
) -> RematchBridge:
    values: dict[str, str | None] = {}
    for target_field, source_fields in field_sources.items():
        values[target_field] = _first_present(read_values, source_fields) or _first_present(row_values, source_fields)
    if values.get("fornitore") is None:
        values["fornitore"] = supplier_name
    return RematchBridge(
        side=side,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        row_id=row_id,
        document_id=document_id,
        values=values,
    )


def _first_present(values: BridgeValues, source_fields: tuple[str, ...]) -> str | None:
    for source_field in source_fields:
        value = values.get(source_field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _supplier_blocker(left: RematchBridge, right: RematchBridge) -> str | None:
    if left.supplier_id is not None and right.supplier_id is not None and left.supplier_id != right.supplier_id:
        return "fornitore diverso"
    left_name = _compact_text(left.value("fornitore") or left.supplier_name)
    right_name = _compact_text(right.value("fornitore") or right.supplier_name)
    if left_name and right_name and left_name != right_name:
        return "fornitore diverso"
    return None


def _hard_blockers(left: RematchBridge, right: RematchBridge) -> tuple[str, ...]:
    blockers: list[str] = []
    # Weight is supporting evidence only: one certificate can cover multiple DDT
    # rows or a certificate-wide total, so a mismatch must not block a strong bridge.
    for field_name in ("colata", "diametro"):
        left_value = left.value(field_name)
        right_value = right.value(field_name)
        if left_value is None or right_value is None:
            continue
        if not _field_matches(field_name, left_value, right_value):
            blockers.append(f"{field_name} diverso")
    return tuple(blockers)


def _field_matches(field_name: str, left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    if field_name == "lega":
        return _normalize_alloy(left) == _normalize_alloy(right)
    if field_name == "diametro":
        return _normalize_number(left) == _normalize_number(right)
    if field_name == "peso":
        return _weights_match(left, right)
    if field_name == "colata":
        return _normalize_primary_code(left) == _normalize_primary_code(right)
    if field_name in {"cdq", "ordine", "ddt"}:
        return _compact_text(left) == _compact_text(right)
    if field_name == "fornitore":
        return _compact_text(left) == _compact_text(right)
    return _compact_text(left) == _compact_text(right)


def _compact_text(value: str | None) -> str | None:
    if value is None:
        return None
    compact = re.sub(r"[^A-Z0-9]+", "", str(value).upper())
    return compact or None


def _normalize_alloy(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).upper()
    text = re.sub(r"\bEN\s*AW\b", "", text)
    text = re.sub(r"\bAA\b", "", text)
    return _compact_text(text)


def _normalize_primary_code(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).upper()
    text = re.split(r"[\s(;/]+", text.strip(), maxsplit=1)[0]
    return _compact_text(text)


def _normalize_number(value: str | None) -> str | None:
    number = _extract_number(value)
    if number is None:
        return None
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _normalize_weight(value: str | None) -> float | None:
    number_text = _extract_number_text(value)
    if number_text is None:
        return None
    normalized = _normalize_numeric_text(number_text)
    if normalized is None:
        return None
    number = float(normalized)
    if _looks_like_thousands_weight(number_text):
        return number * 1000
    return number


def _weights_match(left: str | None, right: str | None) -> bool:
    left_weight = _normalize_weight(left)
    right_weight = _normalize_weight(right)
    if left_weight is None or right_weight is None:
        return False
    tolerance = max(1.0, max(abs(left_weight), abs(right_weight)) * 0.001)
    return abs(left_weight - right_weight) <= tolerance


def _extract_number(value: str | None) -> float | None:
    number_text = _extract_number_text(value)
    if number_text is None:
        return None
    normalized = _normalize_numeric_text(number_text)
    return float(normalized) if normalized is not None else None


def _extract_number_text(value: str | None) -> str | None:
    if value is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return match.group(0) if match else None


def _normalize_numeric_text(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def _looks_like_thousands_weight(value: str) -> bool:
    text = value.strip()
    if "," in text:
        return False
    return bool(re.fullmatch(r"\d{1,2}\.\d{3}", text))
