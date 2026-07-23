from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class EsolverExportEndpointResponse(BaseModel):
    username: str
    password_configured: bool
    path: str
    public_url: str | None
    fields: list[str]


class EsolverSqlViewSettingsResponse(BaseModel):
    enabled: bool
    external_host: str | None
    external_port: int | None
    database_name: str
    schema_name: str
    view_name: str
    reader_username: str | None
    reader_password_configured: bool
    allowed_source: str | None
    ssl_mode: str
    notes: str
    last_view_test_status: str | None
    last_view_test_message: str | None
    last_view_test_at: datetime | None
    last_permissions_test_status: str | None
    last_permissions_test_message: str | None
    last_permissions_test_at: datetime | None
    external_validation_status: str
    external_validation_message: str | None
    external_validation_at: datetime | None
    updated_at: datetime


class EsolverExportPublicationResponse(BaseModel):
    endpoint: EsolverExportEndpointResponse
    sql_view: EsolverSqlViewSettingsResponse


class EsolverSqlViewSettingsUpdateRequest(BaseModel):
    enabled: bool
    external_host: str | None = Field(default=None, max_length=255)
    external_port: int | None = Field(default=None, ge=1, le=65535)
    reader_username: str | None = Field(default=None, max_length=128)
    allowed_source: str | None = Field(default=None, max_length=255)
    ssl_mode: str = Field(min_length=1, max_length=64)
    notes: str = Field(default="", max_length=4000)

    @field_validator("external_host", "reader_username", "allowed_source")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("ssl_mode", "notes")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_complete_external_configuration_when_enabled(self):
        if not self.enabled:
            return self
        missing = []
        if not self.external_host:
            missing.append("host esterno")
        if not self.external_port:
            missing.append("porta esterna")
        if not self.reader_username:
            missing.append("utente sola lettura")
        if not self.allowed_source:
            missing.append("origine autorizzata")
        if self.ssl_mode.upper() == "DA_FORNIRE_IT":
            missing.append("modalità SSL")
        if missing:
            raise ValueError(f"Prima di abilitare completare: {', '.join(missing)}")
        return self


class EsolverSqlViewTestResponse(BaseModel):
    status: str
    message: str
    tested_at: datetime


class EsolverExternalValidationRequest(BaseModel):
    validated: bool
    message: str = Field(default="", max_length=2000)

    @field_validator("message")
    @classmethod
    def strip_validation_message(cls, value: str) -> str:
        return value.strip()
