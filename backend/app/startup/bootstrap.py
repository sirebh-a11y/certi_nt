from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.departments.models import Department  # noqa: F401
from app.core.departments.service import seed_departments
from app.core.logs.service import log_service
from app.core.roles.constants import ROLE_ADMIN
from app.core.security.passwords import hash_password
from app.core.users.models import User


def initialize_application() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        seed_departments(db)
        bootstrap_admin_user(db)
        log_service.record("system", "Application initialized")
    finally:
        db.close()


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
