from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import CurrentUser, DbSession, require_quality_area_admin
from app.modules.customer_requirements.schemas import (
    CustomerRequirementCreateRequest,
    CustomerRequirementListResponse,
    CustomerRequirementResponse,
    CustomerRequirementUpdateRequest,
)
from app.modules.customer_requirements.service import (
    create_customer_requirement,
    delete_customer_requirement,
    get_customer_requirement,
    list_customer_requirements,
    update_customer_requirement,
)

router = APIRouter()
QualityAdminUser = Annotated[CurrentUser, Depends(require_quality_area_admin)]


@router.get("", response_model=CustomerRequirementListResponse)
def list_customer_requirements_route(_: CurrentUser, db: DbSession) -> CustomerRequirementListResponse:
    return list_customer_requirements(db)


@router.post("", response_model=CustomerRequirementResponse)
def create_customer_requirement_route(
    payload: CustomerRequirementCreateRequest,
    current_user: QualityAdminUser,
    db: DbSession,
) -> CustomerRequirementResponse:
    return create_customer_requirement(db=db, payload=payload, actor_email=current_user.email)


@router.put("/{requirement_id}", response_model=CustomerRequirementResponse)
def update_customer_requirement_route(
    requirement_id: int,
    payload: CustomerRequirementUpdateRequest,
    current_user: QualityAdminUser,
    db: DbSession,
) -> CustomerRequirementResponse:
    requirement = get_customer_requirement(db, requirement_id)
    return update_customer_requirement(db=db, requirement=requirement, payload=payload, actor_email=current_user.email)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer_requirement_route(
    requirement_id: int,
    current_user: QualityAdminUser,
    db: DbSession,
) -> Response:
    requirement = get_customer_requirement(db, requirement_id)
    delete_customer_requirement(db=db, requirement=requirement, actor_email=current_user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
