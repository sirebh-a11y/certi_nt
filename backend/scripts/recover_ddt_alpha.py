"""Alpha-only schema/preview/apply tool. No scheduler or application bootstrap.

Prepare: --prepare-schema --maintenance-confirmed --backup /audit/db.sql
Preview: --preview --report /audit/report.json
Apply: --apply --report /audit/report.json --maintenance-confirmed --backup /audit/db.sql
Use a one-off backend container after stopping application writers as documented.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.quarta_taglio.ddt_recovery import (
    alpha_database_identity, apply_approved_recovery, build_recovery_plan,
    prepare_recovery_schema, require_recovery_schema, validate_alpha_settings,
)
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _fetch_complete_snapshot
from app.startup import bootstrap as _registry  # noqa: F401 - model registration only


def check_backup(path):
    if not path or not path.is_absolute() or not path.is_file() or path.stat().st_size == 0:
        raise SnapshotError("readable_database_backup_required")
    with path.open("rb") as file:
        header = file.read(128)
    if not (header.startswith(b"PGDMP") or b"PostgreSQL database dump" in header):
        raise SnapshotError("postgres_dump_header_required")


def main():
    parser = argparse.ArgumentParser(description="Report e recupero DDT nel database Alpha")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--prepare-schema", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--maintenance-confirmed", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if (args.apply or args.prepare_schema) and (not args.maintenance_confirmed or not args.backup):
        parser.error("scritture consentite solo con --maintenance-confirmed e --backup")
    if not args.prepare_schema and not args.report:
        parser.error("--report obbligatorio per --preview e --apply")
    if args.prepare_schema and args.report:
        parser.error("--prepare-schema non produce un report di recupero")
    engine = None
    try:
        validate_alpha_settings(settings)
        if args.apply or args.prepare_schema:
            check_backup(args.backup)
        if args.apply:
            approved = json.loads(args.report.read_text(encoding="utf-8"))
            if not isinstance(approved, dict):
                raise SnapshotError("invalid_approved_report")
        engine = create_engine(settings.database_url, isolation_level="READ COMMITTED")
        with Session(engine) as db, db.begin():
            if args.preview:
                db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            target = alpha_database_identity(db, settings)
            if args.prepare_schema:
                report = prepare_recovery_schema(db)
            elif args.preview:
                require_recovery_schema(db)  # Refuse before any eSolver read.
                report = build_recovery_plan(db, current_rows=_fetch_complete_snapshot(db), target=target)
            else:
                report = apply_approved_recovery(db, approved=approved, target=target)
        if args.prepare_schema:
            print(json.dumps({"status": "schema_prepared", **report}))
        elif args.preview:
            # Exclusive creation prevents replacing an already reviewed report.
            with args.report.open("x", encoding="utf-8") as file:
                json.dump(report, file, ensure_ascii=False, indent=2)
            print(json.dumps({"status": "preview", "plan_id": report["plan_id"], "audit": report["audit"]}, ensure_ascii=False))
        else:
            print(json.dumps({"status": "applied", **report}, ensure_ascii=False, indent=2))
    except SnapshotError as exc:
        print(json.dumps({"status": "not_applied", "error_code": str(exc)}))
        return 1
    except Exception:
        print(json.dumps({"status": "not_applied", "error_code": "alpha_recovery_failed"}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
