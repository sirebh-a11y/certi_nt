from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class EmailSettingsResponse(BaseModel):
    source: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password_configured: bool
    smtp_tls: bool
    mail_from_email: str
    mail_from_name: str
    mail_always_cc_email: str | None
    acquisition_notification_admin_email: str | None
    updated_at: datetime | None


class EmailSettingsUpdateRequest(BaseModel):
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_user: str = Field(default="", max_length=255)
    smtp_password: str | None = Field(default=None, max_length=512)
    clear_smtp_password: bool = False
    smtp_tls: bool
    mail_from_email: str
    mail_from_name: str = Field(min_length=1, max_length=255)
    mail_always_cc_email: str | None = None
    acquisition_notification_admin_email: str | None = None

    @field_validator("smtp_host", "smtp_user", "mail_from_name", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str:
        return (value or "").strip()

    @field_validator("mail_from_email")
    @classmethod
    def validate_required_email(cls, value: str | None) -> str:
        normalized = (value or "").strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Email non valida")
        return normalized

    @field_validator("mail_always_cc_email", "acquisition_notification_admin_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Email non valida")
        return normalized


class EmailSettingsTestRequest(BaseModel):
    to_email: str | None = None

    @field_validator("to_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Email non valida")
        return normalized


class EmailSettingsTestResponse(BaseModel):
    status: str
    message: str
