from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SupplierCalendarClosureCreate(BaseModel):
    start_date: date
    end_date: date
    label: str = Field(min_length=1, max_length=255)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("label obbligatoria")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "SupplierCalendarClosureCreate":
        if self.end_date < self.start_date:
            raise ValueError("La data fine deve essere uguale o successiva alla data inizio")
        return self


class SupplierCalendarClosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_date: date
    end_date: date
    label: str


class SupplierCalendarDayResponse(BaseModel):
    date: date
    kind: str
    label: str


class SupplierCalendarTotalsResponse(BaseModel):
    weekend_days: int
    holiday_days: int
    closure_days: int


class SupplierCalendarYearResponse(BaseModel):
    year: int
    holidays: list[SupplierCalendarDayResponse]
    closures: list[SupplierCalendarClosureResponse]
    days: list[SupplierCalendarDayResponse]
    totals: SupplierCalendarTotalsResponse
