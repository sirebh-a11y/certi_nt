from fastapi import APIRouter

from app.core.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    SetPasswordRequest,
)
from app.core.auth.service import build_auth_user, change_password, login, set_password
from app.core.deps import CurrentUser, DbSession
from app.core.logs.service import log_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login_route(payload: LoginRequest, db: DbSession) -> LoginResponse:
    return login(db=db, email=payload.email, password=payload.password)


@router.post("/set-password", response_model=LoginResponse)
def set_password_route(payload: SetPasswordRequest, db: DbSession) -> LoginResponse:
    return set_password(db=db, setup_token=payload.setup_token, new_password=payload.new_password)


@router.post("/change-password", response_model=MessageResponse)
def change_password_route(payload: ChangePasswordRequest, db: DbSession, current_user: CurrentUser) -> MessageResponse:
    change_password(db=db, user=current_user, current_password=payload.current_password, new_password=payload.new_password)
    return MessageResponse(message="Password updated")


@router.post("/logout", response_model=MessageResponse)
def logout_route(current_user: CurrentUser) -> MessageResponse:
    log_service.record("authentication", "Logout", current_user.email)
    return MessageResponse(message="Logout handled client-side")


@router.get("/me", response_model=LoginResponse)
def me_route(current_user: CurrentUser) -> LoginResponse:
    return LoginResponse(user=build_auth_user(current_user))
