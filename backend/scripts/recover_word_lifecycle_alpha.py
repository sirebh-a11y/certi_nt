"""Separate offline Alpha metadata repair. Never called by bootstrap or the app.

--preview requires an explicit JSON list of reviewed requests; --apply requires
approval of that exact plan ID, maintenance and verified DB/storage backups.
No Word/PDF writes, DDT imports, new certificate IDs or automatic PDF generation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.startup import bootstrap as _registry  # model registration only
from app.modules.quarta_taglio.ddt_recovery import alpha_database_identity
from app.modules.quarta_taglio.word_lifecycle_recovery import build_plan, apply_plan
from scripts.recover_ddt_alpha import check_backup


def _backup_hash(path):
    if not path or not path.is_absolute() or not path.is_file() or not path.stat().st_size:
        raise ValueError('readable_backup_required')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _journal(path, event, mode):
    with path.open(mode, encoding='utf-8') as stream:
        stream.write(json.dumps(event, default=str, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description='Recupero puntuale metadati Word Alpha; nessuna modifica ai documenti')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--requests', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--approved-plan-id')
    parser.add_argument('--maintenance-confirmed', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--storage-backup', type=Path)
    args = parser.parse_args()
    if args.preview and (not args.requests or args.approved_plan_id):
        parser.error('--preview richiede --requests, non --approved-plan-id')
    if args.apply and (args.requests or not all((args.approved_plan_id, args.maintenance_confirmed, args.backup, args.storage_backup))):
        parser.error('--apply richiede plan ID approvato, manutenzione e backup DB/storage; usa le richieste del report')
    engine, commit_started = None, False
    try:
        if settings.ddt_word_reuse_enabled:
            raise ValueError('disable_word_worker_in_one_off_container')
        backups = None
        if args.apply:
            check_backup(args.backup)
            backups = dict(database=_backup_hash(args.backup), storage=_backup_hash(args.storage_backup))
            approved = json.loads(args.report.read_text(encoding='utf-8'))
            journal = args.report.with_suffix('.journal.jsonl')
        else:
            requests = json.loads(args.requests.read_text(encoding='utf-8'))
        engine = create_engine(settings.database_url, isolation_level='READ COMMITTED')
        with Session(engine, autoflush=False) as db, db.begin():
            if args.preview:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout = '120s'"))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            target = alpha_database_identity(db, settings)
            if args.preview:
                report = build_plan(db, target=target, requests=requests)
            else:
                result = apply_plan(db, approved=approved, target=target, approved_plan_id=args.approved_plan_id)
                # Exclusive durable journal BEFORE commit; never overwrite a
                # previous/uncertain attempt. Repeat starts with fresh preview.
                _journal(journal, dict(status='pending_commit', plan=approved,
                    result=result, backup_hashes=backups), 'x')
                commit_started = True
        if args.preview:
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2, ensure_ascii=False)
            print(json.dumps(dict(status='preview_only', plan_id=report['plan_id'],
                                 ids=[a['id'] for a in report['actions']])))
        else:
            _journal(journal, dict(status='committed', plan_id=approved['plan_id'], result=result), 'a')
            print(json.dumps(dict(status='committed', result=result)))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='check_commit' if commit_started else 'not_applied',
                             error=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
