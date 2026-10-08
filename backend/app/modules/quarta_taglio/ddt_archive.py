"""Explicit, reversible archive. No rolling cutoff and no deletion of source facts.

All eligibility checks are local read-only. A new document/Incoming/decision or
source correction makes an old archive ineffective immediately, even before the
next snapshot persists a review event. Nothing is automatically archived.
"""
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.modules.quarta_taglio import models as m
from app.modules.quarta_taglio.ddt_decisions import source_facts, source_revision, require_quality_decider

REVIEW_MESSAGE = "Dati o lavoro modificati dopo l’archiviazione: quota nuovamente disponibile da verificare."


def latest_events(db, ids):
    result = {}
    ids = list(ids)
    for start in range(0, len(ids), 400):
        latest = select(func.max(m.QuartaTaglioDdtArchiveEvent.id)).where(
            m.QuartaTaglioDdtArchiveEvent.work_item_id.in_(ids[start:start + 400])
        ).group_by(m.QuartaTaglioDdtArchiveEvent.work_item_id)
        for event in db.scalars(select(m.QuartaTaglioDdtArchiveEvent).where(m.QuartaTaglioDdtArchiveEvent.id.in_(latest))):
            result[event.work_item_id] = event
    return result


def protection_reasons(db, items):
    """Conservative OL/document protection; an Incoming candidate is not a match."""
    from app.modules.quarta_taglio import service
    reasons = defaultdict(list)
    ols = {i.cod_odp for i in items if i.cod_odp}
    by_ol = defaultdict(list)
    for model, label in (
        (m.QuartaTaglioFinalCertificate, 'certificate'),
        (m.QuartaTaglioCertificateExtraPages, 'extra_pages'),
        (m.QuartaTaglioCertificatePdfAttachment, 'attachment'),
        (m.QuartaTaglioStandardSelection, 'standard'),
        (m.QuartaTaglioIncomingRowOverride, 'manual_material'),
        (m.QuartaTaglioArticleOverride, 'manual_article'),
    ):
        for ol in db.scalars(select(model.cod_odp).distinct()):
            if ol in ols:
                by_ol[ol].append(label)
    decisions = set(db.scalars(select(m.QuartaTaglioDdtDecision.work_item_id)))
    rows = []
    codes = sorted(ols)
    for start in range(0, len(codes), 400):
        rows.extend(db.scalars(select(m.QuartaTaglioRow).where(m.QuartaTaglioRow.cod_odp.in_(codes[start:start + 400]))))
    # Match the same current/history rule as the DDT queue.
    grouped = defaultdict(list)
    for row in rows:
        if row.cod_odp in ols:
            grouped[row.cod_odp].append(row)
    selected = [r for group in grouped.values() for r in ([r for r in group if r.seen_in_last_sync] or group)]
    if selected:
        for row, (_, _, _, matching_ids) in service._evaluate_quarta_rows_from_incoming(db, rows=selected):
            if matching_ids:
                by_ol[row.cod_odp].append('incoming_present_or_candidate')
        # The normal evaluator omits AI-in-progress rows. They are still work
        # in progress and must never disappear during the start-boundary cleanup.
        from app.modules.acquisition.models import AcquisitionRow
        pending_cdqs = {service._norm(value) for value in db.scalars(select(AcquisitionRow.cdq).where(
            AcquisitionRow.ai_processing_status == 'in_lavorazione')) if value}
        for row in selected:
            if service._norm(row.cdq) in pending_cdqs:
                by_ol[row.cod_odp].append('incoming_processing')
    for item in items:
        reasons[item.id].extend(sorted(set(by_ol[item.cod_odp])))
        if item.id in decisions:
            reasons[item.id].append('manual_decision')
        if item.source_review_reason or not item.ddt_date:
            reasons[item.id].append('source_requires_review')
    return reasons


def archive_state(db, items):
    """Return effective archived IDs and latest events, without any writes."""
    latest = latest_events(db, [i.id for i in items])
    candidates = {i.id for i in items if latest.get(i.id) and latest[i.id].action == 'archive'}
    if not candidates:
        return set(), latest
    # Expand to complete documents: new sibling/protected work reopens the document.
    docs = {i.id_documento for i in items if i.id in candidates}
    peers = []
    docs = sorted(docs)
    for start in range(0, len(docs), 400):
        peers.extend(db.scalars(select(m.QuartaTaglioDdtWorkItem).where(
            m.QuartaTaglioDdtWorkItem.id_documento.in_(docs[start:start + 400]))))
    peer_events = latest_events(db, [i.id for i in peers])
    protected = protection_reasons(db, peers)
    invalid_docs = {i.id_documento for i in peers if protected[i.id]
                    or not peer_events.get(i.id) or peer_events[i.id].action != 'archive'
                    or peer_events[i.id].source_facts != source_facts(i)}
    return {i.id for i in items if i.id in candidates and i.id_documento not in invalid_docs}, latest


def archived_ids(db, items):
    return archive_state(db, items)[0]


def invalidate_archives(db, items, now):
    active, latest = archive_state(db, items)
    for item in items:
        previous = latest.get(item.id)
        if previous and previous.action == 'archive' and item.id not in active:
            db.add(m.QuartaTaglioDdtArchiveEvent(work_item_id=item.id, action='review',
                cutoff_date=previous.cutoff_date, reason=REVIEW_MESSAGE, actor_name='Sistema',
                source_facts=source_facts(item), created_at=now))


def require_operational(db, item):
    if item.id in archived_ids(db, [item]):
        raise HTTPException(409, "DDT archiviato per avvio: ripristinarlo dalla pagina DDT da certificare prima di lavorarlo")


def restore_document(db, item_id, payload, user):
    require_quality_decider(user)
    from app.modules.quarta_taglio.ddt_snapshot import _LOCK_NAMESPACE, _LOCK_ID
    try:
        if db.get_bind().dialect.name == 'postgresql':
            if not db.scalar(text('SELECT pg_try_advisory_xact_lock(:n, :k)'), {'n': _LOCK_NAMESPACE, 'k': _LOCK_ID}):
                raise HTTPException(409, "Aggiornamento DDT in corso. Riprova tra poco.")
        item = db.get(m.QuartaTaglioDdtWorkItem, item_id)
        if not item:
            raise HTTPException(404, "Quota DDT non trovata")
        peers = list(db.scalars(select(m.QuartaTaglioDdtWorkItem).where(
            m.QuartaTaglioDdtWorkItem.id_documento == item.id_documento).with_for_update().execution_options(populate_existing=True)))
        active, events = archive_state(db, peers)
        event = events.get(item_id)
        if (item_id not in active or payload.expected_decision_id != (event.id if event else 0)
                or payload.source_revision != source_revision(item)):
            raise HTTPException(409, "La quota è cambiata. Aggiorna la vista.")
        for peer in peers:
            if peer.id in active:
                db.add(m.QuartaTaglioDdtArchiveEvent(work_item_id=peer.id, action='restore',
                    cutoff_date=events[peer.id].cutoff_date, reason=payload.reason,
                    actor_user_id=user.id, actor_name=user.name, source_facts=source_facts(peer),
                    created_at=datetime.now(timezone.utc)))
        db.commit()
        return {'restored': len(active)}
    except Exception:
        db.rollback()
        raise
