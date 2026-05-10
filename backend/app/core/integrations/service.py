from datetime import datetime, timezone
import os

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logs.service import log_service
from app.core.security.crypto import encrypt_secret
from app.core.integrations.models import ExternalConnection
from app.core.integrations.schemas import ExternalConnectionResponse, ExternalConnectionUpdateRequest


DEFAULT_CONNECTIONS = {
    "esolver": {
        "label": "eSolver",
        "enabled": True,
        "server_host": "10.10.3.6",
        "port": 1433,
        "database_name": "ESOLVER",
        "username": "certi",
        "password_env": "ESOLVER_PASSWORD",
        "driver_name": "ODBC Driver 18 for SQL Server",
        "encrypt": False,
        "trust_server_certificate": True,
        "connection_timeout": 10,
        "query_timeout": 30,
        "schema_name": "dbo",
        "object_settings": {
            "anagrafiche_view": "CertiCliForF3",
            "righe_ddt_view": "CertiRigheDDT",
            "odp_field": "ORP",
            "ddt_field": "DDT",
            "supplier_field": "RagSoc",
            "lot_field": "RifLottoAlfanum",
            "quantity_field": "QtaUmMag",
            "certificate_present_field": "CertificatoPresente",
        },
        "notes": "Vista righe DDT e anagrafiche clienti/fornitori in sola lettura.",
    },
    "quarta": {
        "label": "QuartaEVO",
        "enabled": True,
        "server_host": "10.10.6.10",
        "port": 1433,
        "database_name": "INT_Q3",
        "username": "INT_Q3",
        "password_env": "QUARTA_PASSWORD",
        "driver_name": "ODBC Driver 18 for SQL Server",
        "encrypt": False,
        "trust_server_certificate": True,
        "connection_timeout": 10,
        "query_timeout": 30,
        "schema_name": "dbo",
        "object_settings": {
            "traceability_view": "CFG_Q3ESS_ONGIUDET_TRACMP",
            "company_field": "COD_AZIENDA",
            "odp_field": "COD_ODP",
            "article_field": "COD_ART",
            "description_field": "DES_ART",
            "raw_lot_field": "COD_LOTTO",
            "raw_material_field": "COD_MP",
            "supplier_certificate_field": "CERT_FORN",
            "heat_field": "COLATA",
            "quantity_field": "QTA",
        },
        "notes": "Vista tracciabilita materiali per ODP in sola lettura.",
    },
}


def seed_external_connections(db: Session) -> None:
    for code, defaults in DEFAULT_CONNECTIONS.items():
        existing = db.query(ExternalConnection).filter(ExternalConnection.code == code).one_or_none()
        if existing is not None:
            continue

        password = os.getenv(defaults["password_env"], "")
        db.add(
            ExternalConnection(
                code=code,
                label=defaults["label"],
                enabled=defaults["enabled"],
                server_host=defaults["server_host"],
                port=defaults["port"],
                database_name=defaults["database_name"],
                username=defaults["username"],
                password_encrypted=encrypt_secret(password) if password else None,
                driver_name=defaults["driver_name"],
                encrypt=defaults["encrypt"],
                trust_server_certificate=defaults["trust_server_certificate"],
                connection_timeout=defaults["connection_timeout"],
                query_timeout=defaults["query_timeout"],
                schema_name=defaults["schema_name"],
                object_settings=defaults["object_settings"],
                notes=defaults["notes"],
            )
        )
    db.commit()


def serialize_connection(connection: ExternalConnection) -> ExternalConnectionResponse:
    return ExternalConnectionResponse(
        id=connection.id,
        code=connection.code,
        label=connection.label,
        enabled=connection.enabled,
        server_host=connection.server_host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.username,
        password_configured=bool(connection.password_encrypted),
        driver_name=connection.driver_name,
        encrypt=connection.encrypt,
        trust_server_certificate=connection.trust_server_certificate,
        connection_timeout=connection.connection_timeout,
        query_timeout=connection.query_timeout,
        schema_name=connection.schema_name,
        object_settings=connection.object_settings or {},
        notes=connection.notes,
        last_test_status=connection.last_test_status,
        last_test_message=connection.last_test_message,
        last_test_at=connection.last_test_at,
        updated_at=connection.updated_at,
    )


def list_external_connections(db: Session) -> list[ExternalConnectionResponse]:
    items = db.query(ExternalConnection).order_by(ExternalConnection.id.asc()).all()
    return [serialize_connection(item) for item in items]


def get_external_connection(db: Session, code: str) -> ExternalConnection:
    connection = db.query(ExternalConnection).filter(ExternalConnection.code == code).one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External connection not found")
    return connection


def update_external_connection(
    db: Session,
    connection: ExternalConnection,
    payload: ExternalConnectionUpdateRequest,
    actor_email: str,
) -> ExternalConnectionResponse:
    connection.enabled = payload.enabled
    connection.server_host = payload.server_host
    connection.port = payload.port
    connection.database_name = payload.database_name
    connection.username = payload.username
    connection.driver_name = payload.driver_name
    connection.encrypt = payload.encrypt
    connection.trust_server_certificate = payload.trust_server_certificate
    connection.connection_timeout = payload.connection_timeout
    connection.query_timeout = payload.query_timeout
    connection.schema_name = payload.schema_name
    connection.object_settings = payload.object_settings
    connection.notes = payload.notes
    if payload.clear_password:
        connection.password_encrypted = None
    elif payload.password is not None and payload.password != "":
        connection.password_encrypted = encrypt_secret(payload.password)

    db.add(connection)
    db.commit()
    db.refresh(connection)
    log_service.record("integrations", f"External connection updated: {connection.code}", actor_email)
    return serialize_connection(connection)


def record_connection_test(
    db: Session,
    connection: ExternalConnection,
    *,
    status_value: str,
    message: str,
    actor_email: str,
) -> datetime:
    tested_at = datetime.now(timezone.utc)
    connection.last_test_status = status_value
    connection.last_test_message = message
    connection.last_test_at = tested_at
    db.add(connection)
    db.commit()
    log_service.record("integrations", f"External connection test {status_value}: {connection.code}", actor_email)
    return tested_at
