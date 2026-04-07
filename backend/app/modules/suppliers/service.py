import csv
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.logs.service import log_service
from app.modules.suppliers.models import Supplier, SupplierAlias
from app.modules.suppliers.schemas import (
    SupplierAliasCreateRequest,
    SupplierAliasResponse,
    SupplierAliasUpdateRequest,
    SupplierCreateRequest,
    SupplierListItemResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)


def serialize_alias(alias: SupplierAlias) -> SupplierAliasResponse:
    return SupplierAliasResponse(
        id=alias.id,
        nome_alias=alias.nome_alias,
        fonte=alias.fonte,
        attivo=alias.attivo,
    )


def serialize_supplier_list_item(supplier: Supplier) -> SupplierListItemResponse:
    return SupplierListItemResponse(
        id=supplier.id,
        ragione_sociale=supplier.ragione_sociale,
        citta=supplier.citta,
        nazione=supplier.nazione,
        email=supplier.email,
        telefono=supplier.telefono,
        attivo=supplier.attivo,
        alias_count=len(supplier.aliases),
    )


def serialize_supplier(supplier: Supplier) -> SupplierResponse:
    return SupplierResponse(
        id=supplier.id,
        ragione_sociale=supplier.ragione_sociale,
        partita_iva=supplier.partita_iva,
        codice_fiscale=supplier.codice_fiscale,
        indirizzo=supplier.indirizzo,
        cap=supplier.cap,
        citta=supplier.citta,
        provincia=supplier.provincia,
        nazione=supplier.nazione,
        email=supplier.email,
        telefono=supplier.telefono,
        attivo=supplier.attivo,
        note=supplier.note,
        aliases=[serialize_alias(alias) for alias in supplier.aliases],
    )


def list_suppliers(db: Session) -> list[SupplierListItemResponse]:
    suppliers = db.query(Supplier).options(joinedload(Supplier.aliases)).order_by(Supplier.ragione_sociale.asc()).all()
    return [serialize_supplier_list_item(supplier) for supplier in suppliers]


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = (
        db.query(Supplier)
        .options(joinedload(Supplier.aliases))
        .filter(Supplier.id == supplier_id)
        .one_or_none()
    )
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


def get_supplier_alias(db: Session, alias_id: int) -> SupplierAlias:
    alias = db.query(SupplierAlias).options(joinedload(SupplierAlias.supplier)).filter(SupplierAlias.id == alias_id).one_or_none()
    if alias is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier alias not found")
    return alias


def _supplier_name_exists(db: Session, ragione_sociale: str, exclude_supplier_id: int | None = None) -> bool:
    query = db.query(Supplier).filter(func.lower(Supplier.ragione_sociale) == ragione_sociale.lower())
    if exclude_supplier_id is not None:
        query = query.filter(Supplier.id != exclude_supplier_id)
    return query.one_or_none() is not None


def _alias_name_exists(db: Session, nome_alias: str, exclude_alias_id: int | None = None) -> bool:
    query = db.query(SupplierAlias).filter(func.lower(SupplierAlias.nome_alias) == nome_alias.lower())
    if exclude_alias_id is not None:
        query = query.filter(SupplierAlias.id != exclude_alias_id)
    return query.one_or_none() is not None


def create_supplier(db: Session, payload: SupplierCreateRequest, actor_email: str) -> SupplierResponse:
    if _supplier_name_exists(db, payload.ragione_sociale):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier already exists")

    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    created_supplier = get_supplier(db, supplier.id)
    log_service.record("suppliers", f"Supplier created: {created_supplier.ragione_sociale}", actor_email)
    return serialize_supplier(created_supplier)


def update_supplier(db: Session, supplier: Supplier, payload: SupplierUpdateRequest, actor_email: str) -> SupplierResponse:
    if _supplier_name_exists(db, payload.ragione_sociale, exclude_supplier_id=supplier.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier already exists")

    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)

    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    updated_supplier = get_supplier(db, supplier.id)
    log_service.record("suppliers", f"Supplier updated: {updated_supplier.ragione_sociale}", actor_email)
    return serialize_supplier(updated_supplier)


def set_supplier_active(db: Session, supplier: Supplier, attivo: bool, actor_email: str) -> SupplierResponse:
    supplier.attivo = attivo
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    updated_supplier = get_supplier(db, supplier.id)
    state_label = "activated" if attivo else "disabled"
    log_service.record("suppliers", f"Supplier {state_label}: {updated_supplier.ragione_sociale}", actor_email)
    return serialize_supplier(updated_supplier)


def create_supplier_alias(
    db: Session,
    supplier: Supplier,
    payload: SupplierAliasCreateRequest,
    actor_email: str,
) -> SupplierResponse:
    if _alias_name_exists(db, payload.nome_alias):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alias already exists")

    alias = SupplierAlias(
        fornitore_id=supplier.id,
        nome_alias=payload.nome_alias,
        fonte=payload.fonte,
        attivo=payload.attivo,
    )
    db.add(alias)
    db.commit()
    updated_supplier = get_supplier(db, supplier.id)
    log_service.record("suppliers", f"Alias created for {updated_supplier.ragione_sociale}: {payload.nome_alias}", actor_email)
    return serialize_supplier(updated_supplier)


def update_supplier_alias(
    db: Session,
    alias: SupplierAlias,
    payload: SupplierAliasUpdateRequest,
    actor_email: str,
) -> SupplierResponse:
    if _alias_name_exists(db, payload.nome_alias, exclude_alias_id=alias.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alias already exists")

    alias.nome_alias = payload.nome_alias
    alias.fonte = payload.fonte
    alias.attivo = payload.attivo
    db.add(alias)
    db.commit()
    updated_supplier = get_supplier(db, alias.fornitore_id)
    log_service.record("suppliers", f"Alias updated for {updated_supplier.ragione_sociale}: {payload.nome_alias}", actor_email)
    return serialize_supplier(updated_supplier)


def seed_suppliers_from_csv(db: Session) -> None:
    if db.query(Supplier).first() is not None:
        return

    csv_path = _data_file_path("fornitori_import_work_excel.csv")
    if not csv_path.exists():
        return

    inserted = 0
    seen_supplier_names: set[str] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            ragione_sociale = _clean_value(row.get("ragione_sociale"))
            normalized_name = ragione_sociale.lower() if ragione_sociale else None
            if not ragione_sociale or normalized_name in seen_supplier_names:
                continue

            seen_supplier_names.add(normalized_name)
            db.add(
                Supplier(
                    ragione_sociale=ragione_sociale,
                    partita_iva=_clean_value(row.get("partita_iva")),
                    codice_fiscale=_clean_value(row.get("codice_fiscale")),
                    indirizzo=_clean_value(row.get("indirizzo")),
                    cap=_clean_value(row.get("cap")),
                    citta=_clean_value(row.get("citta")),
                    provincia=_clean_value(row.get("provincia")),
                    nazione=_clean_value(row.get("nazione")),
                    email=_clean_value(row.get("email")),
                    telefono=_clean_value(row.get("telefono")),
                    attivo=_parse_bool(row.get("attivo"), default=True),
                    note=_clean_value(row.get("note")),
                )
            )
            inserted += 1

    db.commit()
    if inserted:
        log_service.record("suppliers", f"Initial suppliers seeded from CSV: {inserted}")


def seed_supplier_aliases_from_csv(db: Session) -> None:
    if db.query(SupplierAlias).first() is not None:
        return

    csv_path = _data_file_path("fornitori_alias_import_work.csv")
    if not csv_path.exists():
        return

    suppliers = db.query(Supplier).all()
    supplier_map = {supplier.ragione_sociale: supplier.id for supplier in suppliers}
    inserted = 0
    skipped = 0
    seen_alias_names: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            canonical_name = _clean_value(row.get("ragione_sociale_canonica"))
            nome_alias = _clean_value(row.get("nome_alias"))
            normalized_alias = nome_alias.lower() if nome_alias else None
            if not canonical_name or not nome_alias or normalized_alias in seen_alias_names:
                continue

            supplier_id = supplier_map.get(canonical_name)
            if supplier_id is None:
                skipped += 1
                continue

            seen_alias_names.add(normalized_alias)
            db.add(
                SupplierAlias(
                    fornitore_id=supplier_id,
                    nome_alias=nome_alias,
                    fonte=_clean_value(row.get("fonte")),
                    attivo=_parse_bool(row.get("attivo"), default=True),
                )
            )
            inserted += 1

    db.commit()
    if inserted or skipped:
        log_service.record(
            "suppliers",
            f"Initial supplier aliases seeded from CSV: {inserted}, skipped: {skipped}",
        )


def _data_file_path(filename: str) -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        candidate = parent / "docs" / "modules" / filename
        if candidate.exists():
            return candidate
    return current_path.parents[0] / filename


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_bool(value: str | None, default: bool) -> bool:
    cleaned = _clean_value(value)
    if cleaned is None:
        return default
    return cleaned.lower() in {"true", "1", "yes", "y"}
