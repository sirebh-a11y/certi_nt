from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logs.service import log_service
from app.modules.customer_requirements.models import CustomerRequirement
from app.modules.customer_requirements.schemas import (
    CustomerRequirementCreateRequest,
    CustomerRequirementListResponse,
    CustomerRequirementResponse,
    CustomerRequirementUpdateRequest,
)


SEED_PATH = Path(__file__).with_name("data") / "customer_requirements_seed.json"


def list_customer_requirements(db: Session) -> CustomerRequirementListResponse:
    items = (
        db.query(CustomerRequirement)
        .filter(CustomerRequirement.active.is_(True))
        .order_by(CustomerRequirement.cliente.asc(), CustomerRequirement.cod_f3.asc())
        .all()
    )
    return CustomerRequirementListResponse(items=[serialize_customer_requirement(item) for item in items])


def get_customer_requirement(db: Session, requirement_id: int) -> CustomerRequirement:
    item = (
        db.query(CustomerRequirement)
        .filter(CustomerRequirement.id == requirement_id, CustomerRequirement.active.is_(True))
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer requirement not found")
    return item


def create_customer_requirement(
    db: Session,
    *,
    payload: CustomerRequirementCreateRequest,
    actor_email: str,
) -> CustomerRequirementResponse:
    _ensure_unique_cod_f3(db, payload.cod_f3)
    item = CustomerRequirement()
    _apply_payload(item, payload)
    item.active = True
    db.add(item)
    db.commit()
    db.refresh(item)
    log_service.record("customer_requirements", f"Customer requirement created: {item.cod_f3}", actor_email)
    return serialize_customer_requirement(item)


def update_customer_requirement(
    db: Session,
    *,
    requirement: CustomerRequirement,
    payload: CustomerRequirementUpdateRequest,
    actor_email: str,
) -> CustomerRequirementResponse:
    if requirement.cod_f3 != payload.cod_f3:
        _ensure_unique_cod_f3(db, payload.cod_f3)
    _apply_payload(requirement, payload)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    log_service.record("customer_requirements", f"Customer requirement updated: {requirement.cod_f3}", actor_email)
    return serialize_customer_requirement(requirement)


def delete_customer_requirement(
    db: Session,
    *,
    requirement: CustomerRequirement,
    actor_email: str,
) -> None:
    cod_f3 = requirement.cod_f3
    db.delete(requirement)
    db.commit()
    log_service.record("customer_requirements", f"Customer requirement deleted: {cod_f3}", actor_email)


def seed_customer_requirements(db: Session) -> None:
    if db.query(CustomerRequirement).first() is not None:
        return
    if not SEED_PATH.exists():
        return

    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    inserted = 0
    for seed in data:
        db.add(
            CustomerRequirement(
                cod_f3=str(seed["cod_f3"]),
                cliente=str(seed["cliente"]),
                requires_chemical_analysis=bool(seed.get("requires_chemical_analysis")),
                requires_mechanical_mp=bool(seed.get("requires_mechanical_mp")),
                requires_mechanical_forged=bool(seed.get("requires_mechanical_forged")),
                requires_hardness_hb=bool(seed.get("requires_hardness_hb")),
                requires_lot_traceability_text=bool(seed.get("requires_lot_traceability_text")),
                requires_lot_traceability_photo=bool(seed.get("requires_lot_traceability_photo")),
                requires_dimensional=bool(seed.get("requires_dimensional")),
                requires_marking=bool(seed.get("requires_marking")),
                requires_macro_micro=bool(seed.get("requires_macro_micro")),
                requires_ndt=bool(seed.get("requires_ndt")),
                note=seed.get("note"),
                source_sheet=seed.get("source_sheet"),
                source_row=seed.get("source_row"),
                active=True,
            )
        )
        inserted += 1

    if inserted:
        db.commit()
        log_service.record("customer_requirements", f"Initial customer requirements seeded: {inserted}")


def serialize_customer_requirement(item: CustomerRequirement) -> CustomerRequirementResponse:
    return CustomerRequirementResponse.model_validate(item)


def _apply_payload(
    item: CustomerRequirement,
    payload: CustomerRequirementCreateRequest | CustomerRequirementUpdateRequest,
) -> None:
    item.cod_f3 = payload.cod_f3
    item.cliente = payload.cliente
    item.requires_chemical_analysis = payload.requires_chemical_analysis
    item.requires_mechanical_mp = payload.requires_mechanical_mp
    item.requires_mechanical_forged = payload.requires_mechanical_forged
    item.requires_hardness_hb = payload.requires_hardness_hb
    item.requires_lot_traceability_text = payload.requires_lot_traceability_text
    item.requires_lot_traceability_photo = payload.requires_lot_traceability_photo
    item.requires_dimensional = payload.requires_dimensional
    item.requires_marking = payload.requires_marking
    item.requires_macro_micro = payload.requires_macro_micro
    item.requires_ndt = payload.requires_ndt
    item.note = payload.note


def _ensure_unique_cod_f3(db: Session, cod_f3: str) -> None:
    existing = (
        db.query(CustomerRequirement)
        .filter(
            CustomerRequirement.active.is_(True),
            func.lower(CustomerRequirement.cod_f3) == cod_f3.lower(),
        )
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cod. F3 gia presente")
