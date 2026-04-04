from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str | None = None


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
    email: EmailStr
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
