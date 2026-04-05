from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.logs.service import log_service
from app.core.roles.service import ensure_valid_role
from app.core.security.crypto import encrypt_secret
from app.core.users.models import User
from app.core.users.schemas import UserCreateRequest, UserResponse, UserUpdateRequest


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        department=user.department.name,
        role=user.role,
        active=user.active,
        force_password_change=user.force_password_change,
        openai_key_configured=bool(user.openai_api_key_encrypted),
    )


def list_users(db: Session) -> list[UserResponse]:
    users = db.query(User).options(joinedload(User.department)).order_by(User.name.asc()).all()
    return [serialize_user(user) for user in users]


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).options(joinedload(User.department)).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def create_user(db: Session, payload: UserCreateRequest, department_id: int, actor_email: str) -> UserResponse:
    ensure_valid_role(payload.role)
    existing_user = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")

    user = User(
        name=payload.name,
        email=payload.email,
        department_id=department_id,
        role=payload.role,
        password_hash=None,
        active=True,
        force_password_change=True,
        openai_api_key_encrypted=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    created_user = get_user(db, user.id)
    log_service.record("users", f"User created: {created_user.email}", actor_email)
    return serialize_user(created_user)


def update_user(
    db: Session,
    user: User,
    payload: UserUpdateRequest,
    department_id: int,
    actor_email: str,
) -> UserResponse:
    ensure_valid_role(payload.role)

    user.name = payload.name
    user.department_id = department_id
    user.role = payload.role
    user.active = payload.active
    db.add(user)
    db.commit()
    db.refresh(user)

    updated_user = get_user(db, user.id)
    log_service.record("users", f"User updated: {updated_user.email}", actor_email)
    return serialize_user(updated_user)


def disable_user(db: Session, user: User, actor_email: str) -> None:
    user.active = False
    db.add(user)
    db.commit()
    log_service.record("users", f"User disabled: {user.email}", actor_email)


def reset_user_password(db: Session, user: User, actor_email: str) -> None:
    user.password_hash = None
    user.force_password_change = True
    db.add(user)
    db.commit()
    log_service.record("users", f"Password reset requested: {user.email}", actor_email)


def update_openai_key(db: Session, user: User, openai_api_key: str | None, actor_email: str) -> bool:
    user.openai_api_key_encrypted = encrypt_secret(openai_api_key) if openai_api_key else None
    db.add(user)
    db.commit()
    log_service.record("users", f"OpenAI API key updated for {user.email}", actor_email)
    return bool(user.openai_api_key_encrypted)
