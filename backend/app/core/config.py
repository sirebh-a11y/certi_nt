from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="ENV")
    app_secret_key: str = Field(default="change-me-certi-nt-secret", alias="APP_SECRET_KEY")
    database_url: str = Field(
        default="postgresql+psycopg://certi_nt:certi_nt@postgres:5432/certi_nt",
        alias="DATABASE_URL",
    )
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    setup_token_expire_minutes: int = Field(default=30, alias="SETUP_TOKEN_EXPIRE_MINUTES")
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    smtp_host: str = Field(default="mailhog", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_tls: bool = Field(default=False, alias="SMTP_TLS")
    mail_from_email: str = Field(default="noreply@certi.local", alias="MAIL_FROM_EMAIL")
    mail_from_name: str = Field(default="CERTI_nt System", alias="MAIL_FROM_NAME")
    document_storage_root: str = Field(default="storage/documents", alias="DOCUMENT_STORAGE_ROOT")
    document_vision_model: str = Field(default="gpt-5.4", alias="DOCUMENT_VISION_MODEL")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
