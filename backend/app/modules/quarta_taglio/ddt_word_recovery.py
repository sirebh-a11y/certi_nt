"""Offline reviewed repair of Word associations, never an import from local data."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.database import Base
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.ddt_word_reuse import digest, file_hash, plan_item, apply_item
from app.modules.quarta_taglio.models import QuartaTaglioDdtWorkItem, QuartaTaglioFinalCertificate, QuartaTaglioCertificatePdfAttachment


def build_plan(db, *, target):
    items = list(db.scalars(select(QuartaTaglioDdtWorkItem).order_by(QuartaTaglioDdtWorkItem.id)))
    plans = [plan_item(db, item) for item in items]
    database = {}
    # Fingerprint the complete local decision baseline, including Incoming/manual overrides.
    # Only hashes leave this function; credentials/record contents are never reported.
    for table in Base.metadata.sorted_tables:
        database[table.name] = digest(sorted(digest(dict(row)) for row in db.execute(select(table)).mappings()))
    files = {}
    for cert in db.scalars(select(QuartaTaglioFinalCertificate)):
        for key in (cert.storage_key_docx, cert.storage_key_pdf):
            if key:
                try:
                    files[key] = file_hash(key)
                except OSError:
                    files[key] = 'unavailable'
    for attachment in db.scalars(select(QuartaTaglioCertificatePdfAttachment)):
        try:
            files[attachment.storage_key_pdf] = file_hash(attachment.storage_key_pdf)
        except OSError:
            files[attachment.storage_key_pdf] = 'unavailable'
    # Pin all Python decision/serialization code, not just the CLI entry point.
    root = Path(service.__file__).parents[2]
    algorithm = {str(p.relative_to(root)): digest(p.read_bytes().hex()) for p in sorted(root.rglob('*.py'))}
    cli = root.parent / 'scripts' / 'recover_ddt_words_alpha.py'
    algorithm['recovery_cli'] = digest(cli.read_bytes().hex())
    facts = dict(target=target, database=database, files=files, algorithm=algorithm, plans=plans)
    return dict(version=1, generated_at=datetime.now(timezone.utc).isoformat(), target=target,
                plan_id=digest(facts), summary=dict(Counter(p['reason'] or p['action'] for p in plans)), items=plans)


def validate_plan(approved, current):
    age = datetime.now(timezone.utc) - datetime.fromisoformat(approved['generated_at'])
    if not timedelta(0) <= age <= timedelta(hours=1):
        raise ValueError('report_expired')
    if approved['version'] != 1 or approved['target'] != current['target'] or approved['plan_id'] != current['plan_id']:
        raise ValueError('report_changed_repeat_preview')
    if approved['items'] != current['items']:
        raise ValueError('report_items_changed')


def lock_inputs(db):
    if db.get_bind().dialect.name != 'postgresql':
        raise ValueError('alpha_requires_postgresql')
    # Offline only: refuse existing writers rather than wait for or interrupt them.
    for table in Base.metadata.sorted_tables:
        name = db.get_bind().dialect.identifier_preparer.format_table(table)
        schema_map = db.connection().get_execution_options().get('schema_translate_map', {})
        if None in schema_map:
            name = db.get_bind().dialect.identifier_preparer.quote_schema(schema_map[None]) + '.' + name
        db.execute(text(f'LOCK TABLE {name} IN SHARE ROW EXCLUSIVE MODE NOWAIT'))


def apply_plan(db, *, approved, target, created_paths):
    current = build_plan(db, target=target)
    validate_plan(approved, current)
    changes = []
    for entry in current['items']:
        if entry['action'] != 'reuse':
            continue
        item = db.get(QuartaTaglioDdtWorkItem, entry['item_id'])
        service._lock_certificate_register_for_ol(db, cod_odp=item.cod_odp)
        fresh = plan_item(db, item)  # Earlier writes in this same batch may add compatible sources.
        if fresh['action'] != 'reuse' or fresh['number'] != entry['number'] or fresh['values'] != entry['values']:
            raise ValueError('batch_association_changed')
        certificate_id = apply_item(db, item, fresh, created_paths)
        changes.append(dict(item_id=item.id, target_id=certificate_id, source_id=fresh['source_id'],
                            previous_target_id=entry['target_id'], file=str(created_paths[-1])))
    return changes
