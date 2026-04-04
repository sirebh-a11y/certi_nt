from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str
    department: str
    role: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Invalid email")
        return normalized


class UserCreateRequest(UserBase):
    pass


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
