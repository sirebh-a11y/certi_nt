from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExternalConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    enabled: bool
    server_host: str
    port: int
    database_name: str
    username: str
    password_configured: bool
    driver_name: str
    encrypt: bool
    trust_server_certificate: bool
    connection_timeout: int
    query_timeout: int
    schema_name: str
    object_settings: dict[str, Any]
    notes: str
    last_test_status: str | None
    last_test_message: str | None
    last_test_at: datetime | None
    updated_at: datetime


class ExternalConnectionListResponse(BaseModel):
    items: list[ExternalConnectionResponse]


class ExternalConnectionUpdateRequest(BaseModel):
    enabled: bool
    server_host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: str | None = Field(default=None, max_length=512)
    clear_password: bool = False
    driver_name: str = Field(min_length=1, max_length=128)
    encrypt: bool
    trust_server_certificate: bool
    connection_timeout: int = Field(ge=1, le=120)
    query_timeout: int = Field(ge=1, le=600)
    schema_name: str = Field(min_length=1, max_length=128)
    object_settings: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("server_host", "database_name", "username", "driver_name", "schema_name", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ExternalConnectionTestResponse(BaseModel):
    status: str
    message: str
    tested_at: datetime
