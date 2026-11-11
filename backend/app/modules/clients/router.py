from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.integrations.background import background_response
from app.modules.clients.schemas import EsolverClientListResponse
from app.modules.clients.service import list_esolver_clients

router = APIRouter()


@router.get("/esolver", response_model=EsolverClientListResponse)
@background_response
def list_esolver_clients_route(
    _: CurrentUser,
    db: DbSession,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> EsolverClientListResponse:
    return list_esolver_clients(db, search=search, limit=limit, offset=offset)
