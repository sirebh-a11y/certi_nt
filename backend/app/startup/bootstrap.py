from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.ai.models import AIModel, AIProvider  # noqa: F401
from app.core.ai.service import seed_ai_configuration
from app.core.departments.models import Department  # noqa: F401
from app.core.departments.service import seed_departments
from app.core.logs.service import log_service
from app.core.integrations.models import ExternalConnection  # noqa: F401
from app.core.integrations.service import seed_external_connections
from app.core.roles.constants import ROLE_ADMIN
from app.core.security.passwords import hash_password
from app.core.users.models import User
from app.modules.acquisition.models import (  # noqa: F401
    AcquisitionHistoryEvent,
    AcquisitionRow,
    AcquisitionValueHistory,
    AutonomousProcessingRun,
    CertificateMatch,
    CertificateMatchCandidate,
    Document,
    DocumentEvidence,
    DocumentPage,
    ManualMatchBlock,
    ReadValue,
)
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate  # noqa: F401
from app.modules.notes.service import seed_note_templates
from app.modules.quarta_taglio.models import (  # noqa: F401
    QuartaTaglioArticleOverride,
    QuartaTaglioEsolverLink,
    QuartaTaglioFinalCertificate,
    QuartaTaglioRow,
    QuartaTaglioStandardSelection,
    QuartaTaglioSyncRun,
)
from app.modules.standards.models import (  # noqa: F401
    NormativeStandard,
    NormativeStandardChemistry,
    NormativeStandardProperty,
)
from app.modules.standards.service import seed_normative_standards
from app.modules.suppliers.models import Supplier, SupplierAlias  # noqa: F401
from app.modules.suppliers.service import seed_supplier_aliases_from_csv, seed_suppliers_from_csv


def initialize_application() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_document_upload_columns()
    ensure_acquisition_quality_columns()
    ensure_external_connection_columns()
    ensure_quarta_taglio_columns()
    db: Session = SessionLocal()
    try:
        seed_departments(db)
        bootstrap_admin_user(db)
        seed_ai_configuration(db)
        seed_external_connections(db)
        seed_suppliers_from_csv(db)
        seed_supplier_aliases_from_csv(db)
        seed_note_templates(db)
        seed_normative_standards(db)
        log_service.record("system", "Application initialized")
    finally:
        db.close()


def ensure_document_upload_columns() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("documenti_fornitore")}
    statements: list[str] = []

    if "stato_upload" not in columns:
        statements.append("ALTER TABLE documenti_fornitore ADD COLUMN stato_upload VARCHAR(32) NOT NULL DEFAULT 'persistente'")
    if "upload_batch_id" not in columns:
        statements.append("ALTER TABLE documenti_fornitore ADD COLUMN upload_batch_id VARCHAR(64)")
    if "scadenza_batch" not in columns:
        statements.append("ALTER TABLE documenti_fornitore ADD COLUMN scadenza_batch TIMESTAMP WITH TIME ZONE")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_acquisition_quality_columns() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("datimaterialeincoming")}
    statements: list[str] = []

    if "qualita_data_ricezione" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_data_ricezione DATE")
    if "qualita_data_accettazione" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_data_accettazione DATE")
    if "qualita_data_richiesta" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_data_richiesta DATE")
    if "qualita_numero_analisi" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_numero_analisi VARCHAR(128)")
    if "qualita_valutazione" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_valutazione VARCHAR(32)")
    if "qualita_note" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN qualita_note TEXT")
    if "qualita_numero_analisi_da_ricontrollare" not in columns:
        statements.append(
            "ALTER TABLE datimaterialeincoming ADD COLUMN qualita_numero_analisi_da_ricontrollare BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "qualita_note_da_ricontrollare" not in columns:
        statements.append(
            "ALTER TABLE datimaterialeincoming ADD COLUMN qualita_note_da_ricontrollare BOOLEAN NOT NULL DEFAULT FALSE"
        )

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_external_connection_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("external_connections"):
        return

    columns = {column["name"] for column in inspector.get_columns("external_connections")}
    statements: list[str] = []

    if "driver_name" not in columns:
        statements.append(
            "ALTER TABLE external_connections ADD COLUMN driver_name VARCHAR(128) NOT NULL DEFAULT 'ODBC Driver 18 for SQL Server'"
        )

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_quarta_taglio_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("quarta_taglio_rows"):
        return

    columns = {column["name"] for column in inspector.get_columns("quarta_taglio_rows")}
    statements: list[str] = []

    if "des_art" not in columns:
        statements.append("ALTER TABLE quarta_taglio_rows ADD COLUMN des_art TEXT")
    if "taglio_attivo" not in columns:
        statements.append("ALTER TABLE quarta_taglio_rows ADD COLUMN taglio_attivo BOOLEAN DEFAULT false NOT NULL")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    if inspector.has_table("quarta_taglio_final_certificates"):
        certificate_columns = {column["name"] for column in inspector.get_columns("quarta_taglio_final_certificates")}
        certificate_statements: list[str] = []
        if "download_token" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN download_token VARCHAR(128)")
        if "cdq_key" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN cdq_key TEXT")
            certificate_statements.append("CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_cdq_key ON quarta_taglio_final_certificates (cdq_key)")
        if "cert_date" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN cert_date TIMESTAMP WITH TIME ZONE")
            certificate_statements.append("CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_cert_date ON quarta_taglio_final_certificates (cert_date)")
        if "lega_cod_f3" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN lega_cod_f3 TEXT")
        if "cdo_lega" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN cdo_lega TEXT")
        if "fornitore_cliente" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN fornitore_cliente TEXT")
        if certificate_statements:
            with engine.begin() as connection:
                for statement in certificate_statements:
                    connection.execute(text(statement))


def bootstrap_admin_user(db: Session) -> None:
    admin_user = db.query(User).filter(User.role == ROLE_ADMIN).first()
    if admin_user is not None:
        return

    department = db.query(Department).filter(Department.name == "administration").one()
    db.add(
        User(
            name="System Admin",
            email="admin@certi.local",
            password_hash=hash_password("admin123"),
            department_id=department.id,
            role=ROLE_ADMIN,
            active=True,
            force_password_change=True,
            openai_api_key_encrypted=None,
        )
    )
    db.commit()
    log_service.record("system", "Initial admin user created", "admin@certi.local")
