"""Preview/apply ONLY the reviewed Word repair, with no bootstrap or remote reads."""
import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.startup import bootstrap as _registry  # model registration only; never call bootstrap
from app.modules.quarta_taglio.ddt_recovery import alpha_database_identity
from app.modules.quarta_taglio.ddt_word_recovery import build_plan, apply_plan, lock_inputs
from scripts.recover_ddt_alpha import check_backup


def main():
    parser = argparse.ArgumentParser(description='Recupero Word per quote DDT Alpha; nessuna importazione DDT')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--maintenance-confirmed', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--storage-backup', type=Path)
    args = parser.parse_args()
    if args.apply and not (args.maintenance_confirmed and args.backup and args.storage_backup):
        parser.error('--apply richiede manutenzione e backup DB/storage verificati')
    created, committed, commit_started, engine = [], False, False, None
    try:
        if settings.ddt_word_reuse_enabled:
            raise ValueError('disable_word_worker_in_one_off_container')
        if args.apply:
            check_backup(args.backup)
            if not args.storage_backup.is_absolute() or not args.storage_backup.is_file() or not args.storage_backup.stat().st_size:
                raise ValueError('storage_backup_required')
        approved = json.loads(args.report.read_text(encoding='utf-8')) if args.apply else None
        engine = create_engine(settings.database_url, isolation_level='READ COMMITTED')
        with Session(engine) as db, db.begin():
            if args.preview:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            target = alpha_database_identity(db, settings)
            if args.preview:
                report = build_plan(db, target=target)
            else:
                lock_inputs(db)
                changes = apply_plan(db, approved=approved, target=target, created_paths=created)
                # Exclusive report creation before commit; status remains pending on crash.
                journal = args.report.with_suffix('.applied.json')
                with journal.open('x', encoding='utf-8') as stream:
                    json.dump(dict(status='pending_commit', plan_id=approved['plan_id'], changes=changes), stream, indent=2)
                commit_started = True
        committed = True
        if args.preview:
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2, ensure_ascii=False)
            print(json.dumps(dict(status='preview', summary=report['summary'], plan_id=report['plan_id'])))
        else:
            print(json.dumps(dict(status='committed', plan_id=approved['plan_id'], changes=changes)))
        return 0
    except Exception:
        if not committed and not commit_started:
            for path in created:
                path.unlink(missing_ok=True)
        print(json.dumps(dict(status='check_commit' if committed or commit_started else 'not_applied', error='word_recovery_failed_repeat_audit')))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
