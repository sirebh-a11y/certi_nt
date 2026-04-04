from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logs.service import log_service
from app.core.roles.constants import RoleName
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
