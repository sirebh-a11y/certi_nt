from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioArticleDataRequest,
    QuartaTaglioDetailResponse,
    QuartaTaglioFinalCertificateRegisterResponse,
    QuartaTaglioListResponse,
    QuartaTaglioStandardSelectionRequest,
    QuartaTaglioWordDraftResponse,
)
from app.modules.quarta_taglio.service import (
    confirm_quarta_taglio_standard,
    create_quarta_taglio_word_draft,
    get_quarta_taglio_detail,
    get_quarta_taglio_word_draft_file,
    list_quarta_taglio_final_certificates,
    sync_and_list_quarta_taglio,
    update_quarta_taglio_article_data,
)

router = APIRouter()


@router.get("", response_model=QuartaTaglioListResponse)
def list_quarta_taglio_route(
    current_user: CurrentUser,
    db: DbSession,
    sync: bool = Query(default=True),
    only_taglio_active: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    query_one: str | None = Query(default=None),
    query_two: str | None = Query(default=None),
    query_three: str | None = Query(default=None),
    operator_one: str = Query(default="and"),
    operator_two: str = Query(default="and"),
    sort_field: str | None = Query(default=None),
    sort_direction: str = Query(default="asc"),
) -> QuartaTaglioListResponse:
    return sync_and_list_quarta_taglio(
        db,
        actor_id=current_user.id,
        sync_data=sync,
        only_taglio_active=only_taglio_active,
        limit=limit,
        offset=offset,
        query_one=query_one,
        query_two=query_two,
        query_three=query_three,
        operator_one=operator_one,
        operator_two=operator_two,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )


@router.get("/certificates/register", response_model=QuartaTaglioFinalCertificateRegisterResponse)
def list_quarta_taglio_final_certificates_route(
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioFinalCertificateRegisterResponse:
    return list_quarta_taglio_final_certificates(db)


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


@router.post("/{cod_odp}/word-draft", response_model=QuartaTaglioWordDraftResponse)
def create_quarta_taglio_word_draft_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioWordDraftResponse:
    return create_quarta_taglio_word_draft(db, cod_odp=cod_odp, actor=current_user)


@router.get("/word-drafts/{draft_id}/file")
def get_quarta_taglio_word_draft_file_route(
    draft_id: int,
    db: DbSession,
    download_token: str | None = Query(default=None),
) -> FileResponse:
    path, file_name = get_quarta_taglio_word_draft_file(db, draft_id=draft_id, download_token=download_token)
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )
