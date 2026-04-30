from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.departments.models import Department  # noqa: F401
from app.core.departments.service import seed_departments
from app.core.logs.service import log_service
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
from app.modules.suppliers.models import Supplier, SupplierAlias  # noqa: F401
from app.modules.suppliers.service import seed_supplier_aliases_from_csv, seed_suppliers_from_csv


def initialize_application() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_document_upload_columns()
    db: Session = SessionLocal()
    try:
        seed_departments(db)
        bootstrap_admin_user(db)
        seed_suppliers_from_csv(db)
        seed_supplier_aliases_from_csv(db)
        seed_note_templates(db)
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

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
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
