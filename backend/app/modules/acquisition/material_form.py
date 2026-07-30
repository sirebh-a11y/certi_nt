from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Literal

from app.modules.acquisition.models import AcquisitionRow, DocumentEvidence


MaterialFormCode = Literal[
    "BILLETTE",
    "BARRE",
    "PROFILI",
    "ESTRUSO_GENERICO",
    "DA_VERIFICARE",
    "DATI_DISCORDANTI",
]

MATERIAL_FORM_LABELS: dict[MaterialFormCode, str] = {
    "BILLETTE": "Billetta",
    "BARRE": "Barra",
    "PROFILI": "Profilo",
    "ESTRUSO_GENERICO": "Estruso - forma da verificare",
    "DA_VERIFICARE": "Materiale da verificare",
    "DATI_DISCORDANTI": "Dati materiale discordanti",
}

_MATERIAL_DESCRIPTION_KEYS = {
    "articledescriptionraw",
    "customeritemdescriptionraw",
    "descrizionemateriale",
    "descrizioneprodotto",
    "itemdescriptionraw",
    "materialdescriptionraw",
    "materialraw",
    "productdescription",
    "productdescriptionraw",
    "productraw",
}

_BILLET_PATTERN = re.compile(
    r"\b(?:billets?|billett(?:a|e|es)|(?:strangpress|press)bolzen)\b",
    re.IGNORECASE,
)
_BAR_PATTERN = re.compile(
    r"\b(?:"
    r"round\s+bars?|extruded\s+bars?|bars?|barra|barre|rods?|"
    r"rundstang(?:e|en)|stang(?:e|en)"
    r")\b",
    re.IGNORECASE,
)
_PROFILE_PATTERN = re.compile(
    r"\b(?:profiles?|profili|profilo|profilati|profilés?|sections?|sezioni)\b",
    re.IGNORECASE,
)
_EXTRUDED_PATTERN = re.compile(
    r"\b(?:"
    r"estrus(?:o|a|i|e)|extrud(?:ed|ate|ates|ation|ations|iert|é|ée|és|ées)|"
    r"extrus(?:ion|ions)|extrusi(?:on|ón|ones)|strangpress\w*"
    r")\b",
    re.IGNORECASE,
)
_ROUND_BAR_BILLET_EQUIVALENCE_PATTERN = re.compile(
    r"\b(?:aluminium\s+)?round\s*bars?\s*\(\s*billets?\s*\)",
    re.IGNORECASE,
)
_CAST_BILLET_PROCESS_PATTERN = re.compile(
    r"\b(?:cast|casted|homogeni[sz]ed|scalped|turned)\b",
    re.IGNORECASE,
)
_STRONG_OCR_MATERIAL_LINE_PATTERNS = (
    _ROUND_BAR_BILLET_EQUIVALENCE_PATTERN,
)


@dataclass(frozen=True)
class MaterialFormAssessment:
    code: MaterialFormCode
    label: str
    evidence: tuple[str, ...] = ()
    detected_forms: tuple[MaterialFormCode, ...] = ()

    @property
    def primary_evidence(self) -> str | None:
        return self.evidence[0] if self.evidence else None


def _material_description_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _iter_ai_material_descriptions(payload: object) -> Iterable[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _material_description_key(key) in _MATERIAL_DESCRIPTION_KEYS and isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    yield cleaned
                continue
            if isinstance(value, (dict, list)):
                yield from _iter_ai_material_descriptions(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _iter_ai_material_descriptions(value)


def material_description_candidates(row: AcquisitionRow) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def append(value: object) -> None:
        cleaned = str(value or "").strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            return
        seen.add(key)
        candidates.append(cleaned)

    for value in getattr(row, "values", None) or []:
        if _material_description_key(value.campo) not in _MATERIAL_DESCRIPTION_KEYS:
            continue
        if value.metodo_lettura != "chatgpt":
            continue
        append(value.valore_finale or value.valore_standardizzato or value.valore_grezzo)

    evidences: list[DocumentEvidence] = list(getattr(row, "evidences", None) or [])
    for document in (getattr(row, "ddt_document", None), getattr(row, "certificate_document", None)):
        if document is not None:
            evidences.extend(getattr(document, "evidences", None) or [])

    processed_evidence_ids: set[int] = set()
    for evidence in evidences:
        if evidence.id is not None and evidence.id in processed_evidence_ids:
            continue
        if evidence.id is not None:
            processed_evidence_ids.add(evidence.id)
        if evidence.tipo_evidenza != "ai_payload" or evidence.metodo_estrazione != "chatgpt":
            continue
        raw_payload = (evidence.testo_grezzo or "").strip()
        if not raw_payload.startswith(("{", "[")):
            continue
        try:
            payload = json.loads(raw_payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for description in _iter_ai_material_descriptions(payload):
            append(description)

    # Historical documents may predate the AI product-description field. Only
    # accept narrowly structured product wording here: never generic bar/billet
    # occurrences, which could come from UT notes or table headers.
    for document in (getattr(row, "ddt_document", None), getattr(row, "certificate_document", None)):
        if document is None:
            continue
        for page in getattr(document, "pages", None) or []:
            page_text = str(
                getattr(page, "ocr_text", None)
                or getattr(page, "testo_estratto", None)
                or ""
            )
            for raw_line in page_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if any(pattern.search(line) for pattern in _STRONG_OCR_MATERIAL_LINE_PATTERNS):
                    append(line)

    return candidates


def classify_material_description(value: str) -> MaterialFormCode | None:
    has_bar = bool(_BAR_PATTERN.search(value))
    has_profile = bool(_PROFILE_PATTERN.search(value))
    has_billet = bool(_BILLET_PATTERN.search(value))
    has_extruded = bool(_EXTRUDED_PATTERN.search(value))

    if has_bar and has_billet:
        # Leichtmetall uses "roundbars (billets)" for cylindrical cast billets.
        # Extrusion wording instead identifies a finished bar made from a billet.
        if has_extruded:
            return "BARRE"
        if _ROUND_BAR_BILLET_EQUIVALENCE_PATTERN.search(value) or _CAST_BILLET_PROCESS_PATTERN.search(value):
            return "BILLETTE"
        return "DATI_DISCORDANTI"

    # A finished form is stronger than a separate reference to its source billet.
    if has_bar and not has_profile:
        return "BARRE"
    if has_profile and not has_bar:
        return "PROFILI"
    if has_bar and has_profile:
        return "DATI_DISCORDANTI"
    if has_billet:
        return "BILLETTE"
    if has_extruded:
        return "ESTRUSO_GENERICO"
    return None


def assess_material_form(row: AcquisitionRow) -> MaterialFormAssessment:
    candidates = material_description_candidates(row)
    classified: list[tuple[MaterialFormCode, str]] = []
    for candidate in candidates:
        form = classify_material_description(candidate)
        if form is not None:
            classified.append((form, candidate[:500]))

    specific_forms = {
        form
        for form, _ in classified
        if form in {"BILLETTE", "BARRE", "PROFILI", "DATI_DISCORDANTI"}
    }
    if "DATI_DISCORDANTI" in specific_forms or len(specific_forms) > 1:
        evidence = tuple(dict.fromkeys(value for _, value in classified))
        return MaterialFormAssessment(
            code="DATI_DISCORDANTI",
            label=MATERIAL_FORM_LABELS["DATI_DISCORDANTI"],
            evidence=evidence,
            detected_forms=tuple(sorted(specific_forms)),
        )
    if specific_forms:
        code = next(iter(specific_forms))
        evidence = tuple(dict.fromkeys(value for form, value in classified if form == code))
        return MaterialFormAssessment(
            code=code,
            label=MATERIAL_FORM_LABELS[code],
            evidence=evidence,
            detected_forms=(code,),
        )
    generic_evidence = tuple(
        dict.fromkeys(value for form, value in classified if form == "ESTRUSO_GENERICO")
    )
    if generic_evidence:
        return MaterialFormAssessment(
            code="ESTRUSO_GENERICO",
            label=MATERIAL_FORM_LABELS["ESTRUSO_GENERICO"],
            evidence=generic_evidence,
            detected_forms=("ESTRUSO_GENERICO",),
        )
    return MaterialFormAssessment(
        code="DA_VERIFICARE",
        label=MATERIAL_FORM_LABELS["DA_VERIFICARE"],
        evidence=tuple(candidates[:5]),
    )


def legacy_material_form_assessment(row: AcquisitionRow) -> tuple[bool, str | None, str | None, bool]:
    assessment = assess_material_form(row)
    if assessment.code == "BILLETTE":
        return True, assessment.primary_evidence, None, False
    if assessment.code in {"BARRE", "PROFILI", "ESTRUSO_GENERICO"}:
        return False, None, assessment.primary_evidence, False
    return False, None, None, True
