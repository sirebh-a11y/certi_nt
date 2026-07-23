from datetime import datetime, timezone
import os

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logs.service import log_service
from app.core.security.crypto import encrypt_secret
from app.core.integrations.models import EsolverExportPublicationSettings, ExternalConnection
from app.core.integrations.schemas import (
    EsolverExportEndpointResponse,
    EsolverExportPublicationResponse,
    EsolverExternalValidationRequest,
    EsolverSqlViewSettingsResponse,
    EsolverSqlViewSettingsUpdateRequest,
    EsolverSqlViewTestResponse,
    ExternalConnectionResponse,
    ExternalConnectionUpdateRequest,
)
from app.modules.esolver_export.service import esolver_pdf_export_fields
from app.modules.esolver_export.view import ESOLVER_EXPORT_QUALIFIED_VIEW


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
            "certiol_view": "CertiOL",
        },
        "notes": "",
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
        },
        "notes": "",
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


def seed_esolver_export_publication_settings(db: Session) -> None:
    existing = db.query(EsolverExportPublicationSettings).first()
    database_name = make_url(settings.database_url).database or "certi_nt"
    if existing is not None:
        existing.database_name = database_name
        existing.schema_name = "esolver_export"
        existing.view_name = "certi_certificati_pdf"
        db.add(existing)
        db.commit()
        return
    db.add(
        EsolverExportPublicationSettings(
            enabled=False,
            external_host=None,
            external_port=None,
            database_name=database_name,
            schema_name="esolver_export",
            view_name="certi_certificati_pdf",
            reader_username=None,
            allowed_source=None,
            ssl_mode="DA_FORNIRE_IT",
            notes="Dati di pubblicazione PostgreSQL da completare con IT.",
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


def get_esolver_export_publication_settings(db: Session) -> EsolverExportPublicationSettings:
    publication = db.query(EsolverExportPublicationSettings).order_by(EsolverExportPublicationSettings.id.asc()).first()
    if publication is None:
        seed_esolver_export_publication_settings(db)
        publication = db.query(EsolverExportPublicationSettings).order_by(EsolverExportPublicationSettings.id.asc()).first()
    if publication is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Configurazione export non disponibile")
    return publication


def _reader_password_configured(db: Session, reader_username: str | None) -> bool:
    if not reader_username or db.get_bind().dialect.name != "postgresql":
        return False
    try:
        value = db.execute(
            text("SELECT rolpassword IS NOT NULL FROM pg_roles WHERE rolname = :role_name"),
            {"role_name": reader_username},
        ).scalar_one_or_none()
        return bool(value)
    except Exception:
        db.rollback()
        return False


def serialize_esolver_export_publication(
    db: Session,
    publication: EsolverExportPublicationSettings,
) -> EsolverExportPublicationResponse:
    base_url = settings.certi_public_base_url.strip().rstrip("/")
    endpoint_path = "/api/export/esolver/certificati-pdf"
    return EsolverExportPublicationResponse(
        endpoint=EsolverExportEndpointResponse(
            username=settings.certi_export_username,
            password_configured=bool(settings.certi_export_password),
            path=endpoint_path,
            public_url=f"{base_url}{endpoint_path}" if base_url else None,
            fields=esolver_pdf_export_fields(),
        ),
        sql_view=EsolverSqlViewSettingsResponse(
            enabled=publication.enabled,
            external_host=publication.external_host,
            external_port=publication.external_port,
            database_name=publication.database_name,
            schema_name=publication.schema_name,
            view_name=publication.view_name,
            reader_username=publication.reader_username,
            reader_password_configured=_reader_password_configured(db, publication.reader_username),
            allowed_source=publication.allowed_source,
            ssl_mode=publication.ssl_mode,
            notes=publication.notes,
            last_view_test_status=publication.last_view_test_status,
            last_view_test_message=publication.last_view_test_message,
            last_view_test_at=publication.last_view_test_at,
            last_permissions_test_status=publication.last_permissions_test_status,
            last_permissions_test_message=publication.last_permissions_test_message,
            last_permissions_test_at=publication.last_permissions_test_at,
            external_validation_status=publication.external_validation_status,
            external_validation_message=publication.external_validation_message,
            external_validation_at=publication.external_validation_at,
            updated_at=publication.updated_at,
        ),
    )


def update_esolver_sql_view_settings(
    db: Session,
    publication: EsolverExportPublicationSettings,
    payload: EsolverSqlViewSettingsUpdateRequest,
    actor_email: str,
) -> EsolverExportPublicationResponse:
    reader_changed = publication.reader_username != payload.reader_username
    external_connection_changed = any(
        (
            publication.external_host != payload.external_host,
            publication.external_port != payload.external_port,
            publication.reader_username != payload.reader_username,
            publication.allowed_source != payload.allowed_source,
            publication.ssl_mode != payload.ssl_mode,
        )
    )
    if payload.enabled:
        blockers = []
        if publication.last_view_test_status != "ok":
            blockers.append("test vista")
        if publication.last_permissions_test_status != "ok" or reader_changed:
            blockers.append("test permessi")
        if not _reader_password_configured(db, payload.reader_username):
            blockers.append("password del lettore PostgreSQL")
        if blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Pubblicazione non abilitabile: completare {', '.join(blockers)}",
            )
    for field_name in (
        "enabled",
        "external_host",
        "external_port",
        "reader_username",
        "allowed_source",
        "ssl_mode",
        "notes",
    ):
        setattr(publication, field_name, getattr(payload, field_name))
    if reader_changed:
        publication.last_permissions_test_status = None
        publication.last_permissions_test_message = None
        publication.last_permissions_test_at = None
    if external_connection_changed:
        publication.external_validation_status = "pending"
        publication.external_validation_message = "Verifica esterna da ripetere dopo la modifica della configurazione"
        publication.external_validation_at = None
    db.add(publication)
    db.commit()
    db.refresh(publication)
    log_service.record("integrations", "Configurazione pubblicazione vista eSolver aggiornata", actor_email)
    return serialize_esolver_export_publication(db, publication)


def test_esolver_export_view(
    db: Session,
    publication: EsolverExportPublicationSettings,
    actor_email: str,
) -> EsolverSqlViewTestResponse:
    tested_at = datetime.now(timezone.utc)
    try:
        if db.get_bind().dialect.name != "postgresql":
            raise RuntimeError("La vista SQL eSolver è disponibile solo su PostgreSQL")
        count = db.execute(text(f"SELECT count(*) FROM {ESOLVER_EXPORT_QUALIFIED_VIEW}")).scalar_one()
        status_value = "ok"
        message = f"Vista disponibile: {count} righe esportabili"
    except Exception as exc:
        db.rollback()
        status_value = "error"
        message = f"Test vista fallito: {exc}"
    publication.last_view_test_status = status_value
    publication.last_view_test_message = message
    publication.last_view_test_at = tested_at
    db.add(publication)
    db.commit()
    log_service.record("integrations", f"Test vista eSolver {status_value}", actor_email)
    return EsolverSqlViewTestResponse(status=status_value, message=message, tested_at=tested_at)


def test_esolver_reader_permissions(
    db: Session,
    publication: EsolverExportPublicationSettings,
    actor_email: str,
) -> EsolverSqlViewTestResponse:
    tested_at = datetime.now(timezone.utc)
    try:
        if db.get_bind().dialect.name != "postgresql":
            raise RuntimeError("La verifica permessi è disponibile solo su PostgreSQL")
        role_name = (publication.reader_username or "").strip()
        if not role_name:
            raise RuntimeError("Utente PostgreSQL di sola lettura non indicato")
        role = db.execute(
            text(
                """
                SELECT rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolpassword IS NOT NULL AS has_password
                FROM pg_roles
                WHERE rolname = :role_name
                """
            ),
            {"role_name": role_name},
        ).mappings().one_or_none()
        if role is None:
            raise RuntimeError("Utente PostgreSQL non trovato")
        checks = {
            "login": bool(role["rolcanlogin"]),
            "password": bool(role["has_password"]),
            "no_elevated_role": not any((role["rolsuper"], role["rolcreatedb"], role["rolcreaterole"])),
            "schema_usage": bool(
                db.execute(
                    text("SELECT has_schema_privilege(:role_name, :schema_name, 'USAGE')"),
                    {"role_name": role_name, "schema_name": publication.schema_name},
                ).scalar_one()
            ),
            "view_select": bool(
                db.execute(
                    text("SELECT has_table_privilege(:role_name, :view_name, 'SELECT')"),
                    {
                        "role_name": role_name,
                        "view_name": f"{publication.schema_name}.{publication.view_name}",
                    },
                ).scalar_one()
            ),
            "no_base_table_access": not bool(
                db.execute(
                    text(
                        "SELECT has_table_privilege("
                        ":role_name, 'public.quarta_taglio_final_certificates', "
                        "'SELECT,INSERT,UPDATE,DELETE')"
                    ),
                    {"role_name": role_name},
                ).scalar_one()
            ),
        }
        failed = [name for name, passed in checks.items() if not passed]
        status_value = "ok" if not failed else "error"
        message = "Permessi minimi corretti" if not failed else f"Verifiche non superate: {', '.join(failed)}"
    except Exception as exc:
        db.rollback()
        status_value = "error"
        message = f"Test permessi fallito: {exc}"
    publication.last_permissions_test_status = status_value
    publication.last_permissions_test_message = message
    publication.last_permissions_test_at = tested_at
    db.add(publication)
    db.commit()
    log_service.record("integrations", f"Test permessi vista eSolver {status_value}", actor_email)
    return EsolverSqlViewTestResponse(status=status_value, message=message, tested_at=tested_at)


def record_esolver_external_validation(
    db: Session,
    publication: EsolverExportPublicationSettings,
    payload: EsolverExternalValidationRequest,
    actor_email: str,
) -> EsolverExportPublicationResponse:
    if payload.validated:
        missing = [
            label
            for label, value in (
                ("host esterno", publication.external_host),
                ("porta esterna", publication.external_port),
                ("utente sola lettura", publication.reader_username),
                ("origine autorizzata", publication.allowed_source),
            )
            if not value
        ]
        if publication.ssl_mode.upper() == "DA_FORNIRE_IT":
            missing.append("modalità SSL")
        if publication.last_view_test_status != "ok":
            missing.append("test vista superato")
        if publication.last_permissions_test_status != "ok":
            missing.append("test permessi superato")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Verifica esterna non confermabile: manca {', '.join(missing)}",
            )
    publication.external_validation_status = "ok" if payload.validated else "pending"
    publication.external_validation_message = payload.message or None
    publication.external_validation_at = datetime.now(timezone.utc) if payload.validated else None
    db.add(publication)
    db.commit()
    db.refresh(publication)
    log_service.record("integrations", "Validazione esterna vista eSolver aggiornata", actor_email)
    return serialize_esolver_export_publication(db, publication)
