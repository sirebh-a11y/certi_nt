from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import require_roles
from app.core.logs.schemas import LogListResponse
from app.core.logs.service import log_service
from app.core.roles.constants import ROLE_ADMIN, ROLE_MANAGER

router = APIRouter()

LogViewer = Annotated[object, Depends(require_roles(ROLE_ADMIN, ROLE_MANAGER))]


@router.get("", response_model=LogListResponse)
def list_logs_route(_: LogViewer) -> LogListResponse:
    return LogListResponse(items=log_service.list_entries())
