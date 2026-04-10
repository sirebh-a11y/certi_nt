from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


TableOrientation = Literal["horizontal", "vertical", "unknown"]
LineRole = Literal["header", "min", "max", "measured", "noise"]

MIN_MARKERS = ("min", "soll min", "set value min", "valeur min")
MAX_MARKERS = ("max", "set value max", "soll max", "valeur max")
MEASURED_MARKERS = ("ist/act", "charge no", "charge nr", "coulée no", "value", "valeur", "charge")
IGNORE_MARKERS = ("mechanical", "notes", "remark", "alloy", "customer", "delivery", "certificate")


@dataclass(frozen=True)
class TableWindowAnalysis:
    orientation: TableOrientation
    header_line_index: int | None
    measured_line_indices: tuple[int, ...] = field(default_factory=tuple)
    min_line_indices: tuple[int, ...] = field(default_factory=tuple)
    max_line_indices: tuple[int, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


def classify_line_role(line: str) -> LineRole:
    lowered = line.casefold().strip()
    if not lowered:
        return "noise"
    if any(marker in lowered for marker in MIN_MARKERS):
        return "min"
    if any(marker in lowered for marker in MAX_MARKERS):
        return "max"
    if any(marker in lowered for marker in MEASURED_MARKERS):
        return "measured"
    if re.search(r"\b(si|fe|cu|mn|mg|cr|ni|zn|ti|pb|v|bi|sn|zr|be)\b", lowered):
        return "header"
    if re.search(r"(rp0\.?2|rm|hb|a%|proof|tensile|elongation|brinell)", lowered):
        return "header"
    return "noise"


def analyze_measurement_table(lines: list[str]) -> TableWindowAnalysis:
    header_line_index: int | None = None
    measured: list[int] = []
    mins: list[int] = []
    maxes: list[int] = []
    vertical_score = 0
    horizontal_score = 0

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        role = classify_line_role(line)
        if role == "header" and header_line_index is None:
            header_line_index = index
        elif role == "min":
            mins.append(index)
        elif role == "max":
            maxes.append(index)
        elif role == "measured":
            measured.append(index)

        if _looks_like_horizontal_header(line):
            horizontal_score += 2
        if _looks_like_vertical_axis(line):
            vertical_score += 2

    if header_line_index is not None and measured:
        horizontal_score += 1
    if vertical_score > horizontal_score:
        orientation: TableOrientation = "vertical"
    elif horizontal_score > 0:
        orientation = "horizontal"
    else:
        orientation = "unknown"

    notes: list[str] = []
    if mins or maxes:
        notes.append("Tabella con limiti min/max rilevati")
    if measured:
        notes.append("Riga/asse misurato individuato")
    if orientation == "unknown":
        notes.append("Orientamento tabella non determinato con sicurezza")

    return TableWindowAnalysis(
        orientation=orientation,
        header_line_index=header_line_index,
        measured_line_indices=tuple(measured),
        min_line_indices=tuple(mins),
        max_line_indices=tuple(maxes),
        notes=tuple(notes),
    )


def choose_measured_lines(lines: list[str]) -> list[str]:
    analysis = analyze_measurement_table(lines)
    if analysis.measured_line_indices:
        return [lines[index] for index in analysis.measured_line_indices]

    selected: list[str] = []
    for line in lines:
        lowered = line.casefold().strip()
        if not lowered:
            continue
        if any(marker in lowered for marker in IGNORE_MARKERS):
            continue
        if any(marker in lowered for marker in MIN_MARKERS + MAX_MARKERS):
            continue
        if re.search(r"\d", line):
            selected.append(line)
    return selected


def _looks_like_horizontal_header(line: str) -> bool:
    tokens = re.findall(r"\b[A-Z][a-z]?(?:\+[A-Z][a-z]?)?\b", line)
    return len(tokens) >= 3


def _looks_like_vertical_axis(line: str) -> bool:
    lowered = line.casefold()
    return bool(
        re.match(r"^(si|fe|cu|mn|mg|cr|ni|zn|ti|pb|v|bi|sn|zr|be)\b", lowered)
        or re.match(r"^(rm|rp0\.?2|hb|a%|iacs%)\b", lowered)
    )
