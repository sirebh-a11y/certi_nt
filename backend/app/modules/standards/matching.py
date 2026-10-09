from __future__ import annotations

import re
import math
from dataclasses import dataclass
from typing import Any, Iterable

from app.modules.acquisition.material_form import MaterialFormAssessment, assess_material_form


@dataclass(frozen=True)
class RankedStandard:
    standard: Any
    score: int
    confidence: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    compatible_material_rows: int
    total_material_rows: int


def _text(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def normalize_alloy(value: Any) -> str | None:
    cleaned = _text(value)
    if not cleaned:
        return None
    normalized = re.sub(r"\bEN\s*[- ]?\s*AW\b", " ", cleaned.upper())
    normalized = re.sub(r"\bAW\b", " ", normalized)
    tokens = re.findall(r"[0-9A-Z]+", normalized)
    for index, token in enumerate(tokens):
        match = re.match(r"^([0-9]{4})([A-Z0-9]*)$", token)
        if not match:
            continue
        number, suffix = match.groups()
        suffix_from_same_token = bool(suffix)
        if not suffix and index + 1 < len(tokens):
            next_token = tokens[index + 1]
            if next_token in {"H", "L"} and len(tokens) <= 2:
                suffix = next_token
                suffix_from_same_token = True
            elif next_token in {"F", "T4", "T42", "T6", "T62", "T64", "T651", "T76", "HF", "LF"}:
                suffix = next_token
        if number == "6082" and suffix.startswith("HF"):
            return "6082H"
        if number == "6082" and suffix.startswith("LF"):
            return "6082L"
        if suffix in {"", "F", "T4", "T42", "T6", "T62", "T64", "T651", "T76"}:
            return number
        if number == "6082" and suffix_from_same_token and suffix[:1] in {"H", "L"}:
            return f"{number}{suffix[:1]}"
        return f"{number}A" if suffix[:1] == "A" else number
    return re.sub(r"[^0-9A-Za-z]", "", cleaned).upper() or None


def normalize_standard_product_type(value: Any) -> str | None:
    normalized = _key(value)
    if normalized in {"billetta", "billette", "billet", "billets"}:
        return "BILLETTE"
    if normalized in {"barra", "barre", "bar", "bars", "rod", "rods"}:
        return "BARRE"
    if normalized in {"profilo", "profili", "profile", "profiles", "sezione", "sezioni"}:
        return "PROFILI"
    return None


def _row_alloy(row: Any) -> str | None:
    return normalize_alloy(
        getattr(row, "lega_base", None)
        or getattr(row, "lega_designazione", None)
        or getattr(row, "variante_lega", None)
    )


def _standard_alloy(standard: Any) -> str | None:
    return normalize_alloy(
        getattr(standard, "lega_base", None)
        or getattr(standard, "lega_designazione", None)
    )


def _extract_temper(*values: Any) -> str | None:
    for value in values:
        cleaned = _text(value)
        if not cleaned:
            continue
        match = re.search(r"\bT(?:4|42|6|62|64|651|76)\b", cleaned.upper())
        if match:
            return match.group(0)
    return None


def _numeric(value: Any) -> float | None:
    cleaned = _text(value)
    if not cleaned:
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", cleaned.replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def material_form_summary(rows: Iterable[Any]) -> list[MaterialFormAssessment]:
    return [assess_material_form(row) for row in rows]


def rank_standard_candidates(
    standards: Iterable[Any],
    *,
    rows: list[Any],
    elongation_overrides: dict[int, Any] | None = None,
) -> list[RankedStandard]:
    if not rows:
        return []
    standards = list(standards)

    assessments = material_form_summary(rows)
    row_alloys = [_row_alloy(row) for row in rows]
    known_alloys = [value for value in row_alloys if value]
    distinct_alloys = sorted(set(known_alloys))
    row_tempers = {
        value
        for row in rows
        if (
            value := _extract_temper(
                getattr(row, "lega_designazione", None),
                getattr(row, "lega_base", None),
                getattr(row, "variante_lega", None),
            )
        )
    }
    row_variants = {
        _key(value)
        for row in rows
        if (value := _text(getattr(row, "variante_lega", None)))
    }
    has_diameter = any(_numeric(getattr(row, "diametro", None)) is not None for row in rows)

    ranked_data: list[tuple[int, Any, list[str], list[str], int, int]] = []
    for standard in standards:
        reasons: list[str] = []
        warnings: list[str] = []
        score = 0
        standard_alloy = _standard_alloy(standard)
        compatible_alloy_rows = sum(1 for alloy in known_alloys if alloy == standard_alloy)
        if known_alloys and compatible_alloy_rows == 0:
            continue
        if known_alloys:
            alloy_coverage = compatible_alloy_rows / len(known_alloys)
            score += round(50 * alloy_coverage)
            if alloy_coverage == 1:
                reasons.append(f"lega {standard_alloy}")
            else:
                warnings.append(
                    f"lega compatibile con {compatible_alloy_rows} righe su {len(known_alloys)}"
                )
            if len(distinct_alloys) > 1:
                warnings.append(f"nell'OL sono presenti leghe diverse: {', '.join(distinct_alloys)}")
        else:
            warnings.append("lega non rilevata nei dati Incoming")

        standard_form = normalize_standard_product_type(getattr(standard, "tipo_prodotto", None))
        specific_assessments = [
            item for item in assessments if item.code in {"BILLETTE", "BARRE", "PROFILI"}
        ]
        compatible_form_rows = 0
        if specific_assessments:
            if standard_form is None:
                warnings.append("tipo prodotto non specificato nello standard")
            else:
                compatible_form_rows = sum(1 for item in specific_assessments if item.code == standard_form)
                form_coverage = compatible_form_rows / len(specific_assessments)
                score += round(25 * form_coverage)
                if form_coverage == 1:
                    reasons.append(f"forma materiale {standard_form.lower()}")
                else:
                    score -= round(15 * (1 - form_coverage))
                    warnings.append(
                        f"forma materiale compatibile con {compatible_form_rows} righe su {len(specific_assessments)}"
                    )
        else:
            uncertain_labels = sorted({item.label for item in assessments})
            warnings.append(f"forma materiale da confermare: {', '.join(uncertain_labels)}")

        measure_type = _key(getattr(standard, "misura_tipo", None))
        if has_diameter:
            if measure_type == "diametro":
                score += 15
                reasons.append("misura diametro")
            elif measure_type:
                score -= 5
                warnings.append(f"misura standard {getattr(standard, 'misura_tipo', None)} diversa dal diametro rilevato")

        standard_temper = _extract_temper(getattr(standard, "trattamento_termico", None))
        if row_tempers and standard_temper:
            if standard_temper in row_tempers:
                score += 10
                reasons.append(f"stato {standard_temper}")
            else:
                score -= 10
                warnings.append(
                    f"stato standard {standard_temper} diverso da {', '.join(sorted(row_tempers))}"
                )

        standard_variant = _key(getattr(standard, "variante_lega", None))
        if standard_variant:
            if row_variants and standard_variant in row_variants:
                score += 10
                reasons.append(f"variante {getattr(standard, 'variante_lega', None)}")
            elif not row_variants:
                score -= 5
                warnings.append(
                    f"variante {getattr(standard, 'variante_lega', None)} non rilevata nella riga"
                )

        if not getattr(standard, "property_limits", None):
            warnings.append("proprietà standard non presenti")
        if not getattr(standard, "chemistry_limits", None):
            warnings.append("chimica standard non presente")

        adjustment, elongation_reasons, elongation_warnings = _elongation_preference(
            standard, standards, rows, assessments, elongation_overrides or {}
        )
        score += adjustment
        reasons.extend(elongation_reasons)
        warnings.extend(elongation_warnings)

        ranked_data.append(
            (
                score,
                standard,
                list(dict.fromkeys(reasons)),
                list(dict.fromkeys(warnings)),
                compatible_form_rows,
                len(specific_assessments),
            )
        )

    ranked_data.sort(
        key=lambda item: (
            item[0],
            -len(item[3]),
            len(getattr(item[1], "chemistry_limits", None) or [])
            + len(getattr(item[1], "property_limits", None) or []),
        ),
        reverse=True,
    )
    top_score = ranked_data[0][0] if ranked_data else 0
    result: list[RankedStandard] = []
    for index, (score, standard, reasons, warnings, compatible_rows, total_rows) in enumerate(ranked_data):
        next_score = ranked_data[index + 1][0] if index + 1 < len(ranked_data) else None
        previous_score = ranked_data[index - 1][0] if index > 0 else None
        nearest_score = previous_score if previous_score is not None else next_score
        gap = abs(score - nearest_score) if nearest_score is not None else 99
        if score >= 90 and gap >= 15 and not warnings:
            confidence = "alta"
        elif score >= 65 and gap >= 5:
            confidence = "media"
        else:
            confidence = "bassa"
        if score == top_score and sum(1 for item in ranked_data if item[0] == top_score) > 1:
            confidence = "bassa"
            warnings = [*warnings, "più standard hanno lo stesso punteggio"]
        result.append(
            RankedStandard(
                standard=standard,
                score=score,
                confidence=confidence,
                reasons=tuple(reasons),
                warnings=tuple(dict.fromkeys(warnings)),
                compatible_material_rows=compatible_rows,
                total_material_rows=total_rows,
            )
        )
    return result


def _strict_number(value):
    text = str(value if value is not None else "").strip().replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    number = float(text)
    return number if math.isfinite(number) else None


def _elongation_reading(row, overrides):
    values = [v for v in getattr(row, "values", []) if _key(getattr(v, "blocco", "")) == "proprieta"
              and _key(getattr(v, "campo", "")) in {"a", "a5", "a50", "a50mm"}]
    if not values and getattr(row, "id", None) in overrides:
        return _strict_number(overrides[row.id]), None
    if len(values) != 1:
        return None, None
    value = values[0]
    raw = next((getattr(value, k, None) for k in ("valore_finale", "valore_standardizzato", "valore_grezzo")
                if getattr(value, k, None) is not None), None)
    if getattr(row, "id", None) in overrides:
        raw = overrides[row.id]
    # A% is the canonical storage key, NOT evidence of a proportional test.
    field = _key(getattr(value, "campo", ""))
    basis = "A50mm" if field in {"a50", "a50mm"} else "A" if field == "a5" else None
    evidence = getattr(value, "primary_evidence", None)
    source = str(getattr(evidence, "testo_grezzo", "") or "").strip()
    method = str(getattr(evidence, "metodo_estrazione", "") or "").lower()
    # Only bounded, directly associated OCR excerpts, never normalized AI JSON
    # or an entire document containing several tables/methods.
    if source and len(source) <= 200 and not source.startswith(("{", "[")) and "ocr" in method:
        fixed = bool(re.search(r"\bA\s*50\s*(?:mm)?\s*\(?\s*%", source, re.I))
        proportional = bool(re.search(r"\bA\s*(?:5\s*)?\(?\s*%", source, re.I))
        if fixed and proportional:
            basis = "conflict"
        elif fixed:
            basis = "conflict" if basis == "A" else "A50mm"
        elif proportional:
            basis = "conflict" if basis == "A50mm" else "A"
    return _strict_number(raw), basis


def _elongation_limit(standard, diameter):
    candidates = []
    for prop in getattr(standard, "property_limits", []):
        if _key(getattr(prop, "proprieta", "")) != "a":
            continue
        lower, upper = prop.misura_min, prop.misura_max
        if (lower is None or diameter > lower) and (upper is None or diameter <= upper):
            candidates.append(prop)
    if len(candidates) != 1 or candidates[0].min_value is None:
        return None
    return candidates[0]


def _elongation_preference(standard, standards, rows, assessments, overrides):
    basis = getattr(standard, "elongation_basis", None)
    if basis not in {"A", "A50mm"} or _standard_alloy(standard) != "7003":
        return 0, [], []
    # Unknown/incompatible material never gains confidence from a low number.
    eligible = all(_row_alloy(row) == "7003" and assessment.code == "BARRE"
                   for row, assessment in zip(rows, assessments))
    eligible &= normalize_standard_product_type(standard.tipo_prodotto) == "BARRE"
    eligible &= _key(standard.misura_tipo) == "diametro"
    eligible &= all(_key(getattr(row, "variante_lega", None)) in
                    {"", _key(getattr(standard, "variante_lega", None))} for row in rows)
    eligible &= all((_extract_temper(row.lega_designazione, row.lega_base, row.variante_lega) in
                     {None, _extract_temper(standard.trattamento_termico)}) for row in rows)
    fallback = (-40, [], ["A50mm non deducibile automaticamente: verificare il tipo di prova."]) if basis == "A50mm" else (0, [], [])
    if not eligible:
        return fallback
    samples = []
    for row in rows:
        diameter = _strict_number(getattr(row, "diametro", None))
        value, source_basis = _elongation_reading(row, overrides)
        limit = _elongation_limit(standard, diameter) if diameter and diameter > 0 else None
        if value is None or limit is None or source_basis == "conflict":
            return fallback
        samples.append((diameter, value, source_basis, limit))
    sources = {s[2] for s in samples if s[2]}
    if len(sources) > 1:
        return -40, [], ["Tipi di prova allungamento diversi tra le righe: verificare manualmente."]
    if sources:
        if sources == {basis} and all(s[2] == basis for s in samples):
            return 35, [f"tipo di prova {basis} presente nelle evidenze"], []
        if basis not in sources:
            return -40, [], [f"Il tipo di prova letto non corrisponde a {basis}."]
    if basis == "A":
        return 15, ["standard A ordinario; eventuali fuori limite restano visibili"], []
    ordinary = [s for s in standards if getattr(s, "elongation_basis", None) == "A"
                and _standard_alloy(s) == "7003"
                and all(_key(getattr(s, f, None)) == _key(getattr(standard, f, None))
                        for f in ("norma", "trattamento_termico", "tipo_prodotto", "misura_tipo", "variante_lega"))]
    if len(ordinary) != 1:
        return fallback
    below_ordinary = False
    for diameter, value, source_basis, limit in samples:
        reference = _elongation_limit(ordinary[0], diameter)
        if reference is None or source_basis == "A" or value < limit.min_value or (limit.max_value is not None and value > limit.max_value):
            return fallback
        below_ordinary |= value < reference.min_value
    if not below_ordinary:
        return fallback
    return 35, ["allungamento compatibile con A50mm, sotto il minimo di A"], [
        "Proposto standard A50mm: l'allungamento rientra nei suoi limiti, ma non in quelli di A. "
        "Verifica il tipo di prova nel certificato prima di confermare."
    ]
