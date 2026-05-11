from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    provider_type: str
    base_url: str | None
    enabled: bool
    notes: str
    updated_at: datetime


class AIModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    provider_code: str
    provider_label: str
    label: str
    model_id: str
    usage_scope: str
    enabled: bool
    is_default: bool
    notes: str
    updated_at: datetime


class AIConfigResponse(BaseModel):
    providers: list[AIProviderResponse]
    models: list[AIModelResponse]


class AIProviderCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(min_length=1, max_length=64)
    base_url: str | None = Field(default=None, max_length=255)
    enabled: bool = True
    notes: str = ""

    @field_validator("code", "label", "provider_type", "base_url", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class AIProviderUpdateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(min_length=1, max_length=64)
    base_url: str | None = Field(default=None, max_length=255)
    enabled: bool
    notes: str = ""

    @field_validator("label", "provider_type", "base_url", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class AIModelCreateRequest(BaseModel):
    provider_id: int
    label: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    usage_scope: str = Field(default="document_vision", min_length=1, max_length=64)
    enabled: bool = True
    is_default: bool = False
    notes: str = ""

    @field_validator("label", "model_id", "usage_scope", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class AIModelUpdateRequest(BaseModel):
    provider_id: int
    label: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    usage_scope: str = Field(default="document_vision", min_length=1, max_length=64)
    enabled: bool
    is_default: bool
    notes: str = ""

    @field_validator("label", "model_id", "usage_scope", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()
