from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.startup import bootstrap as _model_registry  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition.models import AcquisitionRow

TEST_MARKER = "KPI_TEST_RIC_LEGA_2026"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup only KPI test rows inserted from Ric_Lega 2026.")
    parser.add_argument("--apply", action="store_true", help="Actually delete rows. Without this flag it only reports.")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = select(AcquisitionRow.id).where(
            AcquisitionRow.note_documento.is_not(None),
            AcquisitionRow.note_documento.like(f"{TEST_MARKER}%"),
        )
        ids = list(db.scalars(query))
        print(f"matching_rows={len(ids)}")
        print(f"marker={TEST_MARKER}")
        if not args.apply:
            print("dry_run=true")
            return

        result = db.execute(
            delete(AcquisitionRow)
            .where(
                AcquisitionRow.note_documento.is_not(None),
                AcquisitionRow.note_documento.like(f"{TEST_MARKER}%"),
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        print(f"deleted={int(result.rowcount or 0)}")


if __name__ == "__main__":
    main()
