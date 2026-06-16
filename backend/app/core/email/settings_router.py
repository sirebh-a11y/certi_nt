from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_it_admin
from app.core.email.schemas import NotificationEmail
from app.core.email.service import email_service
from app.core.email.settings_schemas import (
    EmailSettingsResponse,
    EmailSettingsTestRequest,
    EmailSettingsTestResponse,
    EmailSettingsUpdateRequest,
)
from app.core.email.settings_service import ensure_email_is_configured, get_effective_email_settings, serialize_email_settings, update_email_settings

router = APIRouter()

ItAdminUser = Annotated[CurrentUser, Depends(require_it_admin)]


@router.get("", response_model=EmailSettingsResponse)
def get_email_settings_route(_: ItAdminUser, db: DbSession) -> EmailSettingsResponse:
    return serialize_email_settings(db)


@router.patch("", response_model=EmailSettingsResponse)
def update_email_settings_route(
    payload: EmailSettingsUpdateRequest,
    current_user: ItAdminUser,
    db: DbSession,
) -> EmailSettingsResponse:
    return update_email_settings(db=db, payload=payload, actor_email=current_user.email)


@router.post("/test", response_model=EmailSettingsTestResponse)
def test_email_settings_route(
    payload: EmailSettingsTestRequest,
    current_user: ItAdminUser,
    db: DbSession,
) -> EmailSettingsTestResponse:
    config = get_effective_email_settings(db)
    ensure_email_is_configured(config)
    recipient = str(payload.to_email or current_user.email)
    email_service.send_notification(
        NotificationEmail(
            to_email=recipient,
            subject="CERTI_nt - Test configurazione email",
            body="Messaggio di test configurazione email CERTI_nt.",
        ),
        db=db,
    )
    return EmailSettingsTestResponse(status="ok", message=f"Email di test inviata a {recipient}")
