from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.modules.supplier_calendar.schemas import (
    SupplierCalendarClosureCreate,
    SupplierCalendarClosureResponse,
    SupplierCalendarYearResponse,
)
from app.modules.supplier_calendar.service import (
    create_closure,
    delete_closure,
    get_calendar_year,
)


router = APIRouter()


@router.get("/{year}", response_model=SupplierCalendarYearResponse)
def read_supplier_calendar_year(
    year: int,
    db: DbSession,
    _current_user: CurrentUser,
) -> SupplierCalendarYearResponse:
    if year < 2026 or year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anno supportato da 2026 a 2100",
        )
    return get_calendar_year(db, year)


@router.post("/closures", response_model=SupplierCalendarClosureResponse)
def create_supplier_calendar_closure(
    payload: SupplierCalendarClosureCreate,
    db: DbSession,
    _current_user: CurrentUser,
) -> SupplierCalendarClosureResponse:
    if payload.start_date.year < 2026:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le chiusure sono gestite dal 2026",
        )
    return create_closure(db, payload)


@router.delete("/closures/{closure_id}")
def delete_supplier_calendar_closure(
    closure_id: int,
    db: DbSession,
    _current_user: CurrentUser,
) -> dict[str, bool]:
    if not delete_closure(db, closure_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chiusura non trovata")
    return {"ok": True}
