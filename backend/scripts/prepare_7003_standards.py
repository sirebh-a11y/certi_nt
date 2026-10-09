"""Preview by default. Add two standards only after environment-specific review."""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.startup import bootstrap as _registry  # register models, never run bootstrap
from app.modules.standards.elongation import ensure_schema
from app.modules.standards.prepare_7003 import prepare_7003
from scripts.recover_ddt_alpha import check_backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-standard-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--maintenance-confirmed", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.apply:
        if not args.maintenance_confirmed or not args.backup:
            raise ValueError("apply richiede backup e conferma manutenzione")
        check_backup(args.backup)
        if settings.ddt_word_reuse_enabled or settings.ddt_snapshot_enabled:
            raise ValueError("disable_workers_in_one_off_container")
    engine = create_engine(settings.database_url)
    try:
        with engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                if not args.apply:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                else:
                    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                    connection.execute(text("LOCK TABLE normative_standards IN SHARE ROW EXCLUSIVE MODE NOWAIT"))
            if args.apply:
                ensure_schema(connection)
            # Preview requires the additive column already prepared, with no writes.
            with Session(bind=connection) as db:
                report = prepare_7003(db, source_standard_id=args.source_standard_id,
                                      activate=args.activate, apply=args.apply)
                db.flush()
        print(json.dumps(dict(mode="applied" if args.apply else "preview", standards=report), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
