from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.logs.service import log_service
from app.modules.supplier_codes.models import SupplierInstallationCode
from app.modules.supplier_codes.schemas import (
    SupplierInstallationCodeCreateRequest,
    SupplierInstallationCodeResponse,
    SupplierInstallationCodeUpdateRequest,
)
from app.modules.suppliers.models import Supplier, SupplierEsolverLink


ESOLVER_CODE_BY_INSTALLATION_CODE: dict[str, tuple[str, str]] = {
    "AA": ("10451", "ALCAN ALLUMINIO S.P.A."),
    "AD": ("11817", "CONSTELLIUM EXTRUSIONS DECIN S.R.O."),
    "AL": ("12007", "ALUMINIUM LAUFEN AG"),
    "AM": ("10060", "AVIOMETAL S.P.A."),
    "AP": ("10348", "PECHINEY ITALIA S.P.A."),
    "CD": ("11817", "CONSTELLIUM EXTRUSIONS DECIN S.R.O."),
    "Eu": ("10148", "EURAL GNUTTI S.P.A."),
    "HA": ("12519", "HYDRO ALUMINIUM DEUTSCHLAND GMBH"),
    "Me": ("10517", "METALLUMINIO S.P.A."),
    "Ra": ("10511", "RALCOM S.R.L."),
    "Ro": ("11812", "RONDAL D.O.O. PREDELAVA BARVNIH KOVIN"),
    "Sa": ("11746", "SAG ALUMINIUM LEND G.M.B.H & CO. KG"),
    "TM": ("10619", "TAU METALLI S.P.A. ALLUMINIO BRONZO OTTONE RAME"),
}


DEFAULT_SUPPLIER_CODES: tuple[dict[str, str], ...] = (
    {"codice": "AA", "label": "Alcan Alupex"},
    {"codice": "AB", "label": "Aluminium Bozen", "reader_template_key": "aluminium_bozen"},
    {"codice": "AD", "label": "Alcan Decin"},
    {"codice": "AH", "label": "Alcoa Hannover - Arconic", "reader_template_key": "arconic_hannover"},
    {"codice": "AL", "label": "Alu Laufen"},
    {"codice": "AM", "label": "Aviometal"},
    {"codice": "AP", "label": "Alcan Pechiney"},
    {"codice": "AW", "label": "AWW", "reader_template_key": "aww"},
    {"codice": "CD", "label": "Constellium Decin"},
    {"codice": "Eu", "label": "Eural - Gnutti"},
    {"codice": "Ke", "label": "Grupa Kety", "reader_template_key": "grupa_kety"},
    {"codice": "HA", "label": "Hydro Aluminium"},
    {"codice": "HH", "label": "Hydro Husnes"},
    {"codice": "Im", "label": "Impol", "reader_template_key": "impol"},
    {"codice": "Int", "label": "Materiale interno"},
    {"codice": "Lm", "label": "Leichtmetall A.", "reader_template_key": "leichtmetall"},
    {"codice": "MB", "label": "Metalba", "reader_template_key": "metalba"},
    {"codice": "Me", "label": "Metalluminio"},
    {"codice": "Ne", "label": "Neuman Aluminium", "reader_template_key": "neuman"},
    {"codice": "Ra", "label": "Ralcom"},
    {"codice": "RaIm", "label": "Ralcom-Impol"},
    {"codice": "Ro", "label": "Rondal"},
    {"codice": "Sa", "label": "Sag Aluminium Lend"},
    {"codice": "SB", "label": "Sapa Bolzano"},
    {"codice": "SF", "label": "Sapa Feltre"},
    {"codice": "Sm", "label": "Somet"},
    {"codice": "TM", "label": "Tau Metalli"},
    {"codice": "Za", "label": "Zalco", "reader_template_key": "zalco"},
)


def serialize_supplier_code(code: SupplierInstallationCode) -> SupplierInstallationCodeResponse:
    supplier_name = code.supplier.ragione_sociale if code.supplier is not None else None
    display_name = supplier_name or code.esolver_ragione_sociale or code.etichetta_manuale or "-"
    link_type = "manuale"
    if code.fornitore_id is not None:
        link_type = "locale"
    elif code.esolver_cod_clifor is not None:
        link_type = "esolver"
    return SupplierInstallationCodeResponse(
        id=code.id,
        codice=code.codice,
        fornitore_id=code.fornitore_id,
        ragione_sociale_fornitore=supplier_name,
        esolver_cod_clifor=code.esolver_cod_clifor,
        esolver_ragione_sociale=code.esolver_ragione_sociale,
        etichetta_manuale=code.etichetta_manuale,
        nome_visualizzato=display_name,
        tipo_collegamento=link_type,
    )


def list_supplier_codes(db: Session) -> list[SupplierInstallationCodeResponse]:
    items = (
        db.query(SupplierInstallationCode)
        .options(joinedload(SupplierInstallationCode.supplier))
        .order_by(func.lower(SupplierInstallationCode.codice).asc(), SupplierInstallationCode.codice.asc())
        .all()
    )
    return [serialize_supplier_code(item) for item in items]


def get_supplier_code(db: Session, code_id: int) -> SupplierInstallationCode:
    item = (
        db.query(SupplierInstallationCode)
        .options(joinedload(SupplierInstallationCode.supplier))
        .filter(SupplierInstallationCode.id == code_id)
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Codice fornitore non trovato")
    return item


def create_supplier_code(
    db: Session,
    payload: SupplierInstallationCodeCreateRequest,
    actor_email: str,
) -> SupplierInstallationCodeResponse:
    if _code_exists(db, payload.codice):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codice già presente")
    item = SupplierInstallationCode()
    _apply_payload(db, item, payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    log_service.record("supplier_codes", f"Supplier code created: {item.codice}", actor_email)
    return serialize_supplier_code(get_supplier_code(db, item.id))


def update_supplier_code(
    db: Session,
    item: SupplierInstallationCode,
    payload: SupplierInstallationCodeUpdateRequest,
    actor_email: str,
) -> SupplierInstallationCodeResponse:
    if _code_exists(db, payload.codice, exclude_id=item.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codice già presente")
    _apply_payload(db, item, payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    log_service.record("supplier_codes", f"Supplier code updated: {item.codice}", actor_email)
    return serialize_supplier_code(get_supplier_code(db, item.id))


def delete_supplier_code(db: Session, item: SupplierInstallationCode, actor_email: str) -> None:
    code = item.codice
    db.delete(item)
    db.commit()
    log_service.record("supplier_codes", f"Supplier code deleted: {code}", actor_email)


def seed_supplier_installation_codes(db: Session) -> None:
    inserted = 0
    updated = 0
    for seed in DEFAULT_SUPPLIER_CODES:
        item = db.query(SupplierInstallationCode).filter(SupplierInstallationCode.codice == seed["codice"]).one_or_none()
        supplier = _find_supplier_by_reader_key(db, seed.get("reader_template_key"))
        esolver_code, esolver_name = _seed_esolver_link(db, seed["codice"], supplier)
        if item is None:
            db.add(
                SupplierInstallationCode(
                    codice=seed["codice"],
                    fornitore_id=supplier.id if supplier is not None else None,
                    esolver_cod_clifor=esolver_code,
                    esolver_ragione_sociale=esolver_name,
                    etichetta_manuale=None if supplier is not None or esolver_code is not None else seed["label"],
                )
            )
            inserted += 1
            continue

        changed = False
        if supplier is not None and item.fornitore_id != supplier.id:
            item.fornitore_id = supplier.id
            changed = True
        if esolver_code is not None and item.esolver_cod_clifor != esolver_code:
            item.esolver_cod_clifor = esolver_code
            changed = True
        if esolver_name is not None and item.esolver_ragione_sociale != esolver_name:
            item.esolver_ragione_sociale = esolver_name
            changed = True
        if (supplier is not None or esolver_code is not None) and item.etichetta_manuale is not None:
            item.etichetta_manuale = None
            changed = True
        if changed:
            db.add(item)
            updated += 1

    if inserted or updated:
        db.commit()
        log_service.record("supplier_codes", f"Supplier installation codes ensured: inserted={inserted}, updated={updated}")


def _apply_payload(
    db: Session,
    item: SupplierInstallationCode,
    payload: SupplierInstallationCodeCreateRequest | SupplierInstallationCodeUpdateRequest,
) -> None:
    supplier = None
    if payload.fornitore_id is not None:
        supplier = db.get(Supplier, payload.fornitore_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fornitore non trovato")

    item.codice = payload.codice
    item.fornitore_id = supplier.id if supplier is not None else None
    item.esolver_cod_clifor = payload.esolver_cod_clifor
    item.esolver_ragione_sociale = payload.esolver_ragione_sociale
    if supplier is not None and supplier.esolver_link is not None:
        item.esolver_cod_clifor = supplier.esolver_link.cod_clifor
        item.esolver_ragione_sociale = supplier.esolver_link.ragione_sociale_esolver
    item.etichetta_manuale = None if supplier is not None or payload.esolver_cod_clifor is not None else payload.etichetta_manuale


def _code_exists(db: Session, codice: str, exclude_id: int | None = None) -> bool:
    query = db.query(SupplierInstallationCode).filter(SupplierInstallationCode.codice == codice)
    if exclude_id is not None:
        query = query.filter(SupplierInstallationCode.id != exclude_id)
    return query.one_or_none() is not None


def _find_supplier_by_reader_key(db: Session, reader_template_key: str | None) -> Supplier | None:
    if not reader_template_key:
        return None
    return db.query(Supplier).filter(Supplier.reader_template_key == reader_template_key).one_or_none()


def _seed_esolver_link(db: Session, codice: str, supplier: Supplier | None) -> tuple[str | None, str | None]:
    if supplier is not None:
        link = db.query(SupplierEsolverLink).filter(SupplierEsolverLink.fornitore_id == supplier.id).one_or_none()
        if link is not None:
            return link.cod_clifor, link.ragione_sociale_esolver
    return ESOLVER_CODE_BY_INSTALLATION_CODE.get(codice, (None, None))
