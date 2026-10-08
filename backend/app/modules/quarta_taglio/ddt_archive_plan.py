"""Offline reviewed start boundary. No imports, deletes, or document writes."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select

from app.core.database import Base
from app.modules.quarta_taglio import models as m
from app.modules.quarta_taglio.ddt_archive import archive_state, protection_reasons
from app.modules.quarta_taglio.ddt_decisions import source_facts
from app.modules.quarta_taglio.ddt_word_reuse import digest
from app.modules.quarta_taglio.ddt_word_recovery import validate_plan


def build_plan(db, *, target, cutoff):
    items = list(db.scalars(select(m.QuartaTaglioDdtWorkItem).order_by(m.QuartaTaglioDdtWorkItem.id)))
    protections = protection_reasons(db, items)
    archived, events = archive_state(db, items)
    protected_docs = {i.id_documento for i in items if protections[i.id]
                      or not i.ddt_date or i.ddt_date >= cutoff
                      or (events.get(i.id) and events[i.id].action in {'restore', 'review'})}
    plans = []
    for item in items:
        action = ('already_archived' if item.id in archived else
                  'keep' if item.id_documento in protected_docs else 'archive')
        plans.append(dict(item_id=item.id, document=item.id_documento, ddt=item.ddt_raw,
            ol=item.cod_odp, cod_f3=item.cod_f3, action=action,
            protections=protections[item.id], source_facts=source_facts(item)))
    baseline = {t.name: digest(sorted(digest(dict(r)) for r in db.execute(select(t)).mappings()))
                for t in Base.metadata.sorted_tables}
    root = Path(__file__).parents[2]
    algorithm = {str(p.relative_to(root)): digest(p.read_bytes().hex()) for p in sorted(root.rglob('*.py'))}
    cli = root.parent / 'scripts' / 'archive_ddt.py'
    algorithm['cli'] = digest(cli.read_bytes().hex())
    return dict(version=1, generated_at=datetime.now(timezone.utc).isoformat(), target=target,
        cutoff=cutoff.isoformat(), items=plans, summary=dict(Counter(p['action'] for p in plans)),
        plan_id=digest([target, cutoff, plans, baseline, algorithm]))


def apply_plan(db, *, approved, target, cutoff, actor):
    current = build_plan(db, target=target, cutoff=cutoff)
    validate_plan(approved, current)
    if approved.get('cutoff') != current['cutoff']:
        raise ValueError('cutoff_changed')
    changed = []
    for row in current['items']:
        if row['action'] == 'archive':
            db.add(m.QuartaTaglioDdtArchiveEvent(work_item_id=row['item_id'], action='archive',
                cutoff_date=cutoff, reason=f"Storico precedente al {cutoff.strftime('%d/%m/%Y')}, senza lavoro avviato; archiviato per avvio.",
                actor_name=actor, source_facts=row['source_facts'], batch_id=current['plan_id'],
                created_at=datetime.now(timezone.utc)))
            changed.append(row['item_id'])
    db.flush()
    return changed
