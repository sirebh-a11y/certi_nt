from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security.crypto import decrypt_secret
from app.modules.acquisition.schemas import (
    AutonomousRunResponse,
    AutonomousRunStartRequest,
    AcquisitionRowCreateRequest,
    AcquisitionRowDetailResponse,
    AcquisitionRowListResponse,
    AcquisitionRowUpdateRequest,
    ChemistryCaptureRequest,
    ChemistryCaptureResponse,
    DocumentBatchUploadResponse,
    CurrentUploadBatchResponse,
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentEvidenceCreateRequest,
    DocumentEvidenceResponse,
    DocumentListResponse,
    DocumentPageCreateRequest,
    DocumentPageResponse,
    DocumentResponse,
    DocumentSplitRowsCreateResponse,
    MatchResponse,
    MatchUpsertRequest,
    ReadValueResponse,
    ReadValueUpsertRequest,
)
from app.modules.acquisition.service import (
    get_active_autonomous_run,
    get_autonomous_run,
    create_acquisition_row,
    create_document,
    create_document_page,
    create_rows_from_document_split_plan,
    capture_chemistry_value_from_page,
    create_evidence,
    discard_current_upload_batch,
    detect_chemistry,
    detect_properties,
    detect_standard_notes,
    extract_ddt_fields_with_vision,
    extract_core_fields,
    get_acquisition_row,
    get_document,
    get_document_file_path,
    get_document_page,
    get_document_page_image_path,
    index_document,
    get_current_upload_batch,
    list_acquisition_rows,
    list_documents,
    process_row_minimal,
    prepare_document_for_reader,
    run_ai_intervention,
    run_autonomous_processing,
    serialize_acquisition_row_detail,
    serialize_document_detail,
    serialize_autonomous_run,
    start_autonomous_run,
    upload_document,
    upload_documents_batch,
    upsert_match,
    upsert_read_value,
    update_acquisition_row,
    validate_final_row,
)
from app.modules.document_reader.schemas import DocumentRowSplitPlanResponse, ReaderPlanResponse
from app.modules.document_reader.service import build_document_row_split_plan, build_reader_plan

router = APIRouter()


def _resolve_openai_api_key(current_user: CurrentUser) -> str | None:
    if current_user.openai_api_key_encrypted:
        return decrypt_secret(current_user.openai_api_key_encrypted)
    return settings.openai_api_key


@router.post("/automation/runs", response_model=AutonomousRunResponse)
def start_automation_run_route(
    payload: AutonomousRunStartRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
) -> AutonomousRunResponse:
    run = start_autonomous_run(db=db, payload=payload, actor_id=current_user.id)
    openai_api_key = _resolve_openai_api_key(current_user)
    if payload.usa_intervento_ai and not openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key is not configured")
    background_tasks.add_task(
        run_autonomous_processing,
        run_id=run.id,
        ddt_document_ids=payload.ddt_document_ids,
        certificate_document_ids=payload.certificate_document_ids,
        actor_id=current_user.id,
        actor_email=current_user.email,
        openai_api_key=openai_api_key,
        use_ddt_vision=payload.usa_ddt_vision,
        use_ai_intervention=payload.usa_intervento_ai,
    )
    return run


@router.get("/automation/runs/active", response_model=AutonomousRunResponse | None)
def get_active_automation_run_route(current_user: CurrentUser, db: DbSession) -> AutonomousRunResponse | None:
    run = get_active_autonomous_run(db, actor_id=current_user.id)
    return serialize_autonomous_run(run) if run is not None else None


@router.get("/automation/runs/{run_id}", response_model=AutonomousRunResponse)
def get_automation_run_route(run_id: int, _: CurrentUser, db: DbSession) -> AutonomousRunResponse:
    return serialize_autonomous_run(get_autonomous_run(db, run_id))


@router.get("/documents", response_model=DocumentListResponse)
def list_documents_route(
    current_user: CurrentUser,
    db: DbSession,
    tipo_documento: str | None = Query(default=None),
    fornitore_id: int | None = Query(default=None),
    upload_batch_id: str | None = Query(default=None),
) -> DocumentListResponse:
    return DocumentListResponse(
        items=list_documents(
            db,
            tipo_documento=tipo_documento,
            fornitore_id=fornitore_id,
            upload_batch_id=upload_batch_id,
            actor_id=current_user.id,
        )
    )


@router.get("/documents/current-batch", response_model=CurrentUploadBatchResponse)
def get_current_upload_batch_route(current_user: CurrentUser, db: DbSession) -> CurrentUploadBatchResponse:
    return get_current_upload_batch(db, actor_id=current_user.id)


@router.delete("/documents/current-batch", response_model=CurrentUploadBatchResponse)
def discard_current_upload_batch_route(current_user: CurrentUser, db: DbSession) -> CurrentUploadBatchResponse:
    return discard_current_upload_batch(db, actor_id=current_user.id)


@router.post("/documents", response_model=DocumentResponse)
def create_document_route(payload: DocumentCreateRequest, current_user: CurrentUser, db: DbSession) -> DocumentResponse:
    return create_document(db=db, payload=payload, actor_id=current_user.id, actor_email=current_user.email)


@router.post("/documents/upload", response_model=DocumentResponse)
def upload_document_route(
    current_user: CurrentUser,
    db: DbSession,
    tipo_documento: str = Form(...),
    file: UploadFile = File(...),
    fornitore_id: int | None = Form(default=None),
    documento_padre_id: int | None = Form(default=None),
    origine_upload: str = Form(default="utente"),
    upload_batch_id: str | None = Form(default=None),
) -> DocumentResponse:
    return upload_document(
        db=db,
        tipo_documento=tipo_documento,
        uploaded_file=file,
        actor_id=current_user.id,
        actor_email=current_user.email,
        fornitore_id=fornitore_id,
        documento_padre_id=documento_padre_id,
        origine_upload=origine_upload,
        upload_batch_id=upload_batch_id,
    )


@router.post("/documents/upload-batch", response_model=DocumentBatchUploadResponse)
def upload_documents_batch_route(
    current_user: CurrentUser,
    db: DbSession,
    tipo_documento: str = Form(...),
    files: list[UploadFile] = File(...),
    fornitore_id: int | None = Form(default=None),
    documento_padre_id: int | None = Form(default=None),
    origine_upload: str = Form(default="utente"),
    upload_batch_id: str | None = Form(default=None),
) -> DocumentBatchUploadResponse:
    return upload_documents_batch(
        db=db,
        tipo_documento=tipo_documento,
        uploaded_files=files,
        actor_id=current_user.id,
        actor_email=current_user.email,
        fornitore_id=fornitore_id,
        documento_padre_id=documento_padre_id,
        origine_upload=origine_upload,
        upload_batch_id=upload_batch_id,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document_route(document_id: int, _: CurrentUser, db: DbSession) -> DocumentDetailResponse:
    return serialize_document_detail(get_document(db, document_id))


@router.get("/documents/{document_id}/row-split-plan", response_model=DocumentRowSplitPlanResponse)
def get_document_row_split_plan_route(
    document_id: int,
    _: CurrentUser,
    db: DbSession,
) -> DocumentRowSplitPlanResponse:
    document = get_document(db, document_id)
    document = prepare_document_for_reader(db, document)
    return build_document_row_split_plan(document)


@router.post("/documents/{document_id}/split-rows", response_model=DocumentSplitRowsCreateResponse)
def create_document_split_rows_route(
    document_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> DocumentSplitRowsCreateResponse:
    document = get_document(db, document_id)
    return create_rows_from_document_split_plan(
        db=db,
        document=document,
        actor_id=current_user.id,
        actor_email=current_user.email,
    )


@router.get("/documents/{document_id}/file")
def get_document_file_route(document_id: int, _: CurrentUser, db: DbSession) -> FileResponse:
    document = get_document(db, document_id)
    file_path = get_document_file_path(document)
    media_type = document.mime_type or "application/octet-stream"
    return FileResponse(path=file_path, media_type=media_type, filename=document.nome_file_originale)


@router.post("/documents/{document_id}/index", response_model=DocumentDetailResponse)
def index_document_route(document_id: int, current_user: CurrentUser, db: DbSession) -> DocumentDetailResponse:
    document = get_document(db, document_id)
    return index_document(db=db, document=document, actor_email=current_user.email)


@router.post("/documents/{document_id}/pages", response_model=DocumentPageResponse)
def create_document_page_route(
    document_id: int,
    payload: DocumentPageCreateRequest,
    _: CurrentUser,
    db: DbSession,
) -> DocumentPageResponse:
    document = get_document(db, document_id)
    return create_document_page(db=db, document=document, payload=payload)


@router.get("/document-pages/{page_id}/image")
def get_document_page_image_route(page_id: int, _: CurrentUser, db: DbSession) -> FileResponse:
    page = get_document_page(db, page_id)
    image_path = get_document_page_image_path(page)
    filename = image_path.name
    return FileResponse(path=image_path, media_type="image/png", filename=filename)


@router.post("/document-pages/{page_id}/chemistry-capture", response_model=ChemistryCaptureResponse)
def capture_chemistry_value_route(
    page_id: int,
    payload: ChemistryCaptureRequest,
    _: CurrentUser,
    db: DbSession,
) -> ChemistryCaptureResponse:
    page = get_document_page(db, page_id)
    return capture_chemistry_value_from_page(page=page, payload=payload)


@router.get("/rows", response_model=AcquisitionRowListResponse)
def list_acquisition_rows_route(
    _: CurrentUser,
    db: DbSession,
    stato_tecnico: str | None = Query(default=None),
    stato_workflow: str | None = Query(default=None),
    priorita_operativa: str | None = Query(default=None),
    fornitore_id: int | None = Query(default=None),
    has_certificate: bool | None = Query(default=None),
) -> AcquisitionRowListResponse:
    return AcquisitionRowListResponse(
        items=list_acquisition_rows(
            db,
            stato_tecnico=stato_tecnico,
            stato_workflow=stato_workflow,
            priorita_operativa=priorita_operativa,
            fornitore_id=fornitore_id,
            has_certificate=has_certificate,
        )
    )


@router.post("/rows", response_model=AcquisitionRowDetailResponse)
def create_acquisition_row_route(
    payload: AcquisitionRowCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    return create_acquisition_row(db=db, payload=payload, actor_id=current_user.id, actor_email=current_user.email)


@router.get("/rows/{row_id}", response_model=AcquisitionRowDetailResponse)
def get_acquisition_row_route(row_id: int, _: CurrentUser, db: DbSession) -> AcquisitionRowDetailResponse:
    return serialize_acquisition_row_detail(get_acquisition_row(db, row_id))


@router.get("/rows/{row_id}/reader-plan", response_model=ReaderPlanResponse)
def get_reader_plan_route(row_id: int, _: CurrentUser, db: DbSession) -> ReaderPlanResponse:
    row = get_acquisition_row(db, row_id)
    if row.ddt_document is not None:
        row.ddt_document = prepare_document_for_reader(db, row.ddt_document)
    if row.certificate_document is not None:
        row.certificate_document = prepare_document_for_reader(db, row.certificate_document)
    return build_reader_plan(row)


@router.patch("/rows/{row_id}", response_model=AcquisitionRowDetailResponse)
def update_acquisition_row_route(
    row_id: int,
    payload: AcquisitionRowUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return update_acquisition_row(db=db, row=row, payload=payload, actor_id=current_user.id, actor_email=current_user.email)


@router.post("/rows/{row_id}/evidences", response_model=DocumentEvidenceResponse)
def create_evidence_route(
    row_id: int,
    payload: DocumentEvidenceCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> DocumentEvidenceResponse:
    row = get_acquisition_row(db, row_id)
    return create_evidence(db=db, row=row, payload=payload, actor_id=current_user.id)


@router.put("/rows/{row_id}/values", response_model=ReadValueResponse)
def upsert_read_value_route(
    row_id: int,
    payload: ReadValueUpsertRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ReadValueResponse:
    row = get_acquisition_row(db, row_id)
    return upsert_read_value(db=db, row=row, payload=payload, actor_id=current_user.id)


@router.put("/rows/{row_id}/match", response_model=MatchResponse)
def upsert_match_route(
    row_id: int,
    payload: MatchUpsertRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> MatchResponse:
    row = get_acquisition_row(db, row_id)
    return upsert_match(db=db, row=row, payload=payload, actor_id=current_user.id)


@router.post("/rows/{row_id}/detect-notes", response_model=AcquisitionRowDetailResponse)
def detect_standard_notes_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return detect_standard_notes(db=db, row=row, actor_id=current_user.id)


@router.post("/rows/{row_id}/detect-chemistry", response_model=AcquisitionRowDetailResponse)
def detect_chemistry_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return detect_chemistry(db=db, row=row, actor_id=current_user.id, openai_api_key=_resolve_openai_api_key(current_user))


@router.post("/rows/{row_id}/detect-properties", response_model=AcquisitionRowDetailResponse)
def detect_properties_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return detect_properties(db=db, row=row, actor_id=current_user.id, openai_api_key=_resolve_openai_api_key(current_user))


@router.post("/rows/{row_id}/extract-core-fields", response_model=AcquisitionRowDetailResponse)
def extract_core_fields_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return extract_core_fields(db=db, row=row, actor_id=current_user.id)


@router.post("/rows/{row_id}/extract-ddt-vision", response_model=AcquisitionRowDetailResponse)
def extract_ddt_vision_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    openai_api_key = _resolve_openai_api_key(current_user)
    if not openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key is not configured")
    row = get_acquisition_row(db, row_id)
    return extract_ddt_fields_with_vision(db=db, row=row, actor_id=current_user.id, openai_api_key=openai_api_key)


@router.post("/rows/{row_id}/process-minimal", response_model=AcquisitionRowDetailResponse)
def process_row_minimal_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return process_row_minimal(db=db, row=row, actor_id=current_user.id)


@router.post("/rows/{row_id}/intervento-ai", response_model=AcquisitionRowDetailResponse)
def run_ai_intervention_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    openai_api_key = _resolve_openai_api_key(current_user)
    if not openai_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key is not configured")
    row = get_acquisition_row(db, row_id)
    return run_ai_intervention(db=db, row=row, actor_id=current_user.id, openai_api_key=openai_api_key)


@router.post("/rows/{row_id}/validate-final", response_model=AcquisitionRowDetailResponse)
def validate_final_row_route(
    row_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> AcquisitionRowDetailResponse:
    row = get_acquisition_row(db, row_id)
    return validate_final_row(db=db, row=row, actor_id=current_user.id)
