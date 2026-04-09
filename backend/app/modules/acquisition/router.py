from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.modules.acquisition.schemas import (
    AcquisitionRowCreateRequest,
    AcquisitionRowDetailResponse,
    AcquisitionRowListResponse,
    AcquisitionRowUpdateRequest,
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentEvidenceCreateRequest,
    DocumentEvidenceResponse,
    DocumentListResponse,
    DocumentPageCreateRequest,
    DocumentPageResponse,
    DocumentResponse,
    MatchResponse,
    MatchUpsertRequest,
    ReadValueResponse,
    ReadValueUpsertRequest,
)
from app.modules.acquisition.service import (
    create_acquisition_row,
    create_document,
    create_document_page,
    create_evidence,
    get_acquisition_row,
    get_document,
    list_acquisition_rows,
    list_documents,
    serialize_acquisition_row_detail,
    serialize_document_detail,
    upsert_match,
    upsert_read_value,
    update_acquisition_row,
)

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents_route(
    _: CurrentUser,
    db: DbSession,
    tipo_documento: str | None = Query(default=None),
    fornitore_id: int | None = Query(default=None),
) -> DocumentListResponse:
    return DocumentListResponse(items=list_documents(db, tipo_documento=tipo_documento, fornitore_id=fornitore_id))


@router.post("/documents", response_model=DocumentResponse)
def create_document_route(payload: DocumentCreateRequest, current_user: CurrentUser, db: DbSession) -> DocumentResponse:
    return create_document(db=db, payload=payload, actor_id=current_user.id, actor_email=current_user.email)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document_route(document_id: int, _: CurrentUser, db: DbSession) -> DocumentDetailResponse:
    return serialize_document_detail(get_document(db, document_id))


@router.post("/documents/{document_id}/pages", response_model=DocumentPageResponse)
def create_document_page_route(
    document_id: int,
    payload: DocumentPageCreateRequest,
    _: CurrentUser,
    db: DbSession,
) -> DocumentPageResponse:
    document = get_document(db, document_id)
    return create_document_page(db=db, document=document, payload=payload)


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
