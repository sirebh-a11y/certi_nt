"""Derived, read-only queue. Never refresh remote links or certification detail here.

Detail retrieval can confirm Incoming or create register records. This projection
only reads local facts and uses the same Incoming evaluator on transient results.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio.ddt_context import exact_certificate as _exact_certificate, quantity_matches as _quantity_matches
from app.modules.quarta_taglio.ddt_snapshot import last_snapshot_runs
from app.modules.quarta_taglio.ddt_decisions import (
    exclusion_valid, latest_decisions, source_revision, REVIEW_MESSAGE,
)
from app.modules.quarta_taglio.ddt_schemas import (
    DdtQueueCountersResponse, DdtQueueResponse, DdtQueueSyncResponse,
    DdtSyncAttemptResponse, DdtWorkItemResponse, DdtDecisionResponse, DdtPdfAction,
)
from app.modules.quarta_taglio.models import (
    QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtWorkItem,
    QuartaTaglioFinalCertificate, QuartaTaglioRow,
)


LABELS = {
    "completed": "Completato", "to_link": "Da collegare",
    "quality_rejected": "Qualità respinta", "waiting_incoming": "In attesa Incoming",
    "word_ready": "Word pronto - completare PDF", "ready": "Pronto lato Incoming",
    "review": "Verifica richiesta", "excluded": "Non richiede certificazione",
    "archived": "Archiviato per avvio",
}

SORT_FIELDS = {
    "ddt_date", "ddt_raw", "cod_odp", "cod_f3", "cliente", "quantita",
    "ordine_cliente", "conferma_ordine", "incoming", "certificazione",
    "state", "last_seen_at",
}


def _clean(value):
    return str(value).strip() if value is not None else ""


def _certification_due_date(ddt_date):
    # The date printed on the DDT is day 1, regardless of when CERTI reads it.
    if ddt_date is None:
        return None
    try:
        return ddt_date + timedelta(days=settings.ddt_certification_days - 1)
    except OverflowError:
        return None


def _file_available(key):
    if not key:
        return False
    try:
        path = service._certificate_storage_path(key)
        return path.is_file() and path.stat().st_size > 0
    except (HTTPException, OSError, ValueError):
        return False


def _pdf_valid(certificate, versions):
    return service._certificate_is_pdf_final(certificate) and any(
        version.status == "active" and version.annulled_at is None
        and version.storage_key_pdf == certificate.storage_key_pdf
        for version in versions
    ) and _file_available(certificate.storage_key_pdf)


def _incoming_status(db, quarta_rows):
    if not quarta_rows:
        return dict(ready=False, rejected=False, ids=[], reasons=["OL non presente nei dati Quarta"], ambiguous=False)
    # Same fallback as certification detail: current rows, otherwise history.
    current = [row for row in quarta_rows if row.seen_in_last_sync]
    selected = current or quarta_rows
    evaluations = service._evaluate_quarta_rows_from_incoming(db, rows=selected)
    states, ids, reasons = [], set(), []
    ambiguous = False
    for row, (color, message, details, matching_ids) in evaluations:
        states.append(SimpleNamespace(status_color=color, status_message=message))
        ids.update(matching_ids)
        reasons.extend(f"CDQ {row.cdq}: {detail}" for detail in details)
        # Reuse the evaluator's explicit ambiguity explanations, never choose a row here.
        ambiguous |= any("verifica manuale" in detail.lower() or "scelta manuale non" in detail.lower()
                         for detail in details)
    ready = bool(states) and len(states) == len(selected) and service._incoming_rows_ready_for_certification(states)
    return dict(ready=ready,
                rejected=any(state.status_message == service.QUALITY_REJECTED_STATUS_MESSAGE for state in states),
                ids=sorted(ids), reasons=list(dict.fromkeys(reasons)), ambiguous=ambiguous)


def _derive(item, certificates, versions_by_id, incoming, family_counts):
    reasons = list(incoming["reasons"])
    if not item.source_present:
        reasons.append("Non più presente nella finestra eSolver; riga conservata nello storico")
    state, certificate_id, word_id = None, None, None
    exact = [cert for cert in certificates if _exact_certificate(item, cert)]
    if len(exact) > 1:
        state = "review"
        reasons.append("Più certificati per la stessa unità: verifica richiesta")
    elif exact:
        cert = exact[0]
        certificate_id = cert.id
        if not _quantity_matches(item, cert) and cert.status == "pdf_final":
            state = "review"
            reasons.append("Quantità eSolver diversa dal PDF chiuso: nessuna modifica automatica")
        elif _pdf_valid(cert, versions_by_id.get(cert.id, [])):
            state = "completed"
        elif cert.status == "pdf_final":
            state = "review"
            reasons.append("PDF finale non verificabile: controllare file e versione attiva")
        elif _file_available(cert.storage_key_docx):
            word_id = cert.id
        elif cert.storage_key_docx:
            state = "review"
            reasons.append("File Word non disponibile")
    if not state and item.source_review_reason:
        state = "review"
        reasons.append("Dati eSolver da verificare: " + item.source_review_reason)
    if not state and not item.cod_odp:
        state = "to_link"
        reasons.append("OL non fornito da eSolver")
    if not state and (not item.cod_f3 or not item.ddt_raw):
        state = "review"
        reasons.append("Cod. F3 o DDT mancante dalla riga eSolver")

    if not state and not exact:
        # Old/changed identities must not be silently treated as a new clean job.
        related = [cert for cert in certificates if (
            (_clean(cert.esolver_id_documento) == item.id_documento
             and _clean(cert.esolver_id_riga_doc) == item.id_riga_doc
             and _clean(cert.esolver_rif_lotto_alfanum) == _clean(item.rif_lotto_alfanum))
            or (not cert.esolver_id_documento and not cert.esolver_id_riga_doc
                and _clean(cert.cod_f3) == _clean(item.cod_f3)
                and _clean(cert.ddt) == _clean(item.ddt_raw))
        )]
        if related:
            state = "review"
            reasons.append("Certificato con dati precedenti o identità incompleta: verificare il collegamento")
        else:
            early = [cert for cert in certificates
                     if _clean(cert.cod_f3) == _clean(item.cod_f3) and not _clean(cert.ddt)
                     and not cert.esolver_id_documento and not cert.esolver_id_riga_doc
                     and not cert.esolver_rif_lotto_alfanum and cert.status != "pdf_final"
                     and cert.storage_key_docx]
            if early:
                if len(early) == 1 and family_counts[(item.cod_odp, item.cod_f3)] == 1:
                    # A source Word is not yet the Word of this shipment.
                    # Only an exact certificate above can expose word_ready.
                    if not _file_available(early[0].storage_key_docx):
                        state = "review"
                        reasons.append("Word preparato prima del DDT ma file non disponibile")
                else:
                    state = "review"
                    reasons.append("Word senza DDT associabile a più quote: verificare senza creare duplicati")
    if not state:
        if incoming["ambiguous"]:
            state = "review"
        elif incoming["rejected"]:
            state = "quality_rejected"
        elif not incoming["ready"]:
            state = "waiting_incoming"
        elif word_id:
            state = "word_ready"
        else:
            state = "ready"
    values = {name: getattr(item, name) for name in DdtWorkItemResponse.model_fields
              if hasattr(item, name)}
    return DdtWorkItemResponse(**values, state=state, label=LABELS[state], reasons=reasons,
                               certification_due_date=_certification_due_date(item.ddt_date),
                               incoming_row_ids=incoming["ids"], incoming_ready=incoming["ready"],
                               certificate_id=certificate_id, word_candidate_id=word_id)


def _project(db, items):
    """Batch local context by OL; no SQL Server reads and no per-DDT refresh."""
    result = []
    # Bounded IN clauses also support SQLite tests and large historical queues.
    cod_odps = sorted({item.cod_odp for item in items if item.cod_odp})
    by_ol, certificates_by_ol, versions_by_id = defaultdict(list), defaultdict(list), defaultdict(list)
    family_counts = Counter()
    for start in range(0, len(cod_odps), 400):
        chunk = cod_odps[start:start + 400]
        for row in db.scalars(select(QuartaTaglioRow).where(QuartaTaglioRow.cod_odp.in_(chunk))):
            by_ol[row.cod_odp].append(row)
        for cert in db.scalars(select(QuartaTaglioFinalCertificate).where(QuartaTaglioFinalCertificate.cod_odp.in_(chunk))):
            certificates_by_ol[cert.cod_odp].append(cert)
        # Count ALL sibling source items, not just filtered/visible items.
        for ol, f3 in db.execute(select(QuartaTaglioDdtWorkItem.cod_odp, QuartaTaglioDdtWorkItem.cod_f3)
                                .where(QuartaTaglioDdtWorkItem.cod_odp.in_(chunk))):
            family_counts[(ol, f3)] += 1
        for version in db.scalars(select(QuartaTaglioCertificatePdfVersion)
                                  .join(QuartaTaglioFinalCertificate)
                                  .where(QuartaTaglioFinalCertificate.cod_odp.in_(chunk))):
            versions_by_id[version.certificate_id].append(version)
    incoming_by_ol = {ol: _incoming_status(db, by_ol[ol]) for ol in cod_odps}
    decisions = latest_decisions(db, [item.id for item in items])
    from app.modules.quarta_taglio.ddt_archive import archive_state, REVIEW_MESSAGE as ARCHIVE_REVIEW
    archived, archive_events = archive_state(db, items)
    from app.modules.quarta_taglio.models import QuartaTaglioDdtArchiveEvent
    boundary = db.scalar(select(QuartaTaglioDdtArchiveEvent).where(
        QuartaTaglioDdtArchiveEvent.action == 'archive').order_by(QuartaTaglioDdtArchiveEvent.id.desc()).limit(1))
    missing = dict(ready=False, rejected=False, ids=[], reasons=[], ambiguous=False)
    for item in items:
        row = _derive(item, certificates_by_ol[item.cod_odp], versions_by_id,
                      incoming_by_ol.get(item.cod_odp, missing), family_counts)
        # Reuse diagnostics are distinct from a missing OL in eSolver. Never guess
        # an OL from the numeric lot; no write/remote query in this projection.
        if (row.state == 'ready' or (row.state == 'review' and any('Word senza DDT associabile' in reason for reason in row.reasons))):
            from app.modules.quarta_taglio.ddt_word_reuse import plan_item
            reuse = plan_item(db, item)
            if reuse['action'] == 'reuse':
                row.state, row.label = 'ready', LABELS['ready']
                row.reasons = [r for r in row.reasons if 'Word senza DDT associabile' not in r]
            elif reuse['reason'] == 'word_standard_outdated':
                row.state, row.label = 'review', 'Word da aggiornare'
                row.reasons.append(service.word_standard.MESSAGE)
            elif reuse['reason'] in {'different_word_sources', 'source_file_or_controls_invalid',
                                      'no_compatible_word', 'target_material_changed', 'legacy_or_changed_identity',
                                      'target_content_requires_review'}:
                row.state, row.label = 'review', LABELS['review']
                row.reasons.append('Word esistente non collegabile automaticamente: verificare compatibilità, file e campi DDT')
        decision = decisions.get(item.id)
        certificate = next((c for c in certificates_by_ol[item.cod_odp] if c.id == row.certificate_id), None)
        if row.state != 'completed' and certificate and service.word_standard.is_stale(certificate, db):
            row.state, row.label = 'review', 'Word da aggiornare'
            row.reasons = [service.word_standard.MESSAGE]
        row.operational_state = row.state
        row.source_revision = source_revision(item)
        if decision:
            row.latest_decision = DdtDecisionResponse.model_validate(decision)
            row.exclusion_active = exclusion_valid(item, decision)
            if row.state != "completed":
                if row.exclusion_active:
                    row.state, row.label = "excluded", LABELS["excluded"]
                elif decision.action in {"exclude", "review"}:
                    row.state, row.label = "review", LABELS["review"]
                    row.reasons.insert(0, REVIEW_MESSAGE)
        if row.state == 'word_ready' and row.certificate_id == row.word_candidate_id:
            certificate = next((c for c in certificates_by_ol[item.cod_odp] if c.id == row.certificate_id), None)
            if (certificate and _exact_certificate(item, certificate) and _quantity_matches(item, certificate)
                    and not item.source_review_reason and item.ddt_date and certificate.cert_date
                    and certificate.certificate_number and not certificate.storage_key_pdf
                    and certificate.status != 'pdf_final'
                    and service._certificate_conformity_status(certificate) == 'conforme'):
                row.pdf_action = DdtPdfAction(
                    id=certificate.id, certificate_number=certificate.certificate_number,
                    pdf_file_name=certificate.pdf_file_name,
                    default_pdf_file_name=service.standard_certificate_file_name(certificate, 'pdf'),
                    word_source=certificate.word_source, ddt=item.ddt_raw,
                    cod_odp=item.cod_odp, cod_f3=item.cod_f3,
                )
        archive_event = archive_events.get(item.id)
        if (boundary and not archive_event and item.ddt_date and item.ddt_date < boundary.cutoff_date
                and item.first_seen_at.replace(tzinfo=timezone.utc) >= boundary.created_at.replace(tzinfo=timezone.utc)):
            row.reasons.insert(0, 'DDT acquisito dopo l’avvio con data precedente: mantenuto disponibile, verificare se da certificare.')
        if archive_event:
            row.latest_archive = DdtDecisionResponse.model_validate(archive_event)
            if item.id in archived:
                row.state, row.label = 'archived', LABELS['archived']
                row.pdf_action = None
                row.certification_due_date = None
                row.reasons = [archive_event.reason]
            elif archive_event.action in {'archive', 'review'}:
                row.reasons.insert(0, ARCHIVE_REVIEW)
        result.append(row)
    return result


def require_queue_pdf_action(db, item, certificate_id, expected_revision):
    """Recheck the clicked share, including exclusions and live Incoming, before PDF."""
    if not expected_revision or source_revision(item) != expected_revision:
        raise HTTPException(409, "La riga DDT è cambiata: aggiorna la vista prima di generare il PDF")
    with db.no_autoflush:
        row = _project(db, [item])[0]
    if row.pdf_action is None or row.pdf_action.id != certificate_id:
        raise HTTPException(409, "PDF non generabile per questa riga: aggiorna la vista e verifica il certificato")


def read_ddt_sync(db):
    """Lightweight status for the page's four-hour connection warning."""
    latest, success = last_snapshot_runs(db)
    return DdtQueueSyncResponse(
        enabled=settings.ddt_snapshot_enabled,
        last_attempt=DdtSyncAttemptResponse.model_validate(latest) if latest else None,
        last_success=DdtSyncAttemptResponse.model_validate(success) if success else None,
    )


def _sort_value(item, field):
    if field == "incoming":
        value = "Qualità respinta" if item.operational_state == "quality_rejected" else "Pronto" if item.incoming_ready else "Da verificare"
    elif field == "certificazione":
        value = "PDF finale" if item.state == "completed" else "Non richiesta" if item.state == "excluded" else "Word presente" if item.word_candidate_id else "Scheda presente" if item.certificate_id else "Da fare"
    elif field == "state":
        value = item.label
    else:
        value = getattr(item, field)
    if isinstance(value, str):
        return value.strip().casefold() or None
    return value


def read_ddt_queue(db, *, scope="active", state=None, query=None, ddt=None, cod_odp=None,
                   cod_f3=None, cliente=None, date_from: date | None = None,
                   date_to: date | None = None, source_present=None,
                   limit=50, offset=0, sort_field="ddt_date", sort_direction="desc", counters_only=False):
    """All filtering precedes pagination. Counts share the same source-filtered population."""
    if scope not in {"active", "completed", "excluded", "archived", "all"} or (state is not None and state not in LABELS):
        raise HTTPException(status_code=422, detail="Filtro stato non valido")
    if limit < 1 or limit > 200 or offset < 0 or sort_field not in SORT_FIELDS or sort_direction not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="Paginazione/ordinamento non valido")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Intervallo date non valido")
    statement = select(QuartaTaglioDdtWorkItem)
    if date_from:
        statement = statement.where(QuartaTaglioDdtWorkItem.ddt_date >= date_from)
    if date_to:
        statement = statement.where(QuartaTaglioDdtWorkItem.ddt_date <= date_to)
    if source_present is not None:
        statement = statement.where(QuartaTaglioDdtWorkItem.source_present == source_present)
    for column, value in ((QuartaTaglioDdtWorkItem.ddt_raw, ddt), (QuartaTaglioDdtWorkItem.cod_odp, cod_odp),
                          (QuartaTaglioDdtWorkItem.cod_f3, cod_f3), (QuartaTaglioDdtWorkItem.cliente, cliente)):
        if value and value.strip():
            statement = statement.where(column.icontains(value.strip(), autoescape=True))
    with db.no_autoflush:
        items = list(db.scalars(statement))
        if query and query.strip():
            needle = query.strip().casefold()
            items = [item for item in items if any(needle in _clean(getattr(item, field)).casefold()
                     for field in ("ddt_raw", "cod_odp", "cod_f3", "cliente", "ordine_cliente", "conferma_ordine",
                                   "id_documento", "id_riga_doc", "rif_lotto_alfanum"))]
        projected = _project(db, items)
        counts = {key: 0 for key in LABELS}
        counts.update(Counter(item.state for item in projected))
        sync = read_ddt_sync(db)
        counters = dict(total=len(projected), active=len(projected) - counts["completed"] - counts["excluded"] - counts["archived"], by_state=counts, sync=sync)
        if counters_only:
            return DdtQueueCountersResponse(**counters)
        selected = [item for item in projected if (scope == "all" or item.state == scope
                    or (scope == "active" and item.state not in {"completed", "excluded", "archived"}))
                    and (state is None or item.state == state)]
        # Sort the whole filtered population before pagination; missing values stay last.
        present = sorted((item for item in selected if _sort_value(item, sort_field) is not None),
                         key=lambda item: (_sort_value(item, sort_field), item.id),
                         reverse=sort_direction == "desc")
        missing = sorted((item for item in selected if _sort_value(item, sort_field) is None),
                         key=lambda item: item.id, reverse=sort_direction == "desc")
        selected = present + missing
        return DdtQueueResponse(**counters, total_items=len(selected), limit=limit, offset=offset,
                                items=selected[offset:offset + limit])
