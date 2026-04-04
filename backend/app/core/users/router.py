from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.departments.service import get_department_by_name
from app.core.roles.constants import ROLE_ADMIN, ROLE_MANAGER
from app.core.users.schemas import (
    OpenAIKeyStatusResponse,
    OpenAIKeyUpdateRequest,
    UserActionResponse,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
)
from app.core.users.service import (
    create_user,
    disable_user,
    get_user,
    list_users,
    reset_user_password,
    serialize_user,
    update_openai_key,
)

router = APIRouter()

AdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN))]
AdminOrManagerUser = Annotated[CurrentUser, Depends(require_roles(ROLE_ADMIN, ROLE_MANAGER))]


@router.get("", response_model=UserListResponse)
def list_users_route(_: AdminOrManagerUser, db: DbSession) -> UserListResponse:
    return UserListResponse(items=list_users(db))


@router.post("", response_model=UserResponse)
def create_user_route(payload: UserCreateRequest, current_user: AdminUser, db: DbSession) -> UserResponse:
    department = get_department_by_name(db, payload.department)
    return create_user(db=db, payload=payload, department_id=department.id, actor_email=current_user.email)


@router.get("/me", response_model=UserResponse)
def get_me_route(current_user: CurrentUser) -> UserResponse:
    return serialize_user(current_user)


@router.put("/me/openai-key", response_model=OpenAIKeyStatusResponse)
def update_openai_key_route(payload: OpenAIKeyUpdateRequest, current_user: CurrentUser, db: DbSession) -> OpenAIKeyStatusResponse:
    configured = update_openai_key(db=db, user=current_user, openai_api_key=payload.openai_api_key)
    return OpenAIKeyStatusResponse(configured=configured)


@router.get("/{user_id}", response_model=UserResponse)
def get_user_route(user_id: int, current_user: CurrentUser, db: DbSession) -> UserResponse:
    user = get_user(db, user_id)
    if current_user.role not in {ROLE_ADMIN, ROLE_MANAGER} and current_user.id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return serialize_user(user)


@router.patch("/{user_id}/disable", response_model=UserActionResponse)
def disable_user_route(user_id: int, current_user: AdminUser, db: DbSession) -> UserActionResponse:
    user = get_user(db, user_id)
    disable_user(db=db, user=user, actor_email=current_user.email)
    return UserActionResponse(message="User disabled")


@router.patch("/{user_id}/reset-password", response_model=UserActionResponse)
def reset_password_route(user_id: int, current_user: AdminUser, db: DbSession) -> UserActionResponse:
    user = get_user(db, user_id)
    reset_user_password(db=db, user=user, actor_email=current_user.email)
    return UserActionResponse(message="Password reset")
