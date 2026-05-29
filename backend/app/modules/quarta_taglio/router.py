from fastapi import APIRouter, Body, File, Query, UploadFile
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioArticleDataRequest,
    QuartaTaglioDetailResponse,
    QuartaTaglioFinalCertificateRegisterItem,
    QuartaTaglioFinalCertificateRegisterResponse,
    QuartaTaglioIncomingRowOverrideRequest,
    QuartaTaglioListResponse,
    QuartaTaglioPdfReopenRequest,
    QuartaTaglioStandardSelectionRequest,
    QuartaTaglioWordDraftRequest,
    QuartaTaglioWordDraftResponse,
)
from app.modules.quarta_taglio.service import (
    apply_quick_incoming_confirmation,
    confirm_quarta_taglio_standard,
    create_quarta_taglio_word_draft,
    generate_quarta_taglio_certificate_pdf,
    get_quarta_taglio_additional_page_template_file,
    get_quarta_taglio_certificate_pdf_file,
    get_quarta_taglio_detail,
    get_quarta_taglio_word_draft_file,
    list_quarta_taglio_final_certificates,
    reopen_quarta_taglio_certificate_pdf,
    set_quarta_taglio_incoming_row_override,
    sync_and_list_quarta_taglio,
    update_quarta_taglio_article_data,
    upload_quarta_taglio_additional_pages,
    upload_quarta_taglio_pdf_attachment,
    upload_quarta_taglio_word_file,
    delete_quarta_taglio_pdf_attachment,
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


@router.post("/certificates/{certificate_id}/pdf", response_model=QuartaTaglioFinalCertificateRegisterItem)
def generate_quarta_taglio_certificate_pdf_route(
    certificate_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioFinalCertificateRegisterItem:
    return generate_quarta_taglio_certificate_pdf(db, certificate_id=certificate_id, actor=current_user)


@router.post("/certificates/{certificate_id}/reopen", response_model=QuartaTaglioFinalCertificateRegisterItem)
def reopen_quarta_taglio_certificate_pdf_route(
    certificate_id: int,
    payload: QuartaTaglioPdfReopenRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioFinalCertificateRegisterItem:
    return reopen_quarta_taglio_certificate_pdf(db, certificate_id=certificate_id, reason=payload.reason, actor=current_user)


@router.get("/certificates/{certificate_id}/pdf-file")
def get_quarta_taglio_certificate_pdf_file_route(
    certificate_id: int,
    db: DbSession,
    download_token: str | None = Query(default=None),
) -> FileResponse:
    path, file_name = get_quarta_taglio_certificate_pdf_file(db, certificate_id=certificate_id, download_token=download_token)
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=file_name,
    )


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
    candidate_cod_f3: str | None = Query(default=None),
) -> QuartaTaglioDetailResponse:
    return get_quarta_taglio_detail(db, cod_odp=cod_odp, certificate_id=certificate_id, candidate_cod_f3=candidate_cod_f3)


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


@router.post("/{cod_odp}/incoming-row-override", response_model=QuartaTaglioDetailResponse)
def set_quarta_taglio_incoming_row_override_route(
    cod_odp: str,
    payload: QuartaTaglioIncomingRowOverrideRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> QuartaTaglioDetailResponse:
    return set_quarta_taglio_incoming_row_override(db, cod_odp=cod_odp, payload=payload, actor_id=current_user.id)


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
        candidate_cod_f3=payload.candidate_cod_f3,
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


@router.post("/{cod_odp}/pdf-attachments", response_model=QuartaTaglioDetailResponse)
def upload_quarta_taglio_pdf_attachment_route(
    cod_odp: str,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
    file: UploadFile = File(...),
) -> QuartaTaglioDetailResponse:
    return upload_quarta_taglio_pdf_attachment(
        db,
        cod_odp=cod_odp,
        uploaded_file=file,
        actor=current_user,
        certificate_id=certificate_id,
    )


@router.delete("/{cod_odp}/pdf-attachments/{attachment_id}", response_model=QuartaTaglioDetailResponse)
def delete_quarta_taglio_pdf_attachment_route(
    cod_odp: str,
    attachment_id: int,
    current_user: CurrentUser,
    db: DbSession,
    certificate_id: int | None = Query(default=None),
) -> QuartaTaglioDetailResponse:
    return delete_quarta_taglio_pdf_attachment(
        db,
        cod_odp=cod_odp,
        attachment_id=attachment_id,
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
