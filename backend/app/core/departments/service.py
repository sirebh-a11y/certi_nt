from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.departments.models import Department

DEPARTMENTS = [
    ("quality", "Quality"),
    ("administration", "Administration"),
    ("production", "Production"),
    ("managing", "Managing"),
    ("incoming", "Incoming"),
    ("laboratory", "Laboratory"),
]


def seed_departments(db: Session) -> None:
    for name, description in DEPARTMENTS:
        exists = db.query(Department).filter(Department.name == name).one_or_none()
        if exists is None:
            db.add(Department(name=name, description=description))
    db.commit()


def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name.asc()).all()


def get_department_by_name(db: Session, name: str) -> Department:
    department = db.query(Department).filter(Department.name == name).one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid department")
    return department
