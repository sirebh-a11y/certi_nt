"""User policy: eSolver/Quarta reads have no elapsed-time deadline.

Keep connection establishment, PDF/AI and lock timeouts independent. Existing
stored query_timeout values remain available for rollback; they are not a new
deadline for these two integrations. pymssql defines timeout=0 as no timeout.
"""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.integrations.models import ExternalConnection


NO_DEADLINE_CODES = frozenset({"esolver", "quarta"})
_REVISION_FIELDS = ("enabled", "server_host", "port", "database_name", "username",
                    "password_encrypted", "schema_name", "object_settings")


def query_timeout(connection) -> int:
    return 0 if getattr(connection, "code", None) in NO_DEADLINE_CODES else connection.query_timeout


def connection_revision(connection) -> str:
    data = {field: getattr(connection, field, None) for field in _REVISION_FIELDS}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def ensure_connection_unchanged(db, connection, revision: str) -> None:
    # Real sessions only; no populate_existing that could discard pending work.
    if not isinstance(db, Session) or not isinstance(connection, ExternalConnection) or connection.id is None:
        return
    fields = [getattr(ExternalConnection, field) for field in _REVISION_FIELDS]
    values = db.execute(select(*fields).where(ExternalConnection.id == connection.id)).mappings().one_or_none()
    current = hashlib.sha256(json.dumps(dict(values) if values else {}, sort_keys=True, default=str).encode()).hexdigest()
    if current != revision:
        raise HTTPException(409, "Parametri del collegamento modificati durante la lettura: aggiorna e riprova.")
