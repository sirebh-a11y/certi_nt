"""Read-only local report of DDT units cached before the persistent queue.

Run with PYTHONPATH=backend. --with-esolver reads the complete eSolver view but
still does not write to either database. Without it, a successful local DDT
snapshot is needed to distinguish historical rows from current rows.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.quarta_taglio.ddt_legacy_audit import analyze_legacy_cache
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _fetch_complete_snapshot
from app.startup import bootstrap as _model_registry  # noqa: F401 - imports models; never calls bootstrap


def main():
    parser = argparse.ArgumentParser(description="Analizza la cache DDT senza importare o modificare righe")
    parser.add_argument("--with-esolver", action="store_true", help="legge la vista eSolver completa in sola lettura")
    parser.add_argument("--local-compose", action="store_true", help="usa localhost per il PostgreSQL del Compose locale")
    args = parser.parse_args()
    url = make_url(settings.database_url)
    if args.local_compose:
        if url.host != "postgres" or url.database != "certi_nt":
            parser.error("--local-compose richiede la configurazione del Compose locale certi_nt")
        url = url.set(host="127.0.0.1")
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SET TRANSACTION READ ONLY"))
            elif db.get_bind().dialect.name == "sqlite":
                db.execute(text("PRAGMA query_only = ON"))
            else:
                parser.error("database non supportato per il dry-run")
            try:
                current_rows = _fetch_complete_snapshot(db) if args.with_esolver else None
                report = analyze_legacy_cache(db, current_rows=current_rows)
            except SnapshotError as exc:
                report = {"status": "source_read_failed", "error_code": str(exc)}
            finally:
                db.rollback()
    except SQLAlchemyError as exc:
        report = {"status": "local_database_unavailable", "sqlstate": getattr(getattr(exc, "orig", None), "sqlstate", None)}
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
