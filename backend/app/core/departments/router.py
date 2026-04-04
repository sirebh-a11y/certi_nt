from fastapi import APIRouter

from app.core.departments.schemas import DepartmentListResponse
from app.core.departments.service import list_departments
from app.core.deps import CurrentUser, DbSession

router = APIRouter()


@router.get("", response_model=DepartmentListResponse)
def list_departments_route(_: CurrentUser, db: DbSession) -> DepartmentListResponse:
    return DepartmentListResponse(items=list_departments(db))
