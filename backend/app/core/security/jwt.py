from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.core.config import settings

ALGORITHM = "HS256"


def create_token(subject: str, token_type: str, expires_minutes: int, extra: dict | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_token_type: str | None = None) -> dict:
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    token_type = payload.get("type")
    if expected_token_type and token_type != expected_token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload
