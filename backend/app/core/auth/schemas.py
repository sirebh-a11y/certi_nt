from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Invalid email")
        return normalized


class SetPasswordRequest(BaseModel):
    setup_token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    department: str
    role: str
    active: bool
    force_password_change: bool
    openai_key_configured: bool


class LoginResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    requires_set_password: bool = False
    requires_password_change: bool = False
    setup_token: str | None = None
    user: AuthUser | None = None


class MessageResponse(BaseModel):
    message: str
