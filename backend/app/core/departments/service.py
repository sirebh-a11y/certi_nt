from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.departments.models import Department
from app.core.users.models import User

DEPARTMENTS = [
    ("Qualità", "Qualità"),
    ("Amministrazione", "Amministrazione"),
    ("Produzione", "Produzione"),
    ("Direzione", "Direzione"),
    ("Incoming", "Incoming"),
    ("Laboratorio", "Laboratorio"),
    ("IT", "IT"),
]

LEGACY_DEPARTMENT_NAMES = {
    "quality": "Qualità",
    "administration": "Amministrazione",
    "production": "Produzione",
    "managing": "Direzione",
    "incoming": "Incoming",
    "laboratory": "Laboratorio",
}


def migrate_department_names(db: Session) -> None:
    for legacy_name, canonical_name in LEGACY_DEPARTMENT_NAMES.items():
        legacy = db.query(Department).filter(Department.name == legacy_name).one_or_none()
        if legacy is None:
            continue

        canonical = db.query(Department).filter(Department.name == canonical_name).one_or_none()
        if canonical is None:
            legacy.name = canonical_name
            legacy.description = canonical_name
            continue

        if legacy.id != canonical.id:
            db.query(User).filter(User.department_id == legacy.id).update({User.department_id: canonical.id})
            db.delete(legacy)


def seed_departments(db: Session) -> None:
    migrate_department_names(db)
    db.flush()
    for name, description in DEPARTMENTS:
        db.execute(
            text(
                """
                INSERT INTO departments (name, description)
                VALUES (:name, :description)
                ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
                """
            ),
            {"name": name, "description": description},
        )
    db.commit()


def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name.asc()).all()


def get_department_by_name(db: Session, name: str) -> Department:
    department = db.query(Department).filter(Department.name == name).one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department")
    return department
