from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class CustomerRequirementBase(BaseModel):
    cod_f3: str = Field(min_length=1, max_length=64)
    cliente: str = Field(min_length=1, max_length=255)
    requires_chemical_analysis: bool = False
    requires_mechanical_mp: bool = False
    requires_mechanical_forged: bool = False
    requires_hardness_hb: bool = False
    requires_lot_traceability_text: bool = False
    requires_lot_traceability_photo: bool = False
    requires_dimensional: bool = False
    requires_marking: bool = False
    requires_macro_micro: bool = False
    requires_ndt: bool = False
    note: str | None = None

    @field_validator("cod_f3", "cliente")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class CustomerRequirementCreateRequest(CustomerRequirementBase):
    pass


class CustomerRequirementUpdateRequest(CustomerRequirementBase):
    pass


class CustomerRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cod_f3: str
    cliente: str
    requires_chemical_analysis: bool
    requires_mechanical_mp: bool
    requires_mechanical_forged: bool
    requires_hardness_hb: bool
    requires_lot_traceability_text: bool
    requires_lot_traceability_photo: bool
    requires_dimensional: bool
    requires_marking: bool
    requires_macro_micro: bool
    requires_ndt: bool
    note: str | None
    source_sheet: str | None
    source_row: int | None
    active: bool
    created_at: datetime
    updated_at: datetime


class CustomerRequirementListResponse(BaseModel):
    items: list[CustomerRequirementResponse]
