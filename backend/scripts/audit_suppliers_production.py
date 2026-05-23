from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.startup.bootstrap  # noqa: F401
from app.core.database import SessionLocal
from app.modules.acquisition.models import AcquisitionRow, Document
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.service import CORE_SUPPLIER_SEED


def main() -> None:
    core_names = {str(seed["ragione_sociale"]).casefold() for seed in CORE_SUPPLIER_SEED}
    core_keys = {str(seed["reader_template_key"]) for seed in CORE_SUPPLIER_SEED}

    db = SessionLocal()
    try:
        suppliers = db.query(Supplier).order_by(Supplier.ragione_sociale).all()
        rows = []
        for supplier in suppliers:
            document_count = db.query(Document).filter(Document.fornitore_id == supplier.id).count()
            row_count = db.query(AcquisitionRow).filter(AcquisitionRow.fornitore_id == supplier.id).count()
            is_core = (
                supplier.ragione_sociale.casefold() in core_names
                or (supplier.reader_template_key is not None and supplier.reader_template_key in core_keys)
            )
            rows.append(
                {
                    "id": supplier.id,
                    "ragione_sociale": supplier.ragione_sociale,
                    "reader_template_key": supplier.reader_template_key,
                    "core": is_core,
                    "documenti": document_count,
                    "righe_incoming": row_count,
                    "azione_proposta": "mantieni" if is_core else ("valuta_manualmente" if document_count or row_count else "rimovibile"),
                }
            )

        print(json.dumps({"fornitori": rows}, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
