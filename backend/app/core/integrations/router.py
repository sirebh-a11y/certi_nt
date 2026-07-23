from typing import Annotated
import socket

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_it_admin
from app.core.integrations.schemas import (
    EsolverExportPublicationResponse,
    EsolverExternalValidationRequest,
    EsolverSqlViewSettingsUpdateRequest,
    EsolverSqlViewTestResponse,
    ExternalConnectionListResponse,
    ExternalConnectionResponse,
    ExternalConnectionTestResponse,
    ExternalConnectionUpdateRequest,
)
from app.core.integrations.service import (
    get_esolver_export_publication_settings,
    get_external_connection,
    list_external_connections,
    record_connection_test,
    serialize_connection,
    update_external_connection,
    record_esolver_external_validation,
    serialize_esolver_export_publication,
    test_esolver_export_view,
    test_esolver_reader_permissions,
    update_esolver_sql_view_settings,
)

router = APIRouter()

ItAdminUser = Annotated[CurrentUser, Depends(require_it_admin)]


@router.get("", response_model=ExternalConnectionListResponse)
def list_connections_route(_: ItAdminUser, db: DbSession) -> ExternalConnectionListResponse:
    return ExternalConnectionListResponse(items=list_external_connections(db))


@router.get("/export-publication", response_model=EsolverExportPublicationResponse)
def get_export_publication_route(_: ItAdminUser, db: DbSession) -> EsolverExportPublicationResponse:
    publication = get_esolver_export_publication_settings(db)
    return serialize_esolver_export_publication(db, publication)


@router.patch("/export-publication/sql-view", response_model=EsolverExportPublicationResponse)
def update_export_publication_route(
    payload: EsolverSqlViewSettingsUpdateRequest,
    current_user: ItAdminUser,
    db: DbSession,
) -> EsolverExportPublicationResponse:
    publication = get_esolver_export_publication_settings(db)
    return update_esolver_sql_view_settings(db, publication, payload, current_user.email)


@router.post("/export-publication/sql-view/test", response_model=EsolverSqlViewTestResponse)
def test_export_view_route(current_user: ItAdminUser, db: DbSession) -> EsolverSqlViewTestResponse:
    publication = get_esolver_export_publication_settings(db)
    return test_esolver_export_view(db, publication, current_user.email)


@router.post("/export-publication/sql-view/test-permissions", response_model=EsolverSqlViewTestResponse)
def test_export_permissions_route(current_user: ItAdminUser, db: DbSession) -> EsolverSqlViewTestResponse:
    publication = get_esolver_export_publication_settings(db)
    return test_esolver_reader_permissions(db, publication, current_user.email)


@router.post("/export-publication/sql-view/external-validation", response_model=EsolverExportPublicationResponse)
def record_export_external_validation_route(
    payload: EsolverExternalValidationRequest,
    current_user: ItAdminUser,
    db: DbSession,
) -> EsolverExportPublicationResponse:
    publication = get_esolver_export_publication_settings(db)
    return record_esolver_external_validation(db, publication, payload, current_user.email)


@router.get("/{code}", response_model=ExternalConnectionResponse)
def get_connection_route(code: str, _: ItAdminUser, db: DbSession) -> ExternalConnectionResponse:
    return serialize_connection(get_external_connection(db, code))


@router.patch("/{code}", response_model=ExternalConnectionResponse)
def update_connection_route(
    code: str,
    payload: ExternalConnectionUpdateRequest,
    current_user: ItAdminUser,
    db: DbSession,
) -> ExternalConnectionResponse:
    connection = get_external_connection(db, code)
    return update_external_connection(db=db, connection=connection, payload=payload, actor_email=current_user.email)


@router.post("/{code}/test-network", response_model=ExternalConnectionTestResponse)
def test_network_route(code: str, current_user: ItAdminUser, db: DbSession) -> ExternalConnectionTestResponse:
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
