from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.modules.standards.schemas import (
    StandardCreateRequest,
    StandardListResponse,
    StandardResponse,
    StandardUpdateRequest,
)
from app.modules.standards.service import (
    create_standard,
    get_standard,
    list_standards,
    serialize_standard,
    update_standard,
)

router = APIRouter()


@router.get("", response_model=StandardListResponse)
def list_standards_route(
    _: CurrentUser,
    db: DbSession,
    lega: str | None = Query(default=None),
    stato: str | None = Query(default=None),
) -> StandardListResponse:
    return list_standards(db, lega=lega, stato=stato)


@router.get("/{standard_id}", response_model=StandardResponse)
def get_standard_route(_: CurrentUser, standard_id: int, db: DbSession) -> StandardResponse:
    return serialize_standard(get_standard(db, standard_id))


@router.post("", response_model=StandardResponse)
def create_standard_route(
    payload: StandardCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> StandardResponse:
    return create_standard(db=db, payload=payload, actor_email=current_user.email)


@router.put("/{standard_id}", response_model=StandardResponse)
def update_standard_route(
    standard_id: int,
    payload: StandardUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> StandardResponse:
    standard = get_standard(db, standard_id)
    return update_standard(db=db, standard=standard, payload=payload, actor_email=current_user.email)
