"""Preview only: classify identities/provenance before a separately approved repair.

No flush/commit, writes, bootstrap, remote queries, re-numbering or PDF generation.
In particular a mismatched hash is NOT evidence allowing automatic adoption.
"""
from collections import Counter, defaultdict
from sqlalchemy import select

from app.modules.quarta_taglio import service, word_reference as refs, ddt_word_reuse as reuse
from app.modules.quarta_taglio.models import (
    QuartaTaglioFinalCertificate as Certificate,
    QuartaTaglioCertificatePdfVersion as Version,
    QuartaTaglioCertificatePdfAttachment as Attachment,
    QuartaTaglioCertificateExtraPages as ExtraPages,
    QuartaTaglioDdtWorkItem as Item,
)


def preview(db):
    certificates = list(db.scalars(select(Certificate).order_by(Certificate.id)))
    by_id = {c.id:c for c in certificates}
    report = dict(preview_only=True, certificates=len(certificates),
                  states=dict(Counter(c.status for c in certificates)),
                  reference_checks=[], identity_issues=[], manual_bases=[], ddt_plans=[])
    paths = defaultdict(list)
    protected = dict(records=[], files={})
    def protect(key):
        if key and key not in protected['files']:
            try: protected['files'][key] = reuse.file_hash(key)
            except (OSError, ValueError): protected['files'][key] = 'unavailable'
    for c in certificates:
        protected['records'].append({col.key:getattr(c,col.key) for col in c.__table__.columns})
        protect(c.storage_key_docx)
        protect(c.storage_key_pdf)
        meta = refs.metadata(c)
        protect(meta.get('storage_key'))
        if c.storage_key_docx:
            paths[c.storage_key_docx].append(c.id)
        if meta.get('kind') == 'copy':
            source = by_id.get(meta.get('source_id'))
            if source is None or (source.cod_odp,source.cod_f3)!=(c.cod_odp,c.cod_f3):
                report['identity_issues'].append(dict(id=c.id, reason='invalid_source_id', source_id=meta.get('source_id')))
        if meta.get('kind') in {'reference','copy'}:
            reason = refs.integrity_reason(c)
            action = 'preserve'
            if reason:
                action = 'review_required_no_automatic_adoption'
            elif meta.get('storage_key') != c.storage_key_docx:
                action = 'candidate_metadata_path_only'
            report['reference_checks'].append(dict(id=c.id, ol=c.cod_odp, f3=c.cod_f3,
                status=c.status, number=c.certificate_number, kind=meta.get('kind'),
                source_id=meta.get('source_id'), revision=meta.get('revision'), action=action,
                reason=reason, current_key=c.storage_key_docx,
                current_hash=protected['files'].get(c.storage_key_docx), recorded_key=meta.get('storage_key')))
        if c.storage_key_docx and c.certificate_number:
            legacy_key = f'certificati_finali/manual_bases/{service._safe_file_part(c.certificate_number)}_manual_base.docx'
            expected = service._certificate_manual_base_docx_storage_key(c)
            if service._certificate_storage_path(legacy_key).is_file():
                protect(legacy_key)
                report['manual_bases'].append(dict(id=c.id, ol=c.cod_odp, number=c.certificate_number,
                    legacy_key=legacy_key, expected_key=expected,
                    action='preserve' if service._certificate_storage_path(expected).is_file()
                           else 'candidate_build_from_own_validated_word',
                    own_word_integrity=refs.integrity_reason(c)))
    for key,ids in paths.items():
        if len(ids)>1:
            report['identity_issues'].append(dict(reason='shared_current_word_path', ids=ids, key=key))
    for model in (Version, Attachment, ExtraPages):
        for record in db.scalars(select(model)):
            protected['records'].append({col.key:getattr(record,col.key) for col in model.__table__.columns})
            protect(getattr(record,'storage_key_pdf',None))
            protect(getattr(record,'storage_key_docx',None))
    for item in db.scalars(select(Item).order_by(Item.id)):
        protected['records'].append({col.key:getattr(item,col.key) for col in Item.__table__.columns})
        plan = reuse.plan_item(db,item)
        # No tokens/URLs/full business record dump in the report. Existing IDs
        # remain stable; a missing target will receive its own normal new ID.
        report['ddt_plans'].append({k:plan.get(k) for k in ('item_id','ol','cod_f3','ddt','action','reason','source_id','target_id','number')})
    report['baseline_hash'] = reuse.digest(protected)
    report['summary'] = dict(reference_actions=dict(Counter(r['action'] for r in report['reference_checks'])),
        identity_issues=len(report['identity_issues']), manual_bases=len(report['manual_bases']),
        ddt_actions=dict(Counter(p['reason'] or p['action'] for p in report['ddt_plans'])))
    return report
