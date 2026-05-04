from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.logs.service import log_service
from app.modules.standards.models import (
    NormativeStandard,
    NormativeStandardChemistry,
    NormativeStandardProperty,
)
from app.modules.standards.schemas import (
    StandardChemistryPayload,
    StandardCreateRequest,
    StandardListResponse,
    StandardPropertyPayload,
    StandardResponse,
    StandardUpdateRequest,
)


SEED_VERSION = "excel_prova_analisi_v1"
SEED_PATH = Path(__file__).with_name("data") / "standards_seed.json"


def list_standards(
    db: Session,
    *,
    lega: str | None = None,
    stato: str | None = None,
) -> StandardListResponse:
    query = db.query(NormativeStandard).options(
        selectinload(NormativeStandard.chemistry_limits),
        selectinload(NormativeStandard.property_limits),
    )
    if lega:
        query = query.filter(NormativeStandard.lega_base.ilike(f"%{lega.strip()}%"))
    if stato:
        query = query.filter(NormativeStandard.stato_validazione == stato)
    items = (
        query.order_by(
            NormativeStandard.lega_base.asc(),
            NormativeStandard.lega_designazione.asc(),
            NormativeStandard.norma.asc().nulls_last(),
            NormativeStandard.trattamento_termico.asc().nulls_last(),
            NormativeStandard.tipo_prodotto.asc().nulls_last(),
            NormativeStandard.id.asc(),
        )
        .all()
    )
    return StandardListResponse(items=[serialize_standard(item) for item in items])


def get_standard(db: Session, standard_id: int) -> NormativeStandard:
    item = (
        db.query(NormativeStandard)
        .options(
            selectinload(NormativeStandard.chemistry_limits),
            selectinload(NormativeStandard.property_limits),
        )
        .filter(NormativeStandard.id == standard_id)
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standard not found")
    return item


def create_standard(
    db: Session,
    *,
    payload: StandardCreateRequest,
    actor_email: str,
) -> StandardResponse:
    _ensure_unique_code(db, payload.code)
    _validate_payload_limits(payload)
    item = NormativeStandard()
    _apply_standard_payload(item, payload)
    item.chemistry_limits = [_chemistry_from_payload(limit) for limit in payload.chemistry]
    item.property_limits = [_property_from_payload(limit) for limit in payload.properties]
    db.add(item)
    db.commit()
    db.refresh(item)
    log_service.record("standards", f"Standard created: {item.code}", actor_email)
    return serialize_standard(get_standard(db, item.id))


def update_standard(
    db: Session,
    *,
    standard: NormativeStandard,
    payload: StandardUpdateRequest,
    actor_email: str,
) -> StandardResponse:
    if standard.code != payload.code:
        _ensure_unique_code(db, payload.code)
    _validate_payload_limits(payload)
    _apply_standard_payload(standard, payload)
    db.add(standard)
    standard.chemistry_limits.clear()
    standard.property_limits.clear()
    db.flush()
    standard.chemistry_limits = [_chemistry_from_payload(limit) for limit in payload.chemistry]
    standard.property_limits = [_property_from_payload(limit) for limit in payload.properties]
    db.commit()
    db.refresh(standard)
    log_service.record("standards", f"Standard updated: {standard.code}", actor_email)
    return serialize_standard(get_standard(db, standard.id))


def seed_normative_standards(db: Session) -> None:
    if not SEED_PATH.exists():
        return
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    inserted = 0
    for seed in data:
        code = str(seed["code"])
        existing = db.query(NormativeStandard).filter(NormativeStandard.code == code).one_or_none()
        if existing is not None:
            continue
        payload = StandardCreateRequest(
            code=code,
            lega_base=str(seed["lega_base"]),
            lega_designazione=str(seed["lega_designazione"]),
            variante_lega=seed.get("variante_lega"),
            norma=seed.get("norma"),
            trattamento_termico=seed.get("trattamento_termico"),
            tipo_prodotto=seed.get("tipo_prodotto"),
            misura_tipo=seed.get("misura_tipo"),
            fonte_excel_foglio=seed.get("fonte_excel_foglio"),
            fonte_excel_blocco=seed.get("fonte_excel_blocco"),
            stato_validazione=str(seed.get("stato_validazione") or "attivo"),
            note=seed.get("note") or f"Seed iniziale {SEED_VERSION}",
            chemistry=[StandardChemistryPayload(**item) for item in seed.get("chemistry", [])],
            properties=[StandardPropertyPayload(**item) for item in seed.get("properties", [])],
        )
        item = NormativeStandard()
        _apply_standard_payload(item, payload)
        item.chemistry_limits = [_chemistry_from_payload(limit) for limit in payload.chemistry]
        item.property_limits = [_property_from_payload(limit) for limit in payload.properties]
        db.add(item)
        inserted += 1
    if inserted:
        db.commit()
        log_service.record("standards", f"Initial normative standards seeded: {inserted}")


def serialize_standard(item: NormativeStandard) -> StandardResponse:
    return StandardResponse(
        id=item.id,
        code=item.code,
        lega_base=item.lega_base,
        lega_designazione=item.lega_designazione,
        variante_lega=item.variante_lega,
        norma=item.norma,
        trattamento_termico=item.trattamento_termico,
        tipo_prodotto=item.tipo_prodotto,
        misura_tipo=item.misura_tipo,
        fonte_excel_foglio=item.fonte_excel_foglio,
        fonte_excel_blocco=item.fonte_excel_blocco,
        stato_validazione=item.stato_validazione,
        note=item.note,
        created_at=item.created_at,
        updated_at=item.updated_at,
        chemistry=list(item.chemistry_limits),
        properties=list(item.property_limits),
    )


def _apply_standard_payload(item: NormativeStandard, payload: StandardCreateRequest | StandardUpdateRequest) -> None:
    item.code = payload.code or _slugify(
        " ".join(
            part
            for part in (
                payload.lega_designazione,
                payload.norma,
                payload.trattamento_termico,
                payload.tipo_prodotto,
                payload.misura_tipo,
            )
            if part
        )
    )
    item.lega_base = payload.lega_base
    item.lega_designazione = payload.lega_designazione
    item.variante_lega = payload.variante_lega
    item.norma = payload.norma
    item.trattamento_termico = payload.trattamento_termico
    item.tipo_prodotto = payload.tipo_prodotto
    item.misura_tipo = payload.misura_tipo
    item.fonte_excel_foglio = payload.fonte_excel_foglio
    item.fonte_excel_blocco = payload.fonte_excel_blocco
    item.stato_validazione = payload.stato_validazione
    item.note = payload.note


def _chemistry_from_payload(payload: StandardChemistryPayload) -> NormativeStandardChemistry:
    return NormativeStandardChemistry(
        elemento=payload.elemento,
        min_value=payload.min_value,
        max_value=payload.max_value,
    )


def _property_from_payload(payload: StandardPropertyPayload) -> NormativeStandardProperty:
    return NormativeStandardProperty(
        categoria="meccanica",
        proprieta=payload.proprieta,
        misura_min=payload.misura_min,
        misura_max=payload.misura_max,
        range_label=payload.range_label,
        min_value=payload.min_value,
        max_value=payload.max_value,
    )


def _validate_payload_limits(payload: StandardCreateRequest | StandardUpdateRequest) -> None:
    seen_elements: set[str] = set()
    for limit in payload.chemistry:
      element = limit.elemento.strip()
      if element in seen_elements:
          raise HTTPException(
              status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
              detail=f"Duplicate chemistry element: {element}",
          )
      seen_elements.add(element)

    seen_properties: set[tuple[str, float | None, float | None]] = set()
    for limit in payload.properties:
        key = (limit.proprieta.strip(), limit.misura_min, limit.misura_max)
        if key in seen_properties:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Duplicate property range: {limit.proprieta}",
            )
        seen_properties.add(key)


def _ensure_unique_code(db: Session, code: str) -> None:
    existing = db.query(NormativeStandard).filter(NormativeStandard.code == code).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Standard code already exists")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "standard"
