from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping

from app.modules.document_reader.matching import (
    _normalize_order_confirmation_root,
    aww_weights_are_compatible, neuman_weights_are_compatible, weights_are_compatible,
)
from app.modules.document_reader.registry import resolve_supplier_template
from .metalba_alloy import same_source_alloy as metalba_same_source_alloy


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
    supplier_key: str | None = None

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
    supplier_key: str | None = None,
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
            "ordine": (("vs_rif", "customer_order_no", "ordine") if supplier_key == "metalba"
                       else ("customer_order_no", "ordine")),
            "article_code": ("arconic_item_number", "article_code", "articolo"),
            "customer_code": ("customer_item_number", "customer_code", "codice_cliente"),
            "line_no": ("line_no", "product_code"),
            "supplier_order_no": ("sales_order_number", "supplier_order_no"),
            "lot_batch_no": ("lot_batch_no", "job_number"),
            "profile_code": ("profile_code", "product_code"),
            "order_confirmation_root": ("order_confirmation_root", "supplier_order_no"),
        },
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        row_id=row_id,
        document_id=document_id,
        supplier_key=supplier_key,
    )


def build_certificate_bridge(
    *,
    row_values: BridgeValues,
    read_values: BridgeValues | None = None,
    supplier_id: int | None = None,
    supplier_name: str | None = None,
    row_id: int | None = None,
    document_id: int | None = None,
    supplier_key: str | None = None,
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
            "article_code": ("articolo_certificato", "arconic_item_number", "article_code"),
            "customer_code": ("codice_cliente_certificato", "customer_item_number", "customer_code"),
            "line_no": ("line_no_certificato", "line_no", "product_code"),
            "supplier_order_no": ("sales_order_number_certificato", "sales_order_number", "supplier_order_no"),
            "lot_batch_no": ("lot_batch_no_certificato", "job_number", "lot_batch_no"),
            "profile_code": ("profile_code_certificato",),
            "order_confirmation_root": ("supplier_order_no_certificato",),
        },
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        row_id=row_id,
        document_id=document_id,
        supplier_key=supplier_key,
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
    arconic_pair = _is_arconic_bridge_pair(ddt_bridge, certificate_bridge)
    grupa_kety_pair = _is_grupa_kety_bridge_pair(ddt_bridge, certificate_bridge)
    leichtmetall_pair = _is_leichtmetall_bridge_pair(ddt_bridge, certificate_bridge)
    weights = {
        "cdq": 150,
        "colata": 100,
        "diametro": 85,
        "peso": 75,
        "ordine": 65,
        "lega": 45,
        "ddt": 30,
    }
    if arconic_pair:
        weights.update(
            {
                "article_code": 95,
                "customer_code": 95,
                "line_no": 70,
                "supplier_order_no": 55,
                "lot_batch_no": 35,
            }
        )
    supplier_key = _bridge_supplier_key(ddt_bridge, certificate_bridge)
    for field_name, points in weights.items():
        if _field_matches(field_name, ddt_bridge.value(field_name), certificate_bridge.value(field_name),
                          supplier_key=supplier_key):
            matched_fields.append(field_name)
            score += points
            reasons.append(f"{field_name} coerente")

    matched = set(matched_fields)
    strong_patterns = [
        {"cdq"},
        {"colata", "diametro", "peso"},
        {"ordine", "lega", "diametro", "colata"},
    ]
    if arconic_pair:
        strong_patterns.extend(
            [
                {"colata", "customer_code", "article_code"},
                {"colata", "ddt", "article_code"},
                {"ddt", "line_no", "customer_code", "colata"},
                {"ddt", "line_no", "article_code", "colata"},
            ]
        )
    if grupa_kety_pair:
        # Grupa Kety can have one DDT with many certificate rows. Heat/colata
        # is the row anchor; common DDT/order data must not link all rows.
        strong_patterns = [{"colata", "ddt"}, {"colata", "ordine"}, {"colata", "lega"}]
    if leichtmetall_pair:
        # Leichtmetall can repeat the same batch/cdq and diameter across
        # different deliveries. The row discriminator is weight and/or purchase
        # number, so cdq alone must never auto-link a certificate.
        strong_patterns = [
            {"cdq", "diametro", "peso"},
            {"colata", "diametro", "peso"},
            {"cdq", "diametro", "ordine"},
            {"colata", "diametro", "ordine"},
        ]
    has_strong_pattern = any(pattern.issubset(matched) for pattern in strong_patterns)

    if grupa_kety_pair and "colata" not in matched:
        return RematchScore(
            decision=RematchDecision.NONE,
            score=score,
            matched_fields=tuple(matched_fields),
            blockers=(),
            reasons=tuple(reasons),
        )

    # Lega alone, or only weak supports, must never create a rematch proposal.
    material_fields = {"colata", "diametro", "peso", "ordine", "cdq"}
    if arconic_pair:
        material_fields.update({"article_code", "customer_code", "line_no", "supplier_order_no", "lot_batch_no"})
    material_support_count = len(matched & material_fields)
    if leichtmetall_pair and not (matched & {"peso", "ordine"}):
        return RematchScore(
            decision=RematchDecision.NONE,
            score=score,
            matched_fields=tuple(matched_fields),
            blockers=(),
            reasons=tuple(reasons),
        )
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
    supplier_key: str | None,
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
        supplier_key=supplier_key,
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


def _is_arconic_bridge_pair(left: RematchBridge, right: RematchBridge) -> bool:
    if "arconic_hannover" in {left.supplier_key, right.supplier_key}:
        return True
    left_name = _compact_text(left.value("fornitore") or left.supplier_name)
    right_name = _compact_text(right.value("fornitore") or right.supplier_name)
    names = [name for name in (left_name, right_name) if name]
    return any("ARCONIC" in name or "ALCOA" in name for name in names)


def _is_grupa_kety_bridge_pair(left: RematchBridge, right: RematchBridge) -> bool:
    if "grupa_kety" in {left.supplier_key, right.supplier_key}:
        return True
    left_name = _compact_text(left.value("fornitore") or left.supplier_name)
    right_name = _compact_text(right.value("fornitore") or right.supplier_name)
    names = [name for name in (left_name, right_name) if name]
    return any("GRUPAKETY" in name or name == "KETY" for name in names)


def _is_leichtmetall_bridge_pair(left: RematchBridge, right: RematchBridge) -> bool:
    if "leichtmetall" in {left.supplier_key, right.supplier_key}:
        return True
    left_name = _compact_text(left.value("fornitore") or left.supplier_name)
    right_name = _compact_text(right.value("fornitore") or right.supplier_name)
    names = [name for name in (left_name, right_name) if name]
    return any("LEICHTMETALL" in name for name in names)


def _bridge_supplier_key(left: RematchBridge, right: RematchBridge) -> str | None:
    template = resolve_supplier_template(left.supplier_name, right.supplier_name,
                                         left.value("fornitore"), right.value("fornitore"))
    return left.supplier_key or right.supplier_key or (template.supplier_key if template else None)


def _hard_blockers(left: RematchBridge, right: RematchBridge) -> tuple[str, ...]:
    blockers: list[str] = []
    hard_fields = ["colata", "diametro"]
    supplier_key = _bridge_supplier_key(left, right)
    # A high bridge score cannot override contradictions already rejected by
    # the supplier's initial matcher. Missing data stays missing: no additional
    # required anchors, family-wide alloy substitutions or score changes here.
    hard_fields.extend({
        "metalba": ("lega", "peso", "ordine"),
        "impol": ("lega", "peso", "ordine"),
        "leichtmetall": ("lega",),
        "neuman": ("lega", "peso", "article_code"),
        "aww": ("lega", "peso", "ordine", "article_code", "profile_code", "order_confirmation_root"),
        "arconic_hannover": ("ddt", "ordine"),
        "grupa_kety": ("lega",),
    }.get(supplier_key, ()))
    if _is_leichtmetall_bridge_pair(left, right):
        # Leichtmetall DDTs may contain multiple rows and duplicated cdq/diameter
        # across deliveries. If present on both sides, these fields identify the
        # exact row and conflicting values must prevent auto-rematch.
        hard_fields.extend(["cdq", "peso", "ordine"])
    for field_name in hard_fields:
        left_value = left.value(field_name)
        right_value = right.value(field_name)
        if left_value is None or right_value is None:
            continue
        matches = _field_matches(field_name, left_value, right_value, supplier_key=supplier_key)
        if field_name == "ordine" and supplier_key == "metalba" and not matches:
            # Old confirmed Incoming values can contain only the numeric order
            # root (169) while Vs.Rif. retains 169/26. Absence of the year is
            # not a contradiction and earns no new score; two supplied but
            # different years, or different roots, still block the rematch.
            left_order = re.fullmatch(r"\s*(\d+)\s*(?:/\s*(\d{2}|20\d{2}))?\s*", left_value)
            right_order = re.fullmatch(r"\s*(\d+)\s*(?:/\s*(\d{2}|20\d{2}))?\s*", right_value)
            if left_order and right_order and left_order[1] == right_order[1]:
                left_year, right_year = left_order[2], right_order[2]
                matches = not left_year or not right_year or left_year[-2:] == right_year[-2:]
        if field_name == "peso" and supplier_key in {"metalba", "impol", "aww", "neuman"}:
            # Keep the existing supplier tolerances, not the bridge's tighter
            # bonus threshold (which is intentionally unchanged).
            weight_matcher = {"aww": aww_weights_are_compatible,
                              "neuman": neuman_weights_are_compatible}.get(supplier_key, weights_are_compatible)
            matches = weight_matcher(left_value, right_value)
        if not matches:
            blockers.append(f"{field_name} diverso")
    return tuple(blockers)


def _field_matches(field_name: str, left: str | None, right: str | None,
                   *, supplier_key: str | None = None) -> bool:
    if left is None or right is None:
        return False
    if field_name == "lega":
        if supplier_key == "metalba":
            return metalba_same_source_alloy(_normalize_alloy(left), _normalize_alloy(right))
        return _normalize_alloy(left) == _normalize_alloy(right)
    if field_name == "diametro":
        return _normalize_number(left) == _normalize_number(right)
    if field_name == "peso":
        return _weights_match(left, right)
    if field_name == "colata":
        return _normalize_primary_code(left) == _normalize_primary_code(right)
    if field_name == "order_confirmation_root":
        left_root = _normalize_order_confirmation_root(left)
        right_root = _normalize_order_confirmation_root(right)
        return bool(left_root and right_root and left_root == right_root)
    if field_name in {"cdq", "ordine", "ddt", "article_code", "customer_code", "line_no", "supplier_order_no", "lot_batch_no"}:
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
    text = re.split(r"[\s(;/|]+", text.strip(), maxsplit=1)[0]
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
