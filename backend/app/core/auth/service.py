from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth.schemas import AuthUser, LoginResponse
from app.core.config import settings
from app.core.logs.service import log_service
from app.core.security.jwt import create_token, decode_token
from app.core.security.passwords import hash_password, verify_password
from app.core.users.models import User


def build_auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        name=user.name,
        email=user.email,
        department=user.department.name,
        role=user.role,
        active=user.active,
        force_password_change=user.force_password_change,
        openai_key_configured=bool(user.openai_api_key_encrypted),
    )


def login(db: Session, email: str, password: str | None) -> LoginResponse:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.password_hash is None:
        setup_token = create_token(
            subject=str(user.id),
            token_type="setup_password",
            expires_minutes=settings.setup_token_expire_minutes,
        )
        log_service.record("authentication", "Set password requested", user.email)
        return LoginResponse(requires_set_password=True, setup_token=setup_token)

    if not password or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_token(
        subject=str(user.id),
        token_type="access",
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": user.role},
    )
    log_service.record("authentication", "Login successful", user.email)
    return LoginResponse(
        access_token=access_token,
        requires_password_change=user.force_password_change,
        user=build_auth_user(user),
    )


def set_password(db: Session, setup_token: str, new_password: str) -> LoginResponse:
    payload = decode_token(setup_token, expected_token_type="setup_password")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(new_password)
    user.force_password_change = False
    user.last_login = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_token(
        subject=str(user.id),
        token_type="access",
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": user.role},
    )
    log_service.record("authentication", "Password set completed", user.email)
    return LoginResponse(access_token=access_token, user=build_auth_user(user))


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if user.password_hash is None or not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is invalid")

    user.password_hash = hash_password(new_password)
    user.force_password_change = False
    db.add(user)
    db.commit()
    log_service.record("authentication", "Password changed", user.email)
