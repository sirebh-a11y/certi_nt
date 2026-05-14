from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.modules.supplier_kpi.schemas import SupplierKpiSummaryResponse
from app.modules.supplier_kpi.service import build_supplier_kpi_summary

router = APIRouter()


@router.get("/summary", response_model=SupplierKpiSummaryResponse)
def supplier_kpi_summary_route(
    _: CurrentUser,
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    supplier_id: int | None = Query(default=None),
) -> SupplierKpiSummaryResponse:
    return build_supplier_kpi_summary(db=db, year=year or date.today().year, month=month, supplier_id=supplier_id)
