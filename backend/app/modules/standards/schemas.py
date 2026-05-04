from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ValidationState = Literal["attivo", "da_verificare", "bozza"]


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class StandardChemistryPayload(BaseModel):
    elemento: str = Field(min_length=1, max_length=32)
    min_value: float | None = None
    max_value: float | None = None

    @field_validator("elemento")
    @classmethod
    def normalize_element(cls, value: str) -> str:
        return value.strip()


class StandardPropertyPayload(BaseModel):
    proprieta: str = Field(min_length=1, max_length=64)
    misura_min: float | None = None
    misura_max: float | None = None
    range_label: str | None = Field(default=None, max_length=128)
    min_value: float | None = None
    max_value: float | None = None

    @field_validator("proprieta", "range_label")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class StandardBasePayload(BaseModel):
    code: str = Field(min_length=1, max_length=160)
    lega_base: str = Field(min_length=1, max_length=64)
    lega_designazione: str = Field(min_length=1, max_length=128)
    variante_lega: str | None = Field(default=None, max_length=128)
    norma: str | None = Field(default=None, max_length=128)
    trattamento_termico: str | None = Field(default=None, max_length=64)
    tipo_prodotto: str | None = Field(default=None, max_length=64)
    misura_tipo: str | None = Field(default=None, max_length=32)
    fonte_excel_foglio: str | None = Field(default=None, max_length=128)
    fonte_excel_blocco: str | None = Field(default=None, max_length=255)
    stato_validazione: ValidationState = "attivo"
    note: str | None = None

    @field_validator(
        "code",
        "lega_base",
        "lega_designazione",
        "variante_lega",
        "norma",
        "trattamento_termico",
        "tipo_prodotto",
        "misura_tipo",
        "fonte_excel_foglio",
        "fonte_excel_blocco",
        "note",
    )
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class StandardCreateRequest(StandardBasePayload):
    chemistry: list[StandardChemistryPayload] = Field(default_factory=list)
    properties: list[StandardPropertyPayload] = Field(default_factory=list)


class StandardUpdateRequest(StandardBasePayload):
    chemistry: list[StandardChemistryPayload] = Field(default_factory=list)
    properties: list[StandardPropertyPayload] = Field(default_factory=list)


class StandardChemistryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    elemento: str
    min_value: float | None
    max_value: float | None


class StandardPropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proprieta: str
    misura_min: float | None
    misura_max: float | None
    range_label: str | None
    min_value: float | None
    max_value: float | None


class StandardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    lega_base: str
    lega_designazione: str
    variante_lega: str | None
    norma: str | None
    trattamento_termico: str | None
    tipo_prodotto: str | None
    misura_tipo: str | None
    fonte_excel_foglio: str | None
    fonte_excel_blocco: str | None
    stato_validazione: str
    note: str | None
    created_at: datetime
    updated_at: datetime
    chemistry: list[StandardChemistryResponse] = Field(default_factory=list)
    properties: list[StandardPropertyResponse] = Field(default_factory=list)


class StandardListResponse(BaseModel):
    items: list[StandardResponse]
