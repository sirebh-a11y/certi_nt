from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IncomingChemistryLimit:
    element: str
    min_value: float | None
    max_value: float | None
    max_inclusive: bool = True


@dataclass(frozen=True)
class IncomingChemistryProfile:
    code: str
    label: str
    base_alloy: str
    match_any: tuple[str, ...]
    limits: tuple[IncomingChemistryLimit, ...]
    source: str
    version: str


def _key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _alloy_key(*values: object) -> str | None:
    for value in values:
        cleaned = str(value or "").strip().upper()
        if not cleaned:
            continue
        cleaned = re.sub(r"\bEN\s*[- ]?\s*AW\b", " ", cleaned)
        cleaned = re.sub(r"\bAA\b", " ", cleaned)
        for token in re.findall(r"[0-9A-Z]+", cleaned):
            match = re.match(r"^([0-9]{4})([A-Z]?)", token)
            if not match:
                continue
            number, suffix = match.groups()
            if number in {"2017", "2618", "6005", "6110"} and suffix == "A":
                return f"{number}A"
            return number
    return None


@lru_cache(maxsize=1)
def incoming_chemistry_profiles() -> tuple[IncomingChemistryProfile, ...]:
    path = Path(__file__).with_name("data") / "incoming_chemistry_profiles.json"
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    source = str(payload["source"])
    version = str(payload["version"])
    profiles: list[IncomingChemistryProfile] = []
    for item in payload["profiles"]:
        limits = tuple(
            IncomingChemistryLimit(
                element=element,
                min_value=float(values["min"]) if values.get("min") is not None else None,
                max_value=float(values["max"]) if values.get("max") is not None else None,
                max_inclusive=bool(values.get("max_inclusive", True)),
            )
            for element, values in item["limits"].items()
        )
        profiles.append(
            IncomingChemistryProfile(
                code=str(item["code"]),
                label=str(item["label"]),
                base_alloy=str(item["base_alloy"]),
                match_any=tuple(_key(value) for value in item.get("match_any", [])),
                limits=limits,
                source=source,
                version=version,
            )
        )
    return tuple(profiles)


def find_incoming_chemistry_profile(
    *,
    lega_base: str | None,
    lega_designazione: str | None,
    variante_lega: str | None,
) -> IncomingChemistryProfile | None:
    values = (lega_base, lega_designazione, variante_lega)
    alloy = _alloy_key(*values)
    if alloy is None:
        return None
    combined = _key(" ".join(value for value in values if value))
    candidates = [profile for profile in incoming_chemistry_profiles() if profile.base_alloy == alloy]
    for profile in candidates:
        if profile.match_any and any(token in combined for token in profile.match_any):
            return profile
    return next((profile for profile in candidates if not profile.match_any), None)


def incoming_chemistry_value_is_inside(value: float, limit: IncomingChemistryLimit) -> bool:
    epsilon = 1e-9
    if limit.min_value is not None and value + epsilon < limit.min_value:
        return False
    if limit.max_value is not None:
        if limit.max_inclusive and value - epsilon > limit.max_value:
            return False
        if not limit.max_inclusive and value + epsilon >= limit.max_value:
            return False
    return True
