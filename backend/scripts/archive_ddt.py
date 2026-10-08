"""Explicit offline archive maintenance, identical algorithm on separate DBs."""
import argparse
import json
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.startup import bootstrap as _registry  # registration only
from app.modules.quarta_taglio.models import QuartaTaglioDdtArchiveEvent
from app.modules.quarta_taglio.ddt_recovery import alpha_database_identity
from app.modules.quarta_taglio.ddt_word_reuse import digest
from app.modules.quarta_taglio.ddt_word_recovery import lock_inputs
from app.modules.quarta_taglio.ddt_archive_plan import build_plan, apply_plan
from scripts.recover_ddt_alpha import check_backup


def main():
    parser = argparse.ArgumentParser(description='Archiviazione reversibile DDT senza lavoro, nessuna cancellazione')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-schema', action='store_true')
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--environment', choices=['local', 'alpha'], required=True)
    parser.add_argument('--cutoff', type=date.fromisoformat, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--maintenance-confirmed', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--actor', default='Manutenzione autorizzata')
    args = parser.parse_args()
    if (args.apply or args.prepare_schema) and not (args.maintenance_confirmed and args.backup):
        parser.error('Scrittura richiede manutenzione e backup verificato')
    if not args.prepare_schema and not args.report:
        parser.error('--report obbligatorio')
    if not args.actor.strip() or len(args.actor) > 255:
        parser.error('Autore non valido')
    engine = None
    commit_started = False
    try:
        if settings.ddt_snapshot_enabled or settings.ddt_word_reuse_enabled:
            raise ValueError('disable_workers_in_maintenance_container')
        if args.apply or args.prepare_schema:
            check_backup(args.backup)
        approved = json.loads(args.report.read_text(encoding='utf-8')) if args.apply else None
        engine = create_engine(settings.database_url)
        with Session(engine) as db, db.begin():
            if args.preview:
                db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            if args.environment == 'alpha':
                target = alpha_database_identity(db, settings)
            else:
                if settings.app_env.lower() != 'development':
                    raise ValueError('local_environment_mismatch')
                target = dict(environment='local', database_id=digest(db.execute(text(
                    'SELECT current_database(), system_identifier::text FROM pg_control_system()')).one()._asdict()))
            if args.prepare_schema:
                # Add ONLY the new table; never bootstrap or run application jobs.
                QuartaTaglioDdtArchiveEvent.__table__.create(db.connection(), checkfirst=True)
                report = {'status': 'schema_prepared'}
            elif args.preview:
                report = build_plan(db, target=target, cutoff=args.cutoff)
                with args.report.open('x', encoding='utf-8') as stream:
                    json.dump(report, stream, indent=2, ensure_ascii=False)
            else:
                lock_inputs(db)
                changed = apply_plan(db, approved=approved, target=target, cutoff=args.cutoff, actor=args.actor)
                report = dict(status='pending_commit', plan_id=approved['plan_id'], item_ids=changed)
                with args.report.with_suffix('.applied.json').open('x', encoding='utf-8') as stream:
                    json.dump(report, stream, indent=2)
            commit_started = not args.preview
        print(json.dumps({'status': 'preview' if args.preview else 'committed',
                          'summary': report.get('summary'), 'archived': len(report.get('item_ids', []))}))
        return 0
    except Exception:
        print(json.dumps({'status': 'check_commit' if commit_started else 'not_applied',
                          'error': 'archive_failed_repeat_audit'}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
