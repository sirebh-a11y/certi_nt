from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.ai.schemas import (
    AIConfigResponse,
    AIModelCreateRequest,
    AIModelResponse,
    AIModelUpdateRequest,
    AIProviderCreateRequest,
    AIProviderResponse,
    AIProviderUpdateRequest,
)
from app.core.ai.service import (
    create_ai_model,
    create_ai_provider,
    get_ai_configuration,
    get_ai_model,
    get_ai_provider,
    update_ai_model,
    update_ai_provider,
)
from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.roles.constants import ROLE_ADMIN

router = APIRouter()

AdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN))]


@router.get("", response_model=AIConfigResponse)
def get_ai_configuration_route(_: AdminUser, db: DbSession) -> AIConfigResponse:
    return get_ai_configuration(db)


@router.post("/providers", response_model=AIProviderResponse)
def create_provider_route(payload: AIProviderCreateRequest, current_user: AdminUser, db: DbSession) -> AIProviderResponse:
    return create_ai_provider(db=db, payload=payload, actor_email=current_user.email)


@router.patch("/providers/{provider_id}", response_model=AIProviderResponse)
def update_provider_route(
    provider_id: int,
    payload: AIProviderUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> AIProviderResponse:
    provider = get_ai_provider(db, provider_id)
    return update_ai_provider(db=db, provider=provider, payload=payload, actor_email=current_user.email)


@router.post("/models", response_model=AIModelResponse)
def create_model_route(payload: AIModelCreateRequest, current_user: AdminUser, db: DbSession) -> AIModelResponse:
    return create_ai_model(db=db, payload=payload, actor_email=current_user.email)


@router.patch("/models/{model_id}", response_model=AIModelResponse)
def update_model_route(
    model_id: int,
    payload: AIModelUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> AIModelResponse:
    model = get_ai_model(db, model_id)
    return update_ai_model(db=db, model=model, payload=payload, actor_email=current_user.email)
