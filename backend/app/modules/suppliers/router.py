from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.modules.suppliers.schemas import (
    SupplierActionResponse,
    SupplierActiveRequest,
    SupplierAliasCreateRequest,
    SupplierAliasUpdateRequest,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from app.modules.suppliers.service import (
    create_supplier,
    create_supplier_alias,
    get_supplier_alias,
    get_supplier,
    list_suppliers,
    serialize_supplier,
    set_supplier_active,
    update_supplier,
    update_supplier_alias,
)

router = APIRouter()


@router.get("", response_model=SupplierListResponse)
def list_suppliers_route(_: CurrentUser, db: DbSession) -> SupplierListResponse:
    return SupplierListResponse(items=list_suppliers(db))


@router.post("", response_model=SupplierResponse)
def create_supplier_route(payload: SupplierCreateRequest, current_user: CurrentUser, db: DbSession) -> SupplierResponse:
    return create_supplier(db=db, payload=payload, actor_email=current_user.email)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier_route(supplier_id: int, _: CurrentUser, db: DbSession) -> SupplierResponse:
    return serialize_supplier(get_supplier(db, supplier_id))


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier_route(
    supplier_id: int,
    payload: SupplierUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return update_supplier(db=db, supplier=supplier, payload=payload, actor_email=current_user.email)


@router.patch("/{supplier_id}/active", response_model=SupplierResponse)
def update_supplier_active_route(
    supplier_id: int,
    payload: SupplierActiveRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return set_supplier_active(db=db, supplier=supplier, attivo=payload.attivo, actor_email=current_user.email)


@router.post("/{supplier_id}/aliases", response_model=SupplierResponse)
def create_supplier_alias_route(
    supplier_id: int,
    payload: SupplierAliasCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SupplierResponse:
    supplier = get_supplier(db, supplier_id)
    return create_supplier_alias(db=db, supplier=supplier, payload=payload, actor_email=current_user.email)


@router.patch("/aliases/{alias_id}", response_model=SupplierResponse)
def update_supplier_alias_route(
    alias_id: int,
    payload: SupplierAliasUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SupplierResponse:
    alias = get_supplier_alias(db, alias_id)
    return update_supplier_alias(db=db, alias=alias, payload=payload, actor_email=current_user.email)
