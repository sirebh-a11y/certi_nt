from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.roles.constants import ROLE_ADMIN
from app.modules.supplier_codes.schemas import (
    SupplierInstallationCodeCreateRequest,
    SupplierInstallationCodeListResponse,
    SupplierInstallationCodeResponse,
    SupplierInstallationCodeUpdateRequest,
)
from app.modules.supplier_codes.service import (
    create_supplier_code,
    delete_supplier_code,
    get_supplier_code,
    list_supplier_codes,
    update_supplier_code,
)

router = APIRouter()
AdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN))]


@router.get("", response_model=SupplierInstallationCodeListResponse)
def list_supplier_codes_route(_: CurrentUser, db: DbSession) -> SupplierInstallationCodeListResponse:
    return SupplierInstallationCodeListResponse(items=list_supplier_codes(db))


@router.post("", response_model=SupplierInstallationCodeResponse)
def create_supplier_code_route(
    payload: SupplierInstallationCodeCreateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierInstallationCodeResponse:
    return create_supplier_code(db=db, payload=payload, actor_email=current_user.email)


@router.put("/{code_id}", response_model=SupplierInstallationCodeResponse)
def update_supplier_code_route(
    code_id: int,
    payload: SupplierInstallationCodeUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> SupplierInstallationCodeResponse:
    item = get_supplier_code(db, code_id)
    return update_supplier_code(db=db, item=item, payload=payload, actor_email=current_user.email)


@router.delete("/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_code_route(code_id: int, current_user: AdminUser, db: DbSession) -> Response:
    item = get_supplier_code(db, code_id)
    delete_supplier_code(db=db, item=item, actor_email=current_user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
