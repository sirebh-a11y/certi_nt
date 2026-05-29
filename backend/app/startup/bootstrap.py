from datetime import UTC, datetime
import json

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
    AcquisitionUploadBatch,
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
from app.modules.customer_requirements.models import CustomerRequirement  # noqa: F401
from app.modules.customer_requirements.service import seed_customer_requirements
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate  # noqa: F401
from app.modules.notes.service import seed_note_templates
from app.modules.quarta_taglio.models import (  # noqa: F401
    QuartaTaglioArticleOverride,
    QuartaTaglioCertificateExtraPages,
    QuartaTaglioCertificatePdfAttachment,
    QuartaTaglioCertificatePdfVersion,
    QuartaTaglioEsolverLink,
    QuartaTaglioFinalCertificate,
    QuartaTaglioIncomingRowOverride,
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
from app.modules.supplier_codes.models import SupplierInstallationCode  # noqa: F401
from app.modules.supplier_codes.service import seed_supplier_installation_codes
from app.modules.suppliers.models import Supplier, SupplierAlias, SupplierEsolverLink  # noqa: F401
from app.modules.suppliers.service import seed_supplier_aliases_from_csv, seed_suppliers_from_csv


def initialize_application(*, recover_interrupted_jobs: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    ensure_document_upload_columns()
    ensure_acquisition_upload_batch_columns()
    ensure_acquisition_processing_run_columns()
    ensure_acquisition_quality_columns()
    ensure_acquisition_supplier_columns()
    ensure_external_connection_columns()
    ensure_quarta_taglio_columns()
    ensure_supplier_installation_code_columns()
    db: Session = SessionLocal()
    try:
        seed_departments(db)
        bootstrap_admin_user(db)
        seed_ai_configuration(db)
        seed_external_connections(db)
        ensure_supplier_columns()
        seed_suppliers_from_csv(db)
        seed_supplier_aliases_from_csv(db)
        seed_supplier_installation_codes(db)
        seed_note_templates(db)
        seed_normative_standards(db)
        seed_customer_requirements(db)
        if recover_interrupted_jobs:
            recover_interrupted_acquisition_runs(db)
            recover_interrupted_upload_batches(db)
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


def ensure_supplier_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("fornitori"):
        return

    columns = {column["name"] for column in inspector.get_columns("fornitori")}
    statements: list[str] = []
    if "reader_template_key" not in columns:
        statements.append("ALTER TABLE fornitori ADD COLUMN reader_template_key VARCHAR(64)")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_supplier_installation_code_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("fornitori_codici_installazione"):
        return

    columns = {column["name"] for column in inspector.get_columns("fornitori_codici_installazione")}
    statements: list[str] = []
    if "esolver_cod_clifor" not in columns:
        statements.append("ALTER TABLE fornitori_codici_installazione ADD COLUMN esolver_cod_clifor VARCHAR(64)")
        statements.append("CREATE INDEX IF NOT EXISTS ix_fornitori_codici_installazione_esolver_cod_clifor ON fornitori_codici_installazione (esolver_cod_clifor)")
    if "esolver_ragione_sociale" not in columns:
        statements.append("ALTER TABLE fornitori_codici_installazione ADD COLUMN esolver_ragione_sociale VARCHAR(255)")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_acquisition_processing_run_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("acquisition_processing_runs"):
        return

    columns = {column["name"] for column in inspector.get_columns("acquisition_processing_runs")}
    statements: list[str] = []

    if "upload_batch_id" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN upload_batch_id VARCHAR(64)")
    if "ddt_document_ids" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN ddt_document_ids TEXT")
    if "certificate_document_ids" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN certificate_document_ids TEXT")
    if "notification_email" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN notification_email VARCHAR(255)")
    if "admin_notification_email" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN admin_notification_email VARCHAR(255)")
    if "expected_upload_document_count" not in columns:
        statements.append("ALTER TABLE acquisition_processing_runs ADD COLUMN expected_upload_document_count INTEGER NOT NULL DEFAULT 0")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_acquisition_upload_batch_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("acquisition_upload_batches"):
        return

    columns = {column["name"] for column in inspector.get_columns("acquisition_upload_batches")}
    statements: list[str] = []

    if "requested_count" not in columns:
        statements.append("ALTER TABLE acquisition_upload_batches ADD COLUMN requested_count INTEGER NOT NULL DEFAULT 0")
    if "uploaded_count" not in columns:
        statements.append("ALTER TABLE acquisition_upload_batches ADD COLUMN uploaded_count INTEGER NOT NULL DEFAULT 0")
    if "failed_count" not in columns:
        statements.append("ALTER TABLE acquisition_upload_batches ADD COLUMN failed_count INTEGER NOT NULL DEFAULT 0")
    if "failed_items_json" not in columns:
        statements.append("ALTER TABLE acquisition_upload_batches ADD COLUMN failed_items_json TEXT")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def _run_document_ids(raw_value: str | None) -> list[int]:
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [int(item) for item in payload if isinstance(item, int) or (isinstance(item, str) and item.isdigit())]


def recover_interrupted_acquisition_runs(db: Session) -> None:
    runs = (
        db.query(AutonomousProcessingRun)
        .filter(AutonomousProcessingRun.stato.in_(("in_coda", "in_esecuzione")))
        .all()
    )
    if not runs:
        return

    now = datetime.now(UTC)
    for run in runs:
        document_ids = [*_run_document_ids(run.ddt_document_ids), *_run_document_ids(run.certificate_document_ids)]
        if document_ids:
            (
                db.query(Document)
                .filter(Document.id.in_(document_ids), Document.stato_elaborazione == "in_lavorazione")
                .update({Document.stato_elaborazione: "errore"}, synchronize_session=False)
            )
        run.stato = "errore"
        run.fase_corrente = "errore"
        run.messaggio_corrente = "Run interrotto da riavvio server"
        run.ultimo_errore = "Interrotto da riavvio server"
        run.finished_at = now
        db.add(run)
        if run.upload_batch_id:
            batch = db.get(AcquisitionUploadBatch, run.upload_batch_id)
            if batch is not None:
                batch.status = "errore"
                batch.active_uploads = 0
                batch.message = "Run interrotto da riavvio server"
                db.add(batch)
    db.commit()


def recover_interrupted_upload_batches(db: Session) -> None:
    batches = db.query(AcquisitionUploadBatch).filter(AcquisitionUploadBatch.active_uploads > 0).all()
    if not batches:
        return
    for batch in batches:
        batch.active_uploads = 0
        if batch.status == "uploading":
            batch.status = "aperto"
            batch.message = "Caricamento interrotto da riavvio server: verifica i documenti caricati"
        elif batch.status == "avvio_ai_prenotato":
            batch.status = "errore"
            batch.message = "Avvio Assistente AI interrotto da riavvio server"
        db.add(batch)
    db.commit()


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


def ensure_acquisition_supplier_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("datimaterialeincoming"):
        return

    columns = {column["name"] for column in inspector.get_columns("datimaterialeincoming")}
    statements: list[str] = []
    if "fornitore_esolver_cod_clifor" not in columns:
        statements.append("ALTER TABLE datimaterialeincoming ADD COLUMN fornitore_esolver_cod_clifor VARCHAR(64)")
        statements.append("CREATE INDEX IF NOT EXISTS ix_datimaterialeincoming_fornitore_esolver_cod_clifor ON datimaterialeincoming (fornitore_esolver_cod_clifor)")

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
        if "unit_key" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN unit_key VARCHAR(512)")
            certificate_statements.append(
                "CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_unit_key ON quarta_taglio_final_certificates (unit_key)"
            )
        if "cod_f3" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN cod_f3 TEXT")
        if "ddt" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN ddt TEXT")
        if "ordine_cliente" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN ordine_cliente TEXT")
        if "quantita" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN quantita FLOAT")
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
        if "conformity_status" not in certificate_columns:
            certificate_statements.append(
                "ALTER TABLE quarta_taglio_final_certificates ADD COLUMN conformity_status VARCHAR(32) DEFAULT 'da_verificare' NOT NULL"
            )
            certificate_statements.append(
                "CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_conformity_status "
                "ON quarta_taglio_final_certificates (conformity_status)"
            )
        if "conformity_issues" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN conformity_issues JSON DEFAULT '[]' NOT NULL")
        if "word_source" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN word_source VARCHAR(32)")
        if "word_original_filename" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN word_original_filename VARCHAR(255)")
        if "word_content_controls" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN word_content_controls JSON DEFAULT '[]' NOT NULL")
        if "word_missing_content_controls" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN word_missing_content_controls JSON DEFAULT '[]' NOT NULL")
        if "pdf_attachments_initialized" not in certificate_columns:
            certificate_statements.append(
                "ALTER TABLE quarta_taglio_final_certificates ADD COLUMN pdf_attachments_initialized BOOLEAN DEFAULT false NOT NULL"
            )
        if "storage_key_pdf" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN storage_key_pdf VARCHAR(512)")
        if "certified_by_user_id" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN certified_by_user_id INTEGER")
            certificate_statements.append(
                "CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_certified_by_user_id "
                "ON quarta_taglio_final_certificates (certified_by_user_id)"
            )
        if "quality_manager_user_id" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN quality_manager_user_id INTEGER")
            certificate_statements.append(
                "CREATE INDEX IF NOT EXISTS ix_quarta_taglio_final_certificates_quality_manager_user_id "
                "ON quarta_taglio_final_certificates (quality_manager_user_id)"
            )
        if "closed_at" not in certificate_columns:
            certificate_statements.append("ALTER TABLE quarta_taglio_final_certificates ADD COLUMN closed_at TIMESTAMP WITH TIME ZONE")
        if certificate_statements:
            with engine.begin() as connection:
                for statement in certificate_statements:
                    connection.execute(text(statement))
        ensure_quarta_taglio_certificate_unit_key_uniqueness()


def ensure_quarta_taglio_certificate_unit_key_uniqueness() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        certificate.id,
                        row_number() OVER (
                            PARTITION BY certificate.unit_key
                            ORDER BY
                                CASE WHEN certificate.status = 'pdf_final' THEN 0 ELSE 1 END,
                                CASE WHEN certificate.storage_key_pdf IS NOT NULL THEN 0 ELSE 1 END,
                                CASE WHEN certificate.word_source IN ('uploaded', 'manual') THEN 0 ELSE 1 END,
                                CASE WHEN certificate.created_by_user_id IS NOT NULL THEN 0 ELSE 1 END,
                                CASE WHEN certificate.storage_key_docx IS NOT NULL THEN 0 ELSE 1 END,
                                certificate.updated_at DESC NULLS LAST,
                                certificate.id ASC
                        ) AS rn
                    FROM quarta_taglio_final_certificates AS certificate
                    WHERE certificate.unit_key IS NOT NULL AND btrim(certificate.unit_key) <> ''
                )
                DELETE FROM quarta_taglio_final_certificates AS certificate
                USING ranked
                WHERE certificate.id = ranked.id
                    AND ranked.rn > 1
                    AND certificate.status <> 'pdf_final'
                    AND certificate.storage_key_pdf IS NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM quarta_taglio_certificate_pdf_versions AS pdf_version
                        WHERE pdf_version.certificate_id = certificate.id
                    )
                """
            )
        )
        duplicate_groups = connection.execute(
            text(
                """
                SELECT count(*)
                FROM (
                    SELECT unit_key
                    FROM quarta_taglio_final_certificates
                    WHERE unit_key IS NOT NULL AND btrim(unit_key) <> ''
                    GROUP BY unit_key
                    HAVING count(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
        if duplicate_groups == 0:
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_quarta_taglio_final_certificates_unit_key_not_null
                    ON quarta_taglio_final_certificates (unit_key)
                    WHERE unit_key IS NOT NULL AND btrim(unit_key) <> ''
                    """
                )
            )


def bootstrap_admin_user(db: Session) -> None:
    it_department = db.query(Department).filter(Department.name == "IT").one()
    system_admin = db.query(User).filter(User.email == "admin@certi.local").one_or_none()
    if system_admin is not None:
        if system_admin.department_id != it_department.id:
            system_admin.department_id = it_department.id
            db.commit()
            log_service.record("system", "System Admin department moved to IT", "admin@certi.local")
        return

    admin_user = db.query(User).filter(User.role == ROLE_ADMIN).first()
    if admin_user is not None:
        return

    db.add(
        User(
            name="System Admin",
            email="admin@certi.local",
            password_hash=hash_password("admin123"),
            department_id=it_department.id,
            role=ROLE_ADMIN,
            active=True,
            force_password_change=True,
            openai_api_key_encrypted=None,
        )
    )
    db.commit()
    log_service.record("system", "Initial admin user created", "admin@certi.local")
