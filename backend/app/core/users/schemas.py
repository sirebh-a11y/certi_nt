from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import normalize_and_validate_email

class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str
    department: str
    role: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_and_validate_email(value)


class UserCreateRequest(UserBase):
    pass


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    department: str
    role: str
    active: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    department: str
    role: str
    active: bool
    force_password_change: bool
    openai_key_configured: bool


class UserListResponse(BaseModel):
    items: list[UserResponse]


class OpenAIKeyUpdateRequest(BaseModel):
    openai_api_key: str | None = None


class OpenAIKeyStatusResponse(BaseModel):
    configured: bool


class UserActionResponse(BaseModel):
    message: str
