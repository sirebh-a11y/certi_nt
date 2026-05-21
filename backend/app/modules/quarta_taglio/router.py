from fastapi import APIRouter, Body, File, Query, UploadFile
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioArticleDataRequest,
    QuartaTaglioDetailResponse,
    QuartaTaglioFinalCertificateRegisterResponse,
    QuartaTaglioListResponse,
    QuartaTaglioStandardSelectionRequest,
    QuartaTaglioWordDraftRequest,
    QuartaTaglioWordDraftResponse,
)
from app.modules.quarta_taglio.service import (
    apply_quick_incoming_confirmation,
    confirm_quarta_taglio_standard,
    create_quarta_taglio_word_draft,
    get_quarta_taglio_additional_page_template_file,
    get_quarta_taglio_detail,
    get_quarta_taglio_word_draft_file,
    list_quarta_taglio_final_certificates,
    sync_and_list_quarta_taglio,
    update_quarta_taglio_article_data,
    update_quarta_taglio_word_fields,
    upload_quarta_taglio_additional_pages,
    upload_quarta_taglio_word_file,
)

router = APIRouter()


@router.get("", response_model=QuartaTaglioListResponse)
def list_quarta_taglio_route(
    current_user: CurrentUser,
    db: DbSession,
    sync: bool = Query(default=True),
    only_taglio_active: bool = Query(default=False),
    hide_certified: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=1000),
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
        hide_certified=hide_certified,
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


@router.get("/additional-pages/template")
def get_quarta_taglio_additional_page_template_route(
    current_user: CurrentUser,
) -> FileResponse:
    path, file_name = get_quarta_taglio_additional_page_template_file()
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )


@router.get("/{cod_odp}", response_model=QuartaTaglioDetailResponse)
def get_quarta_taglio_detail_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
) -> QuartaTaglioDetailResponse:
    return get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id)


@router.post("/{cod_odp}/standard", response_model=QuartaTaglioDetailResponse)
def confirm_quarta_taglio_standard_route(
    cod_odp: str,
    payload: QuartaTaglioStandardSelectionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioDetailResponse:
    return confirm_quarta_taglio_standard(db, cod_odp=cod_odp, standard_id=payload.standard_id, actor_id=current_user.id)


@router.post("/{cod_odp}/quick-incoming-confirm", response_model=QuartaTaglioDetailResponse)
def apply_quick_incoming_confirmation_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
) -> QuartaTaglioDetailResponse:
    return apply_quick_incoming_confirmation(db, cod_odp=cod_odp, certificate_id=certificate_id, actor_id=current_user.id)


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
    payload: QuartaTaglioWordDraftRequest = Body(default_factory=QuartaTaglioWordDraftRequest),
) -> QuartaTaglioWordDraftResponse:
    return create_quarta_taglio_word_draft(
        db,
        cod_odp=cod_odp,
        actor=current_user,
        force_non_conforming=payload.force_non_conforming,
        force_regenerate=payload.force_regenerate,
        certificate_id=payload.certificate_id,
    )


@router.post("/{cod_odp}/word-file", response_model=QuartaTaglioWordDraftResponse)
def upload_quarta_taglio_word_file_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
    file: UploadFile = File(...),
) -> QuartaTaglioWordDraftResponse:
    return upload_quarta_taglio_word_file(db, cod_odp=cod_odp, uploaded_file=file, actor=current_user, certificate_id=certificate_id)


@router.post("/{cod_odp}/word-fields", response_model=QuartaTaglioWordDraftResponse)
def update_quarta_taglio_word_fields_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
) -> QuartaTaglioWordDraftResponse:
    return update_quarta_taglio_word_fields(db, cod_odp=cod_odp, actor=current_user, certificate_id=certificate_id)


@router.post("/{cod_odp}/additional-pages", response_model=QuartaTaglioWordDraftResponse)
def upload_quarta_taglio_additional_pages_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
    file: UploadFile = File(...),
) -> QuartaTaglioWordDraftResponse:
    return upload_quarta_taglio_additional_pages(
        db,
        cod_odp=cod_odp,
        uploaded_file=file,
        actor=current_user,
        certificate_id=certificate_id,
    )


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
