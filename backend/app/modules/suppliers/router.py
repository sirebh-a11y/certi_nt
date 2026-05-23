from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.roles.constants import ROLE_ADMIN
from app.modules.suppliers.schemas import (
    EsolverSupplierListResponse,
    SupplierImportFromEsolverRequest,
    SupplierEsolverSyncResponse,
    SupplierActiveRequest,
    SupplierAliasCreateRequest,
    SupplierAliasUpdateRequest,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.modules.suppliers.service import (
    create_supplier_alias,
    get_supplier_alias,
    get_supplier,
    import_supplier_from_esolver,
    list_esolver_suppliers,
    list_suppliers,
    serialize_supplier,
    set_supplier_active,
    sync_linked_esolver_suppliers,
    update_supplier,
    update_supplier_alias,
)

router = APIRouter()
AdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN))]


@router.get("", response_model=SupplierListResponse)
def list_suppliers_route(_: CurrentUser, db: DbSession) -> SupplierListResponse:
    return SupplierListResponse(items=list_suppliers(db))


@router.get("/esolver", response_model=EsolverSupplierListResponse)
def list_esolver_suppliers_route(
    _: CurrentUser,
    db: DbSession,
    search: str | None = None,
    limit: int = 50,
) -> EsolverSupplierListResponse:
    return list_esolver_suppliers(db, search=search, limit=limit)


@router.post("/esolver/import", response_model=SupplierResponse)
def import_esolver_supplier_route(
    payload: SupplierImportFromEsolverRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierResponse:
    return import_supplier_from_esolver(db=db, payload=payload, actor_email=current_user.email)


@router.post("/esolver/sync-linked", response_model=SupplierEsolverSyncResponse)
def sync_linked_esolver_suppliers_route(current_user: AdminUser, db: DbSession) -> SupplierEsolverSyncResponse:
    return sync_linked_esolver_suppliers(db=db, actor_email=current_user.email)


@router.patch("/aliases/{alias_id}", response_model=SupplierResponse)
def update_supplier_alias_route(
    alias_id: int,
    payload: SupplierAliasUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierResponse:
    alias = get_supplier_alias(db, alias_id)
    return update_supplier_alias(db=db, alias=alias, payload=payload, actor_email=current_user.email)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier_route(supplier_id: int, _: CurrentUser, db: DbSession) -> SupplierResponse:
    return serialize_supplier(get_supplier(db, supplier_id))


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier_route(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return update_supplier(db=db, supplier=supplier, payload=payload, actor_email=current_user.email)


@router.patch("/{supplier_id}/active", response_model=SupplierResponse)
def update_supplier_active_route(
    supplier_id: int,
    payload: SupplierActiveRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return set_supplier_active(db=db, supplier=supplier, attivo=payload.attivo, actor_email=current_user.email)


@router.post("/{supplier_id}/aliases", response_model=SupplierResponse)
def create_supplier_alias_route(
    supplier_id: int,
    payload: SupplierAliasCreateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return create_supplier_alias(db=db, supplier=supplier, payload=payload, actor_email=current_user.email)
