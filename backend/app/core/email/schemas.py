from pydantic import BaseModel, field_validator


class NotificationEmail(BaseModel):
    to_email: str
    subject: str
    body: str

    @field_validator("to_email")
    @classmethod
    def validate_local_email(cls, value: str) -> str:
        normalized = value.strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Invalid email address")
        return normalized
