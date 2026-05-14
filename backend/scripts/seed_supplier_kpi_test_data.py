from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import delete

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.startup import bootstrap as _model_registry  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition.models import AcquisitionRow
from app.modules.suppliers.models import Supplier

TEST_MARKER = "KPI_TEST_RIC_LEGA_2026"
FIXTURE_PATH = BACKEND_ROOT / "app" / "modules" / "supplier_kpi" / "data" / "ric_lega_2026_test_rows.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed reversible supplier KPI test rows from Ric_Lega 2026.")
    parser.add_argument("--keep-existing", action="store_true", help="Do not delete existing KPI test rows before insert.")
    args = parser.parse_args()

    rows = json.loads(FIXTURE_PATH.read_text(encoding="utf-8-sig"))
    with SessionLocal() as db:
        if not args.keep_existing:
            deleted = _delete_test_rows(db)
            print(f"deleted_existing={deleted}")

        suppliers = {
            supplier.ragione_sociale.strip().lower(): supplier
            for supplier in db.query(Supplier).all()
            if supplier.ragione_sociale
        }
        inserted = 0
        for item in rows:
            supplier_name = _clean(item.get("fornitore"))
            supplier = suppliers.get(supplier_name.lower()) if supplier_name else None
            row = AcquisitionRow(
                fornitore_id=supplier.id if supplier else None,
                fornitore_raw=supplier_name,
                lega_base=_clean(item.get("lega")),
                diametro=_clean(item.get("diametro")),
                cdq=_clean(item.get("cdq")),
                colata=_clean(item.get("colata")),
                ddt=_clean(item.get("ddt")),
                peso=_clean(item.get("peso")),
                ordine=_clean(item.get("ordine")),
                note_documento=f"{TEST_MARKER}:{item.get('source_sheet')}:{item.get('source_row')}",
                qualita_data_ricezione=_parse_excel_date(item.get("data_ricezione")),
                qualita_data_accettazione=_parse_excel_date(item.get("data_accettazione")),
                qualita_data_richiesta=_parse_excel_date(item.get("data_richiesta")),
                qualita_numero_analisi=_clean(item.get("numero_analisi")),
                qualita_valutazione=item.get("valutazione") or None,
                qualita_note=_clean(item.get("note")),
                stato_tecnico="verde",
                stato_workflow="validata_quality",
                priorita_operativa="bassa",
                validata_finale=True,
            )
            db.add(row)
            inserted += 1

        db.commit()
        print(f"inserted={inserted}")
        print(f"marker={TEST_MARKER}")


def _delete_test_rows(db) -> int:
    result = db.execute(
        delete(AcquisitionRow)
        .where(
            AcquisitionRow.note_documento.is_not(None),
            AcquisitionRow.note_documento.like(f"{TEST_MARKER}%"),
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return int(result.rowcount or 0)


def _parse_excel_date(value: str | None) -> date | None:
    value = _clean(value)
    if not value:
        return None
    day, month, year = value.split("/")
    parsed_year = int(year)
    if parsed_year < 100:
        parsed_year += 2000
    return date(parsed_year, int(month), int(day))


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    main()
