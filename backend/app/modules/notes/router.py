from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.users.models import User
from app.modules.notes.schemas import (
    NoteTemplateCreateRequest,
    NoteTemplateListResponse,
    NoteTemplateResponse,
    NoteTemplateUpdateRequest,
)
from app.modules.notes.service import (
    create_note_template,
    get_note_template,
    list_note_templates,
    update_note_template,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_roles("admin"))]


@router.get("", response_model=NoteTemplateListResponse)
def list_note_templates_route(_: CurrentUser, db: DbSession) -> NoteTemplateListResponse:
    return list_note_templates(db)


@router.post("", response_model=NoteTemplateResponse)
def create_note_template_route(
    payload: NoteTemplateCreateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> NoteTemplateResponse:
    return create_note_template(db=db, payload=payload, actor_email=current_user.email)


@router.patch("/{note_id}", response_model=NoteTemplateResponse)
def update_note_template_route(
    note_id: int,
    payload: NoteTemplateUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> NoteTemplateResponse:
    note = get_note_template(db, note_id)
    return update_note_template(db=db, note=note, payload=payload, actor_email=current_user.email)
