from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("Il testo nota non puo essere vuoto")
    return cleaned


class NoteTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    note_key: str | None
    note_value: str | None
    text: str
    is_system: bool
    is_active: bool
    sort_order: int


class NoteTemplateListResponse(BaseModel):
    items: list[NoteTemplateResponse]


class NoteTemplateCreateRequest(BaseModel):
    text: str = Field(min_length=1)
    is_active: bool = True

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _normalize_text(value)


class NoteTemplateUpdateRequest(BaseModel):
    text: str = Field(min_length=1)
    is_active: bool

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _normalize_text(value)

