from datetime import date
from io import BytesIO

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession
from app.modules.supplier_kpi.schemas import SupplierKpiSummaryResponse
from app.modules.supplier_kpi.service import build_supplier_kpi_summary, build_supplier_kpi_xlsx

router = APIRouter()


@router.get("/summary", response_model=SupplierKpiSummaryResponse)
def supplier_kpi_summary_route(
    _: CurrentUser,
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    quarter: int | None = Query(default=None, ge=1, le=4),
    supplier_id: int | None = Query(default=None),
) -> SupplierKpiSummaryResponse:
    return build_supplier_kpi_summary(
        db=db,
        year=year or date.today().year,
        month=month,
        quarter=quarter,
        supplier_id=supplier_id,
    )


@router.get("/export")
def supplier_kpi_export_route(
    _: CurrentUser,
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    quarter: int | None = Query(default=None, ge=1, le=4),
    supplier_id: int | None = Query(default=None),
) -> StreamingResponse:
    selected_year = year or date.today().year
    content = build_supplier_kpi_xlsx(
        db=db,
        year=selected_year,
        month=month,
        quarter=quarter,
        supplier_id=supplier_id,
    )
    period = f"q{quarter}" if quarter else f"m{month}" if month else "anno"
    filename = f"kpi_fornitori_{selected_year}_{period}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
