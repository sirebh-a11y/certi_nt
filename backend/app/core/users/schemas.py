from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    department: str
    role: str


class UserCreateRequest(UserBase):
    pass


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
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
