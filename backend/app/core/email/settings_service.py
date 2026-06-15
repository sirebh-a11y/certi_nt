from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email.models import EmailSettings
from app.core.email.settings_schemas import EmailSettingsResponse, EmailSettingsUpdateRequest
from app.core.logs.service import log_service
from app.core.security.crypto import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class EffectiveEmailSettings:
    source: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_tls: bool
    mail_from_email: str
    mail_from_name: str
    acquisition_notification_admin_email: str | None


def _settings_row(db: Session) -> EmailSettings | None:
    return db.query(EmailSettings).order_by(EmailSettings.id.asc()).first()


def get_effective_email_settings(db: Session | None = None) -> EffectiveEmailSettings:
    row = _settings_row(db) if db is not None else None
    if row is not None:
        return EffectiveEmailSettings(
            source="db",
            smtp_host=row.smtp_host,
            smtp_port=row.smtp_port,
            smtp_user=row.smtp_user,
            smtp_password=decrypt_secret(row.smtp_password_encrypted) if row.smtp_password_encrypted else "",
            smtp_tls=row.smtp_tls,
            mail_from_email=row.mail_from_email,
            mail_from_name=row.mail_from_name,
            acquisition_notification_admin_email=row.acquisition_notification_admin_email,
        )

    return EffectiveEmailSettings(
        source="env",
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
        smtp_tls=settings.smtp_tls,
        mail_from_email=settings.mail_from_email,
        mail_from_name=settings.mail_from_name,
        acquisition_notification_admin_email=settings.acquisition_notification_admin_email,
    )


def serialize_email_settings(db: Session) -> EmailSettingsResponse:
    row = _settings_row(db)
    effective = get_effective_email_settings(db)
    return EmailSettingsResponse(
        source=effective.source,
        smtp_host=effective.smtp_host,
        smtp_port=effective.smtp_port,
        smtp_user=effective.smtp_user,
        smtp_password_configured=bool(effective.smtp_password),
        smtp_tls=effective.smtp_tls,
        mail_from_email=effective.mail_from_email,
        mail_from_name=effective.mail_from_name,
        acquisition_notification_admin_email=effective.acquisition_notification_admin_email,
        updated_at=row.updated_at if row is not None else None,
    )


def update_email_settings(db: Session, payload: EmailSettingsUpdateRequest, actor_email: str) -> EmailSettingsResponse:
    row = _settings_row(db)
    current_effective = get_effective_email_settings(db)
    if row is None:
        row = EmailSettings(
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            smtp_user=payload.smtp_user,
            smtp_password_encrypted=None,
            smtp_tls=payload.smtp_tls,
            mail_from_email=str(payload.mail_from_email),
            mail_from_name=payload.mail_from_name,
            acquisition_notification_admin_email=str(payload.acquisition_notification_admin_email) if payload.acquisition_notification_admin_email else None,
        )

    row.smtp_host = payload.smtp_host
    row.smtp_port = payload.smtp_port
    row.smtp_user = payload.smtp_user
    row.smtp_tls = payload.smtp_tls
    row.mail_from_email = str(payload.mail_from_email)
    row.mail_from_name = payload.mail_from_name
    row.acquisition_notification_admin_email = (
        str(payload.acquisition_notification_admin_email) if payload.acquisition_notification_admin_email else None
    )
    if payload.clear_smtp_password:
        row.smtp_password_encrypted = None
    elif payload.smtp_password is not None and payload.smtp_password != "":
        row.smtp_password_encrypted = encrypt_secret(payload.smtp_password)
    elif row.smtp_password_encrypted is None and current_effective.smtp_password:
        row.smtp_password_encrypted = encrypt_secret(current_effective.smtp_password)

    db.add(row)
    db.commit()
    db.refresh(row)
    log_service.record("email", "Email settings updated", actor_email)
    return serialize_email_settings(db)


def ensure_email_is_configured(config: EffectiveEmailSettings) -> None:
    if not config.smtp_host:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host SMTP non configurato")
    if not config.mail_from_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email mittente non configurata")
