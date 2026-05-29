import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.integrations.models import ExternalConnection
from app.core.logs.service import log_service
from app.core.security.crypto import decrypt_secret
from app.modules.suppliers.models import Supplier, SupplierAlias, SupplierEsolverLink
from app.modules.suppliers.schemas import (
    EsolverSupplierListResponse,
    EsolverSupplierResponse,
    SupplierImportFromEsolverRequest,
    SupplierAliasCreateRequest,
    SupplierAliasResponse,
    SupplierAliasUpdateRequest,
    SupplierEsolverLinkResponse,
    SupplierEsolverSyncResponse,
    SupplierListItemResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)


CORE_SUPPLIER_SEED: tuple[dict[str, object], ...] = (
    {
        "ragione_sociale": "Aluminium Bozen S.r.l.",
        "partita_iva": "08685400966",
        "codice_fiscale": None,
        "indirizzo": "Via Toni Ebner 24",
        "cap": "39100",
        "citta": "Bolzano",
        "provincia": "BZ",
        "nazione": "Italy",
        "email": "info@aluminiumbozen.com",
        "telefono": "+39 0471 906111",
        "reader_template_key": "aluminium_bozen",
        "aliases": ("Aluminium Bz", "Sapa Bz"),
        "esolver": {
            "cod_clifor": "11690",
            "ragione_sociale_esolver": "ALUMINIUM BOZEN S.R.L.",
            "cod_alternativo2": "030.01832",
            "partita_iva_esolver": "08585400966",
            "codice_fiscale_esolver": "08585400966",
        },
    },
    {
        "ragione_sociale": "Arconic Extrusions Hannover GmbH",
        "partita_iva": "DE811145164",
        "indirizzo": "Göttinger Chaussee 12-14",
        "cap": "30453",
        "citta": "Hannover",
        "nazione": "Germany",
        "email": "info@arconic.com",
        "telefono": "+49 511 420 75 0",
        "reader_template_key": "arconic_hannover",
        "aliases": ("Arconic Hannover", "Alcoa Extrusions Hannover"),
        "esolver": {
            "cod_clifor": "11827",
            "ragione_sociale_esolver": "ARCONIC EXTRUSIONS HANNOVER GMBH",
            "cod_alternativo2": "033.00815",
            "partita_iva_esolver": "126638240",
        },
    },
    {
        "ragione_sociale": "Aluminium-Werke Wutöschingen AG & Co. KG",
        "partita_iva": "DE142829998",
        "indirizzo": "Werkstraße 4",
        "cap": "79793",
        "citta": "Wutöschingen",
        "nazione": "Germany",
        "email": "information@aww.de",
        "telefono": "+49 7746 81-0",
        "reader_template_key": "aww",
        "aliases": ("AWW",),
        "esolver": {
            "cod_clifor": "11789",
            "ragione_sociale_esolver": "ALUMINIUM-WERKE WUTÖSCHINGEN AG & Co.KG",
            "cod_alternativo2": "033.00476",
            "partita_iva_esolver": "142829998",
        },
    },
    {
        "ragione_sociale": "Grupa Kety S.A.",
        "partita_iva": "PL5490001468",
        "indirizzo": "ul. Kościuszki 111",
        "cap": "32-650",
        "citta": "Kety",
        "nazione": "Poland",
        "email": "kety@grupakety.com",
        "telefono": "+48 33 844 6000",
        "reader_template_key": "grupa_kety",
        "aliases": (),
        "esolver": {
            "cod_clifor": "11781",
            "ragione_sociale_esolver": "GRUPA KETY S.A.",
            "cod_alternativo2": "033.00158",
            "partita_iva_esolver": "5490001468",
        },
    },
    {
        "ragione_sociale": "Impol d.o.o.",
        "partita_iva": "SI45197687",
        "indirizzo": "Partizanska ulica 38",
        "cap": "2310",
        "citta": "Slovenska Bistrica",
        "nazione": "Slovenia",
        "email": "info@impol.si",
        "telefono": "+386 (0)2 8453 100",
        "reader_template_key": "impol",
        "aliases": ("Ralcom-Impol",),
        "esolver": {
            "cod_clifor": "12198",
            "ragione_sociale_esolver": "IMPOL D.O.O.",
            "partita_iva_esolver": "45197687",
        },
    },
    {
        "ragione_sociale": "Leichtmetall Aluminium Giesserei Hannover GmbH",
        "partita_iva": "DE812225504",
        "indirizzo": "Göttinger Straße 143",
        "cap": "34346",
        "citta": "Hann. Münden",
        "nazione": "Germany",
        "email": "Kathrin.Bodenbach@leichtmetall.eu",
        "telefono": "+49 511 89878-472",
        "reader_template_key": "leichtmetall",
        "aliases": ("Leichtmetall", "Leichtmetall A"),
        "esolver": {
            "cod_clifor": "11792",
            "ragione_sociale_esolver": "EGA LEICHTMETALL GMBH",
            "cod_alternativo2": "033.00479",
            "partita_iva_esolver": "812225504",
        },
    },
    {
        "ragione_sociale": "Metalba S.p.A.",
        "partita_iva": "08703710965",
        "indirizzo": "Via Fortogna 100/A",
        "cap": "32013",
        "citta": "Longarone",
        "provincia": "BL",
        "nazione": "Italy",
        "email": "info@metalba.com",
        "telefono": "+39 0424 252300",
        "reader_template_key": "metalba",
        "aliases": (),
        "esolver": {
            "cod_clifor": "11999",
            "ragione_sociale_esolver": "METALBA ALUMINIUM S.P.A.",
            "cod_alternativo2": "030.01853",
            "partita_iva_esolver": "08703710965",
            "codice_fiscale_esolver": "08703710965",
        },
    },
    {
        "ragione_sociale": "Neuman Aluminium Austria GmbH",
        "partita_iva": "ATU46519101",
        "citta": "Marktl",
        "nazione": "Austria",
        "email": "office@neuman.at",
        "telefono": "+43 2762 500-0",
        "reader_template_key": "neuman",
        "aliases": (),
        "esolver": {
            "cod_clifor": "12611",
            "ragione_sociale_esolver": "NEUMAN ALUMINIUM AUSTRIA GMBH",
            "cod_alternativo2": "012.0611",
            "partita_iva_esolver": "U46519101",
        },
    },
    {
        "ragione_sociale": "Zeeland Aluminium Company",
        "partita_iva": "NL851750990B01",
        "citta": "Vlissingen",
        "nazione": "The Netherlands",
        "email": "info@zalco.nl",
        "telefono": "+31 (0) 113 615 000",
        "reader_template_key": "zalco",
        "aliases": ("Zalco",),
        "esolver": {
            "cod_clifor": "12511",
            "ragione_sociale_esolver": "ZALCO BV ZEELAND ALUMINIUM COMPANY",
            "cod_alternativo2": "012.0511",
            "partita_iva_esolver": "851750990B01",
        },
    },
)


def serialize_alias(alias: SupplierAlias) -> SupplierAliasResponse:
    return SupplierAliasResponse(
        id=alias.id,
        nome_alias=alias.nome_alias,
        fonte=alias.fonte,
        attivo=alias.attivo,
    )


def serialize_esolver_link(link: SupplierEsolverLink | None) -> SupplierEsolverLinkResponse | None:
    if link is None:
        return None
    return SupplierEsolverLinkResponse(
        id=link.id,
        cod_clifor=link.cod_clifor,
        ragione_sociale_esolver=link.ragione_sociale_esolver,
        cod_alternativo2=link.cod_alternativo2,
        partita_iva_esolver=link.partita_iva_esolver,
        codice_fiscale_esolver=link.codice_fiscale_esolver,
        indirizzo_esolver=link.indirizzo_esolver,
        cap_esolver=link.cap_esolver,
        citta_esolver=link.citta_esolver,
        provincia_esolver=link.provincia_esolver,
        nazione_esolver=link.nazione_esolver,
        email_esolver=link.email_esolver,
        telefono_esolver=link.telefono_esolver,
        stato_link=link.stato_link,
        last_sync_at=link.last_sync_at,
    )


def serialize_supplier_list_item(supplier: Supplier) -> SupplierListItemResponse:
    return SupplierListItemResponse(
        id=supplier.id,
        ragione_sociale=supplier.ragione_sociale,
        citta=supplier.citta,
        nazione=supplier.nazione,
        email=supplier.email,
        telefono=supplier.telefono,
        reader_template_key=supplier.reader_template_key,
        attivo=supplier.attivo,
        alias_count=len(supplier.aliases),
        esolver_cod_clifor=supplier.esolver_link.cod_clifor if supplier.esolver_link else None,
        esolver_name=supplier.esolver_link.ragione_sociale_esolver if supplier.esolver_link else None,
        esolver_status=supplier.esolver_link.stato_link if supplier.esolver_link else None,
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
        reader_template_key=supplier.reader_template_key,
        attivo=supplier.attivo,
        note=supplier.note,
        aliases=[serialize_alias(alias) for alias in supplier.aliases],
        esolver_link=serialize_esolver_link(supplier.esolver_link),
    )


def list_suppliers(db: Session) -> list[SupplierListItemResponse]:
    suppliers = (
        db.query(Supplier)
        .options(joinedload(Supplier.aliases), joinedload(Supplier.esolver_link))
        .order_by(Supplier.ragione_sociale.asc())
        .all()
    )
    return [serialize_supplier_list_item(supplier) for supplier in suppliers]


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = (
        db.query(Supplier)
        .options(joinedload(Supplier.aliases), joinedload(Supplier.esolver_link))
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


def list_esolver_suppliers(db: Session, search: str | None = None, limit: int = 50) -> EsolverSupplierListResponse:
    rows = _fetch_esolver_supplier_rows(db, search=search, limit=limit)
    if not rows:
        return EsolverSupplierListResponse(items=[])

    linked_by_code = {
        link.cod_clifor: link.fornitore_id
        for link in db.query(SupplierEsolverLink)
        .filter(SupplierEsolverLink.cod_clifor.in_([row["cod_clifor"] for row in rows]))
        .all()
    }
    return EsolverSupplierListResponse(
        items=[
            EsolverSupplierResponse(
                **row,
                in_app=row["cod_clifor"] in linked_by_code,
                app_supplier_id=linked_by_code.get(row["cod_clifor"]),
            )
            for row in rows
        ]
    )


def import_supplier_from_esolver(
    db: Session,
    payload: SupplierImportFromEsolverRequest,
    actor_email: str,
) -> SupplierResponse:
    cod_clifor = payload.cod_clifor.strip()
    existing_link = db.query(SupplierEsolverLink).filter(SupplierEsolverLink.cod_clifor == cod_clifor).one_or_none()
    if existing_link is not None:
        return serialize_supplier(get_supplier(db, existing_link.fornitore_id))

    row = _fetch_esolver_supplier_by_code(db, cod_clifor)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fornitore eSolver non trovato")

    supplier = db.query(Supplier).filter(func.lower(Supplier.ragione_sociale) == row["ragione_sociale"].lower()).one_or_none()
    if supplier is None:
        supplier = Supplier(
            ragione_sociale=row["ragione_sociale"],
            partita_iva=row.get("partita_iva"),
            codice_fiscale=row.get("codice_fiscale"),
            indirizzo=row.get("indirizzo"),
            cap=row.get("cap"),
            citta=row.get("citta"),
            provincia=row.get("provincia"),
            nazione=row.get("nazione"),
            email=row.get("email"),
            telefono=row.get("telefono"),
            attivo=True,
            note="Creato da anagrafica eSolver. Compilare eventuali campi locali e template lettura se diventa fornitore speciale.",
        )
        db.add(supplier)
        db.flush()

    db.add(
        SupplierEsolverLink(
            fornitore_id=supplier.id,
            stato_link="linked",
            **_esolver_link_fields_from_row(row),
        )
    )
    db.commit()
    updated_supplier = get_supplier(db, supplier.id)
    log_service.record("suppliers", f"Supplier linked from eSolver: {updated_supplier.ragione_sociale} ({cod_clifor})", actor_email)
    return serialize_supplier(updated_supplier)


def sync_linked_esolver_suppliers(db: Session, actor_email: str) -> SupplierEsolverSyncResponse:
    links = db.query(SupplierEsolverLink).all()
    updated = 0
    unchanged = 0
    missing: list[str] = []

    for link in links:
        row = _fetch_esolver_supplier_by_code(db, link.cod_clifor)
        if row is None:
            if link.stato_link != "non_trovato":
                link.stato_link = "non_trovato"
                link.last_sync_at = datetime.now(UTC)
                db.add(link)
                updated += 1
            else:
                unchanged += 1
            missing.append(link.cod_clifor)
            continue

        fields = _esolver_link_fields_from_row(row)
        changed = False
        for field, value in fields.items():
            if getattr(link, field) != value:
                setattr(link, field, value)
                changed = True
        if link.stato_link != "linked":
            link.stato_link = "linked"
            changed = True
        if changed:
            db.add(link)
            updated += 1
        else:
            unchanged += 1

    if updated:
        db.commit()
        log_service.record("suppliers", f"Linked eSolver suppliers synced: {updated}", actor_email)

    return SupplierEsolverSyncResponse(updated=updated, unchanged=unchanged, missing=missing)


def seed_suppliers_from_csv(db: Session) -> None:
    if db.query(Supplier).first() is not None:
        ensure_core_supplier_links(db)
        return

    inserted = 0
    seen_supplier_names: set[str] = set()
    for seed in CORE_SUPPLIER_SEED:
        ragione_sociale = str(seed["ragione_sociale"])
        normalized_name = ragione_sociale.lower()
        if normalized_name in seen_supplier_names:
            continue

        seen_supplier_names.add(normalized_name)
        db.add(
            Supplier(
                ragione_sociale=ragione_sociale,
                partita_iva=_clean_value(seed.get("partita_iva")),
                codice_fiscale=_clean_value(seed.get("codice_fiscale")),
                indirizzo=_clean_value(seed.get("indirizzo")),
                cap=_clean_value(seed.get("cap")),
                citta=_clean_value(seed.get("citta")),
                provincia=_clean_value(seed.get("provincia")),
                nazione=_clean_value(seed.get("nazione")),
                email=_clean_value(seed.get("email")),
                telefono=_clean_value(seed.get("telefono")),
                reader_template_key=_clean_value(seed.get("reader_template_key")),
                attivo=True,
                note=_clean_value(seed.get("note")),
            )
        )
        inserted += 1

    db.commit()
    ensure_core_supplier_links(db)
    if inserted:
        log_service.record("suppliers", f"Initial core suppliers seeded: {inserted}")


def seed_supplier_aliases_from_csv(db: Session) -> None:
    if db.query(SupplierAlias).first() is not None:
        ensure_core_supplier_links(db)
        return
    ensure_core_supplier_links(db)


def ensure_core_supplier_links(db: Session) -> None:
    changed = False
    for seed in CORE_SUPPLIER_SEED:
        supplier = _find_supplier_for_core_seed(db, seed)
        if supplier is None:
            continue

        template_key = _clean_value(seed.get("reader_template_key"))
        if template_key and not supplier.reader_template_key:
            supplier.reader_template_key = template_key
            db.add(supplier)
            changed = True

        for alias_name in seed.get("aliases", ()):
            if _add_alias_if_available(db, supplier, str(alias_name), fonte="seed core"):
                changed = True

        esolver_data = seed.get("esolver")
        if not isinstance(esolver_data, dict):
            continue

        fields = _esolver_link_fields_from_seed(esolver_data)
        link = db.query(SupplierEsolverLink).filter(SupplierEsolverLink.cod_clifor == fields["cod_clifor"]).one_or_none()
        now = datetime.now(UTC)
        if link is None:
            db.add(
                SupplierEsolverLink(
                    fornitore_id=supplier.id,
                    stato_link="linked",
                    last_sync_at=now,
                    **fields,
                )
            )
            changed = True
        elif link.fornitore_id == supplier.id:
            for field, value in fields.items():
                if getattr(link, field) != value:
                    setattr(link, field, value)
                    changed = True
            link.stato_link = "linked"
            link.last_sync_at = now
            db.add(link)

    if changed:
        db.commit()
        log_service.record("suppliers", "Core supplier reader keys and eSolver links ensured")


def _find_supplier_for_core_seed(db: Session, seed: dict[str, object]) -> Supplier | None:
    names = [str(seed["ragione_sociale"])]
    names.extend(str(alias) for alias in seed.get("aliases", ()))
    for name in names:
        supplier = db.query(Supplier).filter(func.lower(Supplier.ragione_sociale) == name.lower()).one_or_none()
        if supplier is not None:
            return supplier
    for name in names:
        alias = db.query(SupplierAlias).filter(func.lower(SupplierAlias.nome_alias) == name.lower()).one_or_none()
        if alias is not None:
            return alias.supplier
    return None


def _add_alias_if_available(db: Session, supplier: Supplier, alias_name: str, *, fonte: str) -> bool:
    cleaned = _clean_value(alias_name)
    if cleaned is None or cleaned.casefold() == supplier.ragione_sociale.casefold():
        return False
    existing_supplier = db.query(Supplier).filter(func.lower(Supplier.ragione_sociale) == cleaned.lower()).one_or_none()
    if existing_supplier is not None and existing_supplier.id != supplier.id:
        return False
    existing_alias = db.query(SupplierAlias).filter(func.lower(SupplierAlias.nome_alias) == cleaned.lower()).one_or_none()
    if existing_alias is not None:
        return False
    db.add(SupplierAlias(fornitore_id=supplier.id, nome_alias=cleaned, fonte=fonte, attivo=True))
    return True


def _esolver_link_fields_from_seed(esolver_data: dict[str, object]) -> dict[str, str | None]:
    return {
        "cod_clifor": str(esolver_data["cod_clifor"]),
        "ragione_sociale_esolver": _clean_value(esolver_data.get("ragione_sociale_esolver")),
        "cod_alternativo2": _clean_value(esolver_data.get("cod_alternativo2")),
        "partita_iva_esolver": _clean_value(esolver_data.get("partita_iva_esolver")),
        "codice_fiscale_esolver": _clean_value(esolver_data.get("codice_fiscale_esolver")),
        "indirizzo_esolver": _clean_value(esolver_data.get("indirizzo_esolver")),
        "cap_esolver": _clean_value(esolver_data.get("cap_esolver")),
        "citta_esolver": _clean_value(esolver_data.get("citta_esolver")),
        "provincia_esolver": _clean_value(esolver_data.get("provincia_esolver")),
        "nazione_esolver": _clean_value(esolver_data.get("nazione_esolver")),
        "email_esolver": _clean_value(esolver_data.get("email_esolver")),
        "telefono_esolver": _clean_value(esolver_data.get("telefono_esolver")),
    }


def _esolver_link_fields_from_row(row: dict[str, str | None]) -> dict[str, str | None]:
    return {
        "cod_clifor": row["cod_clifor"],
        "ragione_sociale_esolver": row["ragione_sociale"],
        "cod_alternativo2": row.get("cod_alternativo2"),
        "partita_iva_esolver": row.get("partita_iva"),
        "codice_fiscale_esolver": row.get("codice_fiscale"),
        "indirizzo_esolver": row.get("indirizzo"),
        "cap_esolver": row.get("cap"),
        "citta_esolver": row.get("citta"),
        "provincia_esolver": row.get("provincia"),
        "nazione_esolver": row.get("nazione"),
        "email_esolver": row.get("email"),
        "telefono_esolver": row.get("telefono"),
        "last_sync_at": datetime.now(UTC),
    }


def _fetch_esolver_supplier_by_code(db: Session, cod_clifor: str) -> dict[str, str | None] | None:
    rows = _fetch_esolver_supplier_rows(db, cod_clifor=cod_clifor, limit=1)
    return rows[0] if rows else None


def _fetch_esolver_supplier_rows(
    db: Session,
    *,
    search: str | None = None,
    cod_clifor: str | None = None,
    limit: int = 50,
) -> list[dict[str, str | None]]:
    connection = db.query(ExternalConnection).filter(ExternalConnection.code == "esolver").one_or_none()
    if connection is None or not connection.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connessione eSolver non configurata o disabilitata")
    if not connection.password_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password eSolver non configurata")

    try:
        import pymssql
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Driver SQL Server pymssql non installato") from exc

    schema_name = _sql_identifier(connection.schema_name or "dbo")
    object_settings = connection.object_settings or {}
    view_name = _sql_identifier(str(object_settings.get("anagrafiche_view") or "CertiCliForF3"))
    if schema_name is None or view_name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome vista eSolver non valido")

    where = ["TipoAnagrafica = 2"]
    params: list[Any] = []
    if cod_clifor:
        where.append("CodCliFor = %s")
        params.append(cod_clifor)
    elif search:
        like = f"%{search.strip()}%"
        where.append("(RagSoc1 LIKE %s OR CodCliFor LIKE %s OR PartitaIva LIKE %s OR CodAlternativo2 LIKE %s)")
        params.extend([like, like, like, like])

    max_rows = max(1, min(limit, 1000))
    query = (
        f"SELECT TOP {max_rows} CodCliFor, RagSoc1, RagSoc2, Indirizzo, Indirizzo2, Localita, "
        f"Localita2, Provincia, Cap, CodStato, IndirEmail, NumTel, NumTel2, CodFiscale, PartitaIva, CodAlternativo2 "
        f"FROM [{schema_name}].[{view_name}] "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY RagSoc1 ASC, CodCliFor ASC"
    )
    password = decrypt_secret(connection.password_encrypted)
    try:
        with pymssql.connect(
            server=connection.server_host,
            port=connection.port,
            user=connection.username,
            password=password,
            database=connection.database_name,
            login_timeout=connection.connection_timeout,
            timeout=connection.query_timeout,
            as_dict=True,
        ) as sql_connection:
            with sql_connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return [_serialize_esolver_supplier_row(row) for row in cursor.fetchall()]
    except pymssql.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eSolver non raggiungibile: verifica connessione, VPN/rete server o parametri del connettore.",
        ) from exc


def _serialize_esolver_supplier_row(row: dict[str, Any]) -> dict[str, str | None]:
    name_parts = [_clean_value(row.get("RagSoc1")), _clean_value(row.get("RagSoc2"))]
    address_parts = [_clean_value(row.get("Indirizzo")), _clean_value(row.get("Indirizzo2"))]
    city_parts = [_clean_value(row.get("Localita")), _clean_value(row.get("Localita2"))]
    return {
        "cod_clifor": str(row.get("CodCliFor") or "").strip(),
        "ragione_sociale": " ".join(part for part in name_parts if part),
        "partita_iva": _clean_value(row.get("PartitaIva")),
        "codice_fiscale": _clean_value(row.get("CodFiscale")),
        "indirizzo": " ".join(part for part in address_parts if part) or None,
        "cap": _clean_value(row.get("Cap")),
        "citta": " ".join(part for part in city_parts if part) or None,
        "provincia": _clean_value(row.get("Provincia")),
        "nazione": _clean_value(row.get("CodStato")),
        "email": _clean_value(row.get("IndirEmail")),
        "telefono": _clean_value(row.get("NumTel")) or _clean_value(row.get("NumTel2")),
        "cod_alternativo2": _clean_value(row.get("CodAlternativo2")),
    }


def _sql_identifier(value: str | None) -> str | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    if not cleaned.replace("_", "").isalnum():
        return None
    return cleaned


def _data_file_path(filename: str) -> Path:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        candidate = parent / "docs" / "modules" / filename
        if candidate.exists():
            return candidate
    return current_path.parents[0] / filename


def _clean_value(value: object | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _parse_bool(value: str | None, default: bool) -> bool:
    cleaned = _clean_value(value)
    if cleaned is None:
        return default
    return cleaned.lower() in {"true", "1", "yes", "y"}
