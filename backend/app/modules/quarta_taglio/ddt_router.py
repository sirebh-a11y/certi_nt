"""Local read-only endpoints, with the same department access as Certification UI."""
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import CurrentUser, DbSession, user_is_in_department
from app.modules.quarta_taglio.ddt_queue import read_ddt_queue, read_ddt_sync
from app.modules.quarta_taglio.ddt_schemas import DdtQueueCountersResponse, DdtQueueResponse, DdtQueueSyncResponse, DdtScope, DdtState


def require_certification_reader(current_user: CurrentUser):
    if not user_is_in_department(current_user, "it", "qualita", "laboratorio"):
        raise HTTPException(status_code=403, detail="Accesso Certificazione non autorizzato")
    return current_user


router = APIRouter(prefix="/ddt-work-items", dependencies=[Depends(require_certification_reader)])


def source_filters(
    query: str | None = Query(None, max_length=200),
    ddt: str | None = Query(None, max_length=200),
    cod_odp: str | None = Query(None, max_length=200),
    cod_f3: str | None = Query(None, max_length=200),
    cliente: str | None = Query(None, max_length=200),
    date_from: date | None = None,
    date_to: date | None = None,
    source_present: bool | None = None,
):
    return dict(query=query, ddt=ddt, cod_odp=cod_odp, cod_f3=cod_f3, cliente=cliente,
                date_from=date_from, date_to=date_to, source_present=source_present)


@router.get("", response_model=DdtQueueResponse)
def list_ddt_work_items(
    db: DbSession,
    filters: Annotated[dict, Depends(source_filters)],
    scope: DdtScope = "active",
    state: DdtState | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_field: Literal["ddt_date", "ddt_raw", "cod_odp", "cod_f3", "cliente", "quantita",
                        "ordine_cliente", "conferma_ordine", "incoming", "certificazione",
                        "state", "last_seen_at"] = "ddt_date",
    sort_direction: Literal["asc", "desc"] = "desc",
):
    return read_ddt_queue(db, **filters, scope=scope, state=state, limit=limit,
                          offset=offset, sort_field=sort_field, sort_direction=sort_direction)


@router.get("/sync", response_model=DdtQueueSyncResponse)
def ddt_sync_status(db: DbSession):
    return read_ddt_sync(db)


@router.get("/counters", response_model=DdtQueueCountersResponse)
def ddt_work_item_counters(db: DbSession, filters: Annotated[dict, Depends(source_filters)]):
    return read_ddt_queue(db, **filters, counters_only=True)
