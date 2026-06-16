from collections.abc import Callable
import unicodedata
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logs.service import log_service
from app.core.roles.constants import ROLE_ADMIN, ROLE_MANAGER, RoleName
from app.core.security.jwt import decode_token
from app.core.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
TokenValue = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(db: DbSession, token: TokenValue) -> User:
    payload = decode_token(token, expected_token_type="access")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, int(user_id))
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not available")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: RoleName) -> Callable[[User], User]:
    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            log_service.record(
                event_type="authorization",
                message=f"Forbidden access for role {current_user.role}",
                actor_email=current_user.email,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user

    return dependency


def _normalize_department_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_accents.strip().lower()


def is_it_admin(user: User) -> bool:
    return user.role == "admin" and _normalize_department_name(user.department.name if user.department else None) == "it"


def user_department_key(user: User) -> str:
    return _normalize_department_name(user.department.name if user.department else None)


def user_is_in_department(user: User, *department_keys: str) -> bool:
    normalized_departments = {_normalize_department_name(department) for department in department_keys}
    return user_department_key(user) in normalized_departments


def is_quality_area_user(user: User) -> bool:
    return user_is_in_department(user, "it", "qualita")


def is_quality_area_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN and is_quality_area_user(user)


def is_quality_area_manager_or_admin(user: User) -> bool:
    return user.role in {ROLE_ADMIN, ROLE_MANAGER} and is_quality_area_user(user)


def require_it_admin(current_user: CurrentUser) -> User:
    if not is_it_admin(current_user):
        log_service.record(
            event_type="authorization",
            message=f"Forbidden IT admin access for role {current_user.role}",
            actor_email=current_user.email,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


def require_quality_area_admin(current_user: CurrentUser) -> User:
    if not is_quality_area_admin(current_user):
        log_service.record(
            event_type="authorization",
            message=f"Forbidden quality admin access for role {current_user.role}",
            actor_email=current_user.email,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


def require_quality_area_manager_or_admin(current_user: CurrentUser) -> User:
    if not is_quality_area_manager_or_admin(current_user):
        log_service.record(
            event_type="authorization",
            message=f"Forbidden quality manager/admin access for role {current_user.role}",
            actor_email=current_user.email,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user
