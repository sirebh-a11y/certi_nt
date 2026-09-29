"""One-time local DDT recovery. Run the read-only audit first.

Requires --local-compose --apply. This command never targets Alpha and does
not enable the periodic DDT snapshot scheduler.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base
from app.modules.quarta_taglio.ddt_legacy_import import import_legacy_cache
from app.modules.quarta_taglio.ddt_snapshot import (
    SnapshotError, _fetch_complete_snapshot, _LOCK_ID, _LOCK_NAMESPACE,
)
from app.modules.quarta_taglio.models import QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem
from app.startup import bootstrap as _model_registry  # noqa: F401 - register models only


def main():
    parser = argparse.ArgumentParser(description="Importa in locale lo storico DDT non ambiguo")
    parser.add_argument("--local-compose", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.local_compose or not args.apply:
        parser.error("servono --local-compose e --apply; eseguire prima audit_ddt_legacy_cache.py")

    url = make_url(settings.database_url)
    if url.host != "postgres" or url.database != "certi_nt":
        parser.error("configurazione diversa dal Compose locale certi_nt: importazione rifiutata")
    engine = create_engine(url.set(host="127.0.0.1"))
    report = None
    try:
        with Session(engine) as db, db.begin():
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            locked = db.scalar(text("SELECT pg_try_advisory_xact_lock(:namespace, :key)"),
                               {"namespace": _LOCK_NAMESPACE, "key": _LOCK_ID})
            if not locked:
                raise SnapshotError("snapshot_busy")
            current_rows = _fetch_complete_snapshot(db)
            # Create only the two new queue tables; PostgreSQL rolls back their
            # creation as well if source validation or import fails.
            Base.metadata.create_all(
                bind=db.connection(),
                tables=[QuartaTaglioDdtWorkItem.__table__, QuartaTaglioDdtSyncRun.__table__],
                checkfirst=True,
            )
            report = import_legacy_cache(db, current_rows=current_rows, now=datetime.now(timezone.utc))
    except SnapshotError as exc:
        report = {"status": "not_applied", "error_code": str(exc)}
    except Exception:
        # Never print connection strings, SQL errors, or encrypted credentials.
        report = {"status": "not_applied", "error_code": "local_import_failed"}
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") == "not_applied":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
