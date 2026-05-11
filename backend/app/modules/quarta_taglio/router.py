from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioArticleDataRequest,
    QuartaTaglioDetailResponse,
    QuartaTaglioListResponse,
    QuartaTaglioStandardSelectionRequest,
)
from app.modules.quarta_taglio.service import (
    confirm_quarta_taglio_standard,
    get_quarta_taglio_detail,
    sync_and_list_quarta_taglio,
    update_quarta_taglio_article_data,
)

router = APIRouter()


@router.get("", response_model=QuartaTaglioListResponse)
def list_quarta_taglio_route(current_user: CurrentUser, db: DbSession) -> QuartaTaglioListResponse:
    return sync_and_list_quarta_taglio(db, actor_id=current_user.id)


@router.get("/{cod_odp}", response_model=QuartaTaglioDetailResponse)
def get_quarta_taglio_detail_route(cod_odp: str, current_user: CurrentUser, db: DbSession) -> QuartaTaglioDetailResponse:
    return get_quarta_taglio_detail(db, cod_odp=cod_odp)


@router.post("/{cod_odp}/standard", response_model=QuartaTaglioDetailResponse)
def confirm_quarta_taglio_standard_route(
    cod_odp: str,
    payload: QuartaTaglioStandardSelectionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioDetailResponse:
    return confirm_quarta_taglio_standard(db, cod_odp=cod_odp, standard_id=payload.standard_id, actor_id=current_user.id)


@router.patch("/{cod_odp}/article-data", response_model=QuartaTaglioDetailResponse)
def update_quarta_taglio_article_data_route(
    cod_odp: str,
    payload: QuartaTaglioArticleDataRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioDetailResponse:
    return update_quarta_taglio_article_data(
        db,
        cod_odp=cod_odp,
        descrizione=payload.descrizione,
        disegno=payload.disegno,
        fields_set=payload.model_fields_set,
        actor_id=current_user.id,
    )
