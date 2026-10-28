"""Offline, allowlisted metadata repair. Never writes a Word/PDF or reissues it.

A fingerprint mismatch is NOT automatically accepted: it requires an explicitly
reviewed file hash and evidence note, then separate approval of the exact plan.
The ordinary application and bootstrap never call this module.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

from app.core.database import Base
from app.modules.quarta_taglio import service, word_reference as refs, word_standard
from app.modules.quarta_taglio import ddt_word_reuse as reuse
from app.modules.quarta_taglio.ddt_word_recovery import lock_inputs
from app.modules.quarta_taglio.models import (
    QuartaTaglioFinalCertificate as Certificate,
    QuartaTaglioCertificatePdfVersion as Version,
    QuartaTaglioCertificatePdfAttachment as Attachment,
    QuartaTaglioCertificateExtraPages as ExtraPages,
)

VERSION = 1
MAX_AGE = timedelta(hours=1)


def protected_baseline(db, ids):
    """Pin ALL records/files, excluding only allowlisted word_reference cells.

No business records or tokens are returned: only hashes. Own metadata is pinned
separately by exact before/after checks. Unrelated user work invalidates preview.
"""
    database, files = {}, {}
    for table in Base.metadata.sorted_tables:
        rows = []
        for raw in db.execute(select(table)).mappings():
            row = dict(raw)
            if table.name == Certificate.__tablename__ and row['id'] in ids:
                row.pop('word_reference', None)
            rows.append(reuse.digest(row))
        database[table.name] = sorted(rows)
    def protect(key):
        if key and key not in files:
            files[key] = reuse.file_hash(key)  # Missing files are a STOP, not a wildcard.
    for c in db.scalars(select(Certificate)):
        protect(c.storage_key_docx)
        protect(c.storage_key_pdf)
        meta = refs.metadata(c)
        # Old paths are captured in each action too. The baseline must stay
        # invariant after their metadata-only correction (current files above).
        if c.id not in ids:
            protect(meta.get('storage_key'))
    for model, key in ((Version, 'storage_key_pdf'), (Attachment, 'storage_key_pdf'),
                       (ExtraPages, 'storage_key_docx')):
        for record in db.scalars(select(model)):
            protect(getattr(record, key))
    return reuse.digest(dict(database=database, files=files))


def algorithm_hash():
    root = Path(service.__file__).parents[2]
    sources = {str(p.relative_to(root)): reuse.digest(p.read_bytes().hex())
               for p in sorted(root.rglob('*.py'))}
    cli = root.parent / 'scripts' / 'recover_word_lifecycle_alpha.py'
    sources['recovery_cli'] = reuse.digest(cli.read_bytes().hex())
    return reuse.digest(sources)


def _action(db, request):
    if set(request) - {'id', 'mode', 'verified_word_sha256', 'review_note'}:
        raise ValueError('unknown_request_fields')
    c = db.get(Certificate, request['id'])
    if c is None:
        raise ValueError('certificate_missing')
    before = deepcopy(refs.metadata(c))
    if before.get('kind') != 'reference' or not before.get('revision'):
        raise ValueError('explicit_reference_required')
    controls, template = reuse.word_facts(c.storage_key_docx)
    if controls.get('CERT_NUMBER') != c.certificate_number or c.cod_f3 not in {
            controls.get('COD_F3_RAW'), controls.get('COD_F3_FINISHED')}:
        raise ValueError('word_identity_not_verified')
    current_hash = reuse.file_hash(c.storage_key_docx)
    before_key = before.get('storage_key')
    before_hash = reuse.file_hash(before_key) if before_key else None
    after = deepcopy(before)
    mode = request['mode']
    if mode == 'equivalent_path':
        if before_key == c.storage_key_docx or template != before.get('template_hash'):
            raise ValueError('not_an_equivalent_path_repair')
        if not before_key or reuse.word_facts(before_key)[1] != template:
            raise ValueError('previous_word_not_equivalent')
        after['storage_key'] = c.storage_key_docx
    elif mode == 'reviewed_fingerprint':
        if (c.status != 'draft' or c.storage_key_pdf
                or db.scalar(select(Version.id).where(Version.certificate_id == c.id).limit(1))):
            raise ValueError('fingerprint_repair_requires_never_closed_draft')
        if before_key != c.storage_key_docx or template == before.get('template_hash'):
            raise ValueError('not_a_fingerprint_only_repair')
        if request.get('verified_word_sha256') != current_hash or len(request.get('review_note', '').strip()) < 20:
            raise ValueError('independent_content_review_required')
        latest = refs.declared(refs.sources_for(db, c.cod_odp, c.cod_f3))
        if latest is None or latest.id != c.id or refs.material_changed(db, c) or word_standard.is_stale(c, db, for_reuse=True):
            raise ValueError('reference_not_current')
        technical = reuse.word_facts(c.storage_key_docx, ignore_number=True)[1]
        for copy in refs.sources_for(db, c.cod_odp, c.cod_f3):
            meta = refs.metadata(copy)
            if (meta.get('kind') == 'copy' and meta.get('source_id') == c.id
                    and meta.get('revision') == before['revision'] and copy.status != 'pdf_final'
                    and reuse.word_facts(copy.storage_key_docx, ignore_number=True)[1] != technical):
                raise ValueError('open_descendant_content_requires_review')
        after['template_hash'] = template
    else:
        raise ValueError('unsupported_repair_mode')
    return dict(id=c.id, ol=c.cod_odp, f3=c.cod_f3, number=c.certificate_number,
                mode=mode, current_key=c.storage_key_docx, current_hash=current_hash,
                previous_key=before_key, previous_hash=before_hash,
                before=before, after=after)


def build_plan(db, *, target, requests, now=None):
    if not isinstance(requests, list) or not requests:
        raise ValueError('explicit_nonempty_allowlist_required')
    ids = [r.get('id') for r in requests]
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('invalid_allowlist_ids')
    requests = sorted(deepcopy(requests), key=lambda r: r['id'])
    actions = [_action(db, r) for r in requests]
    plan = dict(version=VERSION, generated_at=(now or datetime.now(timezone.utc)).isoformat(),
                target=target, requests=requests, actions=actions,
                algorithm=algorithm_hash(), protected_hash=protected_baseline(db, set(ids)))
    plan['plan_id'] = reuse.digest(plan)
    return plan


def apply_plan(db, *, approved, target, approved_plan_id, now=None):
    """Caller owns the transaction/backup/journal. No filesystem writes or commits."""
    body = {k: v for k, v in approved.items() if k != 'plan_id'}
    if approved.get('plan_id') != approved_plan_id or reuse.digest(body) != approved_plan_id:
        raise ValueError('unapproved_or_modified_plan')
    when = datetime.fromisoformat(approved['generated_at'])
    now = now or datetime.now(timezone.utc)
    if when.tzinfo is None or not timedelta(0) <= now - when <= MAX_AGE:
        raise ValueError('expired_plan_repeat_preview')
    if approved.get('version') != VERSION or approved.get('target') != target or approved['algorithm'] != algorithm_hash():
        raise ValueError('wrong_target_or_code')
    lock_inputs(db)  # PostgreSQL NOWAIT locks: never wait for/interfere with user work.
    ids = {a['id'] for a in approved['actions']}
    if protected_baseline(db, ids) != approved['protected_hash']:
        raise ValueError('database_or_files_changed_repeat_preview')
    states = []
    for action in approved['actions']:
        c = db.get(Certificate, action['id'], populate_existing=True)
        meta = refs.metadata(c)
        if meta != action['before'] and meta != action['after']:
            raise ValueError('reference_changed_repeat_preview')
        for key, expected in ((action['current_key'], action['current_hash']),
                              (action['previous_key'], action['previous_hash'])):
            if key and reuse.file_hash(key) != expected:
                raise ValueError('reviewed_file_changed')
        states.append(meta == action['after'])
    if all(states):
        return dict(status='already_applied', ids=sorted(ids))
    if any(states):
        raise ValueError('partial_application_requires_review')
    current = build_plan(db, target=target, requests=approved['requests'], now=when)
    if current != approved:
        raise ValueError('repair_decision_changed_repeat_preview')
    for action in approved['actions']:
        # Preserve timestamps too: this is not a new document or user revision.
        db.execute(update(Certificate).where(Certificate.id == action['id']).values(
            word_reference=action['after'], updated_at=Certificate.updated_at),
            execution_options={'synchronize_session': False})
    db.expire_all()
    if protected_baseline(db, ids) != approved['protected_hash']:
        raise ValueError('protected_data_changed_rollback_required')
    if any(refs.metadata(db.get(Certificate, a['id'])) != a['after'] for a in approved['actions']):
        raise ValueError('metadata_postcheck_failed')
    return dict(status='applied_in_transaction', ids=sorted(ids))
