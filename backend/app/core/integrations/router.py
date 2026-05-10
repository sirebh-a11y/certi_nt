from typing import Annotated
import socket

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.integrations.schemas import (
    ExternalConnectionListResponse,
    ExternalConnectionResponse,
    ExternalConnectionTestResponse,
    ExternalConnectionUpdateRequest,
)
from app.core.integrations.service import (
    get_external_connection,
    list_external_connections,
    record_connection_test,
    serialize_connection,
    update_external_connection,
)
from app.core.roles.constants import ROLE_ADMIN

router = APIRouter()

AdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN))]


@router.get("", response_model=ExternalConnectionListResponse)
def list_connections_route(_: AdminUser, db: DbSession) -> ExternalConnectionListResponse:
    return ExternalConnectionListResponse(items=list_external_connections(db))


@router.get("/{code}", response_model=ExternalConnectionResponse)
def get_connection_route(code: str, _: AdminUser, db: DbSession) -> ExternalConnectionResponse:
    return serialize_connection(get_external_connection(db, code))


@router.patch("/{code}", response_model=ExternalConnectionResponse)
def update_connection_route(
    code: str,
    payload: ExternalConnectionUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> ExternalConnectionResponse:
    connection = get_external_connection(db, code)
    return update_external_connection(db=db, connection=connection, payload=payload, actor_email=current_user.email)


@router.post("/{code}/test-network", response_model=ExternalConnectionTestResponse)
def test_network_route(code: str, current_user: AdminUser, db: DbSession) -> ExternalConnectionTestResponse:
    connection = get_external_connection(db, code)
    try:
        with socket.create_connection((connection.server_host, connection.port), timeout=connection.connection_timeout):
            pass
        message = f"Connessione TCP riuscita verso {connection.server_host}:{connection.port}"
        status_value = "ok"
    except OSError as exc:
        message = f"Connessione TCP fallita verso {connection.server_host}:{connection.port}: {exc}"
        status_value = "error"

    tested_at = record_connection_test(
        db=db,
        connection=connection,
        status_value=status_value,
        message=message,
        actor_email=current_user.email,
    )
    return ExternalConnectionTestResponse(status=status_value, message=message, tested_at=tested_at)
