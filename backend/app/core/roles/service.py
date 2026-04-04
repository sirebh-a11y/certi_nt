from fastapi import HTTPException, status

from app.core.roles.constants import ROLE_NAMES


def ensure_valid_role(role: str) -> None:
    if role not in ROLE_NAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
