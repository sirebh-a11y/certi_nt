from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.modules.quarta_taglio.schemas import QuartaTaglioListResponse
from app.modules.quarta_taglio.service import sync_and_list_quarta_taglio

router = APIRouter()


@router.get("", response_model=QuartaTaglioListResponse)
def list_quarta_taglio_route(current_user: CurrentUser, db: DbSession) -> QuartaTaglioListResponse:
    return sync_and_list_quarta_taglio(db, actor_id=current_user.id)
