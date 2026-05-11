from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logs.service import log_service
from app.modules.notes.models import NoteTemplate
from app.modules.notes.schemas import (
    NoteTemplateCreateRequest,
    NoteTemplateListResponse,
    NoteTemplateResponse,
    NoteTemplateUpdateRequest,
)


SYSTEM_NOTE_SEEDS = [
    {
        "code": "us_control_class_a",
        "note_key": "nota_us_control_class_a",
        "note_value": "true",
        "text": "U.S. control according to ASTM 594 or SAE AMS STD 2154 class A.",
        "sort_order": 10,
    },
    {
        "code": "us_control_class_b",
        "note_key": "nota_us_control_class_b",
        "note_value": "true",
        "text": "U.S. control according to ASTM 594 or SAE AMS STD 2154 class B.",
        "sort_order": 20,
    },
    {
        "code": "rohs",
        "note_key": "nota_rohs",
        "note_value": "true",
        "text": (
            "We hereby declare that material is in compliance with DIRECTIVE 2011/65/EU OF THE "
            "EUROPEAN PARLIAMENT AND OF THE COUNCIL of 8 June 2011 on the restriction of the use "
            "of certain hazardous substances (ROHS II) in electrical and electronic equipment."
        ),
        "sort_order": 30,
    },
    {
        "code": "radioactive_free",
        "note_key": "nota_radioactive_free",
        "note_value": "true",
        "text": "Material free from radioactive contamination.",
        "sort_order": 40,
    },
]


def serialize_note_template(note: NoteTemplate) -> NoteTemplateResponse:
    return NoteTemplateResponse.model_validate(note)


def list_note_templates(db: Session) -> NoteTemplateListResponse:
    items = (
        db.query(NoteTemplate)
        .order_by(NoteTemplate.sort_order.asc(), NoteTemplate.id.asc())
        .all()
    )
    return NoteTemplateListResponse(items=[serialize_note_template(item) for item in items])


def get_note_template(db: Session, note_id: int) -> NoteTemplate:
    note = db.get(NoteTemplate, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def create_note_template(
    db: Session,
    *,
    payload: NoteTemplateCreateRequest,
    actor_email: str,
) -> NoteTemplateResponse:
    code = _build_custom_code(db, payload.text)
    sort_order = _next_custom_sort_order(db)
    note = NoteTemplate(
        code=code,
        note_key=None,
        note_value=None,
        text=payload.text,
        is_system=False,
        is_active=payload.is_active,
        sort_order=sort_order,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    log_service.record("notes", f"Custom note created: {note.code}", actor_email)
    return serialize_note_template(note)


def update_note_template(
    db: Session,
    *,
    note: NoteTemplate,
    payload: NoteTemplateUpdateRequest,
    actor_email: str,
) -> NoteTemplateResponse:
    note.text = payload.text
    note.is_active = payload.is_active
    db.add(note)
    db.commit()
    db.refresh(note)
    log_service.record("notes", f"Note updated: {note.code}", actor_email)
    return serialize_note_template(note)


def seed_note_templates(db: Session) -> None:
    inserted = 0
    updated = 0
    for seed in SYSTEM_NOTE_SEEDS:
        existing = db.query(NoteTemplate).filter(NoteTemplate.code == seed["code"]).one_or_none()
        if existing is not None:
            changed = False
            for field in ("note_key", "note_value", "sort_order"):
                seed_value = seed[field]
                if getattr(existing, field) != seed_value:
                    setattr(existing, field, seed_value)
                    changed = True
            if not existing.is_system:
                existing.is_system = True
                changed = True
            if changed:
                updated += 1
            continue
        db.add(
            NoteTemplate(
                code=str(seed["code"]),
                note_key=str(seed["note_key"]),
                note_value=str(seed["note_value"]),
                text=str(seed["text"]),
                is_system=True,
                is_active=True,
                sort_order=int(seed["sort_order"]),
            )
        )
        inserted += 1
    if inserted or updated:
        db.commit()
        if inserted:
            log_service.record("notes", f"Initial note templates seeded: {inserted}")
        if updated:
            log_service.record("notes", f"System note templates updated: {updated}")


def _build_custom_code(db: Session, text: str) -> str:
    slug = _slugify(text) or "custom_note"
    candidate = slug
    counter = 2
    while db.query(NoteTemplate).filter(NoteTemplate.code == candidate).one_or_none() is not None:
        candidate = f"{slug}_{counter}"
        counter += 1
    return candidate


def _next_custom_sort_order(db: Session) -> int:
    current_max = db.query(NoteTemplate.sort_order).order_by(NoteTemplate.sort_order.desc()).limit(1).scalar()
    if current_max is None:
        return 100
    return int(current_max) + 10


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized[:120]
