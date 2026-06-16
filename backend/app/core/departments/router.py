from fastapi import APIRouter
from typing import Annotated
from fastapi import Depends

from app.core.departments.schemas import DepartmentListResponse
from app.core.departments.service import list_departments
from app.core.deps import CurrentUser, DbSession, require_it_admin

router = APIRouter()
ItAdminUser = Annotated[CurrentUser, Depends(require_it_admin)]


@router.get("", response_model=DepartmentListResponse)
def list_departments_route(_: ItAdminUser, db: DbSession) -> DepartmentListResponse:
    return DepartmentListResponse(items=list_departments(db))
