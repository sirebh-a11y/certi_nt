"""Same-workmanship Word reuse, independent of the rolling eSolver window.

Planning is read-only. Applying owns its transaction and writes new files only.
Never use this to select a different OL, workmanship or certificate material.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import secrets
import zipfile
from lxml import etree
from fastapi import HTTPException

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.quarta_taglio import service
from app.modules.quarta_taglio import word_standard, word_reference
from app.modules.quarta_taglio import ddt_shipments as shipments
from app.modules.quarta_taglio.certificate_docx import update_docx_content_controls
from app.modules.quarta_taglio.ddt_context import exact_certificate, quantity_matches
from app.modules.quarta_taglio.ddt_decisions import exclusion_valid, latest_decisions
from app.modules.quarta_taglio.models import (
    QuartaTaglioDdtWorkItem, QuartaTaglioFinalCertificate,
    QuartaTaglioCertificatePdfAttachment,
    QuartaTaglioCertificatePdfVersion,
)

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
SHIPMENT_TAGS = {'CERT_DATE', 'PURCHASER', 'ORDER_CLIENT', 'CONFIRM_ORDER',
                 'DDT_RAW', 'QUANTITY_RAW', 'DDT_FINISHED', 'QUANTITY_FINISHED'}


def clean(value):
    return str(value).strip() if value is not None else ''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_hash(key):
    path = service._certificate_storage_path(key)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def word_facts(key, *, ignore_number=False):
    """Compare templates ignoring only shipment values, not manual/technical text."""
    controls = {}
    hashes = []
    with zipfile.ZipFile(service._certificate_storage_path(key)) as archive:
        for name in sorted(archive.namelist()):
            data = archive.read(name)
            if name.startswith('word/') and name.endswith('.xml'):
                root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
                for node in root.xpath('//w:sdt', namespaces=NS):
                    tags = node.xpath('./w:sdtPr/w:tag/@w:val', namespaces=NS)
                    if not tags:
                        continue
                    tag = tags[0]
                    values = node.xpath('./w:sdtContent//w:t/text()', namespaces=NS)
                    value = ''.join(values)
                    if tag in controls and controls[tag] != value:
                        raise ValueError('duplicate_content_control')
                    controls[tag] = value
                    if tag in SHIPMENT_TAGS or (ignore_number and tag == 'CERT_NUMBER'):
                        for content in node.xpath('./w:sdtContent', namespaces=NS):
                            content.clear()
                data = etree.tostring(root, method='c14n')
            hashes.append((name, hashlib.sha256(data).hexdigest()))
    return controls, digest(hashes)


def shipment_values(item, certificate, controls, *, db=None):
    code = clean(item.cod_f3)
    raw = clean(controls.get('COD_F3_RAW')) == code
    finished = clean(controls.get('COD_F3_FINISHED')) == code
    if raw == finished or not item.ddt_date:
        raise ValueError('word_article_not_identified')
    branch = 'RAW' if raw else 'FINISHED'
    required = {'CERT_NUMBER', 'CERT_DATE', 'PURCHASER', 'ORDER_CLIENT', 'CONFIRM_ORDER',
                'DDT_' + branch, 'QUANTITY_' + branch}
    if not required.issubset(controls):
        raise ValueError('shipment_controls_missing')
    if clean(controls['CERT_NUMBER']) != clean(certificate.certificate_number):
        raise ValueError('word_number_mismatch')
    values = {
        'CERT_DATE': item.ddt_date.strftime('%d/%m/%Y'),
        'PURCHASER': clean(item.cliente), 'ORDER_CLIENT': clean(item.ordine_cliente),
        'CONFIRM_ORDER': clean(item.conferma_ordine),
        'DDT_' + branch: item.ddt_raw,
        'QUANTITY_' + branch: shipments.quantity_text(db, item) if db is not None else service._format_quantity(float(item.quantita)) if item.quantita is not None else '',
    }
    if db is not None:
        values['CERT_NUMBER'] = certificate.certificate_number
    return values


def _materials(values):
    # Keep certificate number case; do not infer identity from a partial CDQ.
    return sorted({(clean(v.get('cdq')), clean(v.get('colata')), clean(v.get('cod_art')),
                    clean(v.get('lotti'))) for v in values})


def _compatible_materials(saved, current):
    """Same supplier certificate/heat/article; only additional known lots allowed.

    Quarta can record further withdrawals after the Word was prepared. This
    does not create a different material for a single supplier certificate.
    Multiple materials can change weighted chemistry as withdrawals increase:
    do not relax their lot comparison. Missing evidence, removals and a new
    certificate/heat/article must still stop reuse. Do not rewrite old snapshots.
    """
    def indexed(values):
        if not isinstance(values, list) or not values:
            return None
        result = {}
        for value in values:
            if not isinstance(value, dict):
                return None
            key = tuple(clean(value.get(k)) for k in ('cdq', 'colata', 'cod_art'))
            lots = value.get('lotti')
            if (not all(key) or key in result or not isinstance(lots, list)
                    or any(not isinstance(lot, str) or not clean(lot) for lot in lots)):
                return None
            result[key] = {clean(lot) for lot in lots}
        return result

    old, now = indexed(saved), indexed(current)
    compatible = bool(old and now and old.keys() == now.keys() and all(
        lots == now[key] or (len(old) == 1 and lots and lots <= now[key])
        for key, lots in old.items()
    ))
    if not compatible or len(old) == 1:
        return compatible
    # A multi-material Word contains weighted chemistry. Same lots alone do
    # not prove compatibility if the proportions of the materials changed.
    def weights(values):
        if all('qta_totale' not in v for v in values):
            return None
        try:
            result = {tuple(clean(v.get(k)) for k in ('cdq', 'colata', 'cod_art')):
                      Decimal(str(v.get('qta_totale'))) for v in values}
            return result if all(x.is_finite() and x > 0 for x in result.values()) else {}
        except InvalidOperation:
            return {}
    before, after = weights(saved), weights(current)
    if before is None and after is None:
        return True
    if not before or not after:
        return before == after
    old_total, new_total = sum(before.values()), sum(after.values())
    return all(before[key] * new_total == after[key] * old_total for key in before)


def _equivalent_source(candidates):
    """Already byte-equivalent templates, including footer/signature images.

    A legacy NULL signer reference is missing metadata, not a different Word.
    Never infer a signer from the PDF closer or silently reconcile two known
    conflicting users. Choose a record with all the consistent known references.
    """
    fields = ('certified_by_user_id', 'quality_manager_user_id')
    known = {field: {getattr(c[0], field) for c in candidates
                     if getattr(c[0], field) is not None} for field in fields}
    if any(len(values) > 1 for values in known.values()):
        return None
    complete = [c for c in candidates if all(
        not known[field] or getattr(c[0], field) in known[field] for field in fields
    )]
    return min(complete, key=lambda c: c[0].id) if complete else None


def plan_item(db, item):
    """No commit, flush, remote SQL or file writes. Also used by the live worker."""
    result = dict(item_id=item.id, ol=item.cod_odp, ddt=item.ddt_raw, cod_f3=item.cod_f3,
                  document=item.id_documento, line=item.id_riga_doc, action='skip', reason=None)
    def stop(reason):
        result['reason'] = reason
        return result
    from app.modules.quarta_taglio.ddt_archive import archived_ids
    if item.id in archived_ids(db, [item]):
        return stop('archived_before_start')
    if not item.cod_odp:
        return stop('missing_ol_from_esolver')
    if item.source_review_reason or not item.ddt_date or not item.certification_unit_key or not item.cod_f3:
        return stop('source_requires_review')
    decision = latest_decisions(db, [item.id]).get(item.id)
    if decision and (exclusion_valid(item, decision) or decision.action in {'exclude', 'review'}):
        return stop('manual_decision_requires_review')
    try:
        group = shipments.facts(db, item)
    except HTTPException:
        return stop('shipment_group_requires_review')
    certificates = list(db.scalars(select(QuartaTaglioFinalCertificate).where(
        QuartaTaglioFinalCertificate.cod_odp == item.cod_odp)))
    exact = [c for c in certificates if exact_certificate(item, c)]
    if len(exact) > 1:
        return stop('duplicate_exact_certificates')
    target = exact[0] if exact else None
    refreshing = False
    result['target_id'] = target.id if target else None
    if target:
        if not quantity_matches(item, target):
            return stop('quantity_changed')
        if target.status == 'pdf_final' or target.storage_key_pdf:
            return stop('existing_document_preserved')
        if target.storage_key_docx:
            reference = word_reference.declared([c for c in certificates if c.cod_f3 == item.cod_f3])
            total_changed = bool(target.shipment_context and target.shipment_context.get('revision') != group['revision'])
            if (reference is None or reference.id == target.id
                    or word_reference.metadata(target).get('revision') == word_reference.metadata(reference).get('revision')) and not total_changed:
                return stop('existing_document_preserved')
            if total_changed and (target.word_source != 'ddt_reused'
                                  or word_reference.metadata(target).get('kind') == 'reference'):
                return stop('existing_document_preserved')  # Tracked fields refresh on explicit download/PDF.
            try:
                refreshing = (target.word_source == 'ddt_reused'
                    and word_reference.metadata(target).get('kind') == 'copy'
                    and word_reference.metadata(target).get('file_hash') == file_hash(target.storage_key_docx))
            except OSError:
                return stop('source_file_or_controls_invalid')
            if not refreshing:
                return stop('manual_copy_requires_review')
        if ((not refreshing and (target.pdf_attachments_initialized or service._pdf_attachments_for_certificate(db, certificate=target)))
                or db.scalar(select(QuartaTaglioCertificatePdfVersion.id).where(
                    QuartaTaglioCertificatePdfVersion.certificate_id == target.id).limit(1))):
            return stop('target_content_requires_review')
    elif any(c.unit_key == item.certification_unit_key or (
        clean(c.esolver_id_documento) == item.id_documento and clean(c.esolver_id_riga_doc) == item.id_riga_doc
    ) or (not c.esolver_id_documento and c.ddt == item.ddt_raw and c.cod_f3 == item.cod_f3)
             for c in certificates):
        return stop('legacy_or_changed_identity')
    sources = [c for c in certificates if c.id != result['target_id'] and clean(c.cod_f3) == clean(item.cod_f3)
               and c.storage_key_docx and c.certificate_number]
    if not sources:
        return stop('word_not_prepared')
    reference = word_reference.declared(sources)
    if reference is not None:
        sources = [reference]
        selected, reason = word_reference.choose(db, sources)
        if selected is None:
            return stop(reason)
    sources = [c for c in sources if not word_standard.is_stale(c, db, for_reuse=True)]
    if not sources:
        return stop('word_standard_outdated')
    rows = service._load_quarta_rows_for_detail(db, cod_odp=item.cod_odp)
    from app.modules.quarta_taglio.ddt_queue import _incoming_status
    incoming = _incoming_status(db, rows)
    if not incoming['ready'] or incoming['ambiguous'] or incoming['rejected']:
        return stop('incoming_not_ready')
    current_values = [dict(cdq=r.cdq, colata=r.colata, cod_art=r.cod_art, lotti=r.cod_lotti, qta_totale=r.qta_totale) for r in rows]
    current = _materials(current_values)
    if not current or any(not cdq or not colata for cdq, colata, _, _ in current):
        return stop('material_identity_incomplete')
    sources = [c for c in sources if _compatible_materials(c.cdq_values, current_values)]
    if target and not refreshing and target.cdq_values and not _compatible_materials(target.cdq_values, current_values):
        return stop('target_material_changed')
    if target and target.certificate_number:
        sources = [c for c in sources if shipments.base_number(c) == shipments.base_number(target)]
    if not sources:
        return stop('no_compatible_word')
    fingerprints, candidates = set(), []
    for source in sources:
        try:
            controls, template = word_facts(source.storage_key_docx, ignore_number=True)
            allocation = shipments.number_plan(db, item, source, target)
            values = shipment_values(item, source, controls, db=db)
            values['CERT_NUMBER'] = allocation['number']
            attachments = service._pdf_attachments_for_certificate(db, certificate=source)
            attachment_facts = [(a.storage_key_pdf, a.original_filename, file_hash(a.storage_key_pdf)) for a in attachments]
            fingerprints.add(digest([shipments.base_number(source), template, attachment_facts, source.conformity_status,
                                     source.conformity_issues]))
            candidates.append((source, values, attachment_facts))
        except (OSError, ValueError, HTTPException, zipfile.BadZipFile, etree.XMLSyntaxError):
            return stop('source_file_or_controls_invalid')
    if len(fingerprints) != 1:
        return stop('different_word_sources')
    chosen = _equivalent_source(candidates)
    if chosen is None:
        return stop('different_word_sources')
    source, values, attachments = chosen
    result.update(action='reuse', source_id=source.id, number=allocation['number'], allocation=allocation, shipment_group=group,
                  refreshing=refreshing,
                  source_file_hash=file_hash(source.storage_key_docx), values=values,
                  attachments=attachments, quantity=str(item.quantita))
    result['fingerprint'] = digest([
        {c.key: getattr(item, c.key) for c in item.__table__.columns},
        [{col.key: getattr(c, col.key) for col in c.__table__.columns} for c in certificates],
        result, current, incoming, word_standard.snapshot(db, item.cod_odp),
    ])
    return result


def apply_item(db, item, plan, created_paths):
    """Caller holds OL lock and owns commit/rollback + new-file compensation."""
    if plan_item(db, item) != plan or plan['action'] != 'reuse':
        raise ValueError('word_reuse_plan_changed')
    source = db.get(QuartaTaglioFinalCertificate, plan['source_id'])
    target = db.get(QuartaTaglioFinalCertificate, plan['target_id']) if plan['target_id'] else None
    key = service._certificate_docx_storage_key(item.cod_odp)
    path = service._certificate_storage_path(key)
    created_paths.append(path)
    update_docx_content_controls(service._certificate_storage_path(source.storage_key_docx), path, plan['values'])
    new_controls, _ = word_facts(key)
    if any(new_controls.get(k) != str(v) for k, v in plan['values'].items()):
        raise ValueError('shipment_fields_not_updated')
    if plan_item(db, item) != plan:
        raise ValueError('source_changed_during_copy')
    if target is None:
        target = QuartaTaglioFinalCertificate(
            cod_odp=item.cod_odp, cod_f3=item.cod_f3, ddt=item.ddt_raw,
            unit_key=item.certification_unit_key, esolver_id_documento=item.id_documento,
            esolver_id_riga_doc=item.id_riga_doc, esolver_rif_lotto_alfanum=item.rif_lotto_alfanum,
            ordine_cliente=item.ordine_cliente, quantita=float(item.quantita) if item.quantita is not None else None,
            certificate_number=plan['number'], draft_number=plan['number'],
            status='draft', cdq_key=source.cdq_key, cdq_signature=deepcopy(source.cdq_signature),
            cdq_values=deepcopy(source.cdq_values), conformity_status=source.conformity_status,
            conformity_issues=deepcopy(source.conformity_issues),
        )
        db.add(target)
    if plan.get('refreshing'):
        for attachment in service._pdf_attachments_for_certificate(db, certificate=target):
            db.delete(attachment)
        db.flush()
    target.cdq_key = source.cdq_key
    target.cdq_signature, target.cdq_values = deepcopy(source.cdq_signature), deepcopy(source.cdq_values)
    target.conformity_status, target.conformity_issues = source.conformity_status, deepcopy(source.conformity_issues)
    target.certificate_number = target.certificate_number or plan['number']
    target.draft_number = target.certificate_number
    target.cert_date = datetime.combine(item.ddt_date, datetime.min.time(), tzinfo=timezone.utc)
    target.fornitore_cliente, target.cdo_lega, target.lega_cod_f3 = item.cliente, item.conferma_ordine, item.cod_f3
    target.storage_key_docx, target.download_token = key, secrets.token_urlsafe(32)
    shipments.record(db, target, item, plan['allocation'])
    word_standard.copy_provenance(source, target)
    target.certified_by_user_id, target.quality_manager_user_id = source.certified_by_user_id, source.quality_manager_user_id
    service._apply_word_file_state(target, path, source='ddt_reused')
    word_reference.mark_copy(target, source)
    db.flush()
    # Embedded pages remain in the copied Word. Keep attachment records for UI/download.
    for a in service._pdf_attachments_for_certificate(db, certificate=source):
        db.add(QuartaTaglioCertificatePdfAttachment(
            certificate_id=target.id, certificate_number=target.certificate_number, cod_odp=target.cod_odp,
            storage_key_pdf=a.storage_key_pdf, original_filename=a.original_filename,
            sort_order=a.sort_order, uploaded_by_user_id=a.uploaded_by_user_id))
    target.pdf_attachments_initialized = True
    db.flush()
    return target.id


def sync_ddt_words(*, session_factory=SessionLocal, cod_odp=None, cod_f3=None):
    """Retry eligible local snapshots even if eSolver's rolling window has moved on."""
    counts = {'prepared': 0, 'review_or_waiting': 0, 'errors': 0}
    with session_factory() as db:
        from app.modules.quarta_taglio.ddt_archive import archived_ids
        statement = select(QuartaTaglioDdtWorkItem).order_by(QuartaTaglioDdtWorkItem.id)
        if cod_odp is not None:
            statement = statement.where(QuartaTaglioDdtWorkItem.cod_odp == cod_odp)
        if cod_f3 is not None:
            statement = statement.where(QuartaTaglioDdtWorkItem.cod_f3 == cod_f3)
        items = list(db.scalars(statement))
        archived = archived_ids(db, items)
        ids = [i.id for i in items if i.id not in archived]
    for item_id in ids:
        created = []
        commit_started = False
        with session_factory() as db:
            try:
                item = db.get(QuartaTaglioDdtWorkItem, item_id)
                if not item or not item.cod_odp:
                    continue
                service._lock_certificate_register_for_ol(db, cod_odp=item.cod_odp)
                db.refresh(item, with_for_update=True)
                list(db.scalars(select(QuartaTaglioFinalCertificate).where(
                    QuartaTaglioFinalCertificate.cod_odp == item.cod_odp).with_for_update()
                    .execution_options(populate_existing=True)))
                plan = plan_item(db, item)
                if plan['action'] == 'reuse':
                    apply_item(db, item, plan, created)
                    commit_started = True
                    db.commit()
                    counts['prepared'] += 1
                elif plan['reason'] != 'existing_document_preserved':
                    counts['review_or_waiting'] += 1
            except Exception:
                db.rollback()
                if not commit_started:
                    for path in created:
                        path.unlink(missing_ok=True)
                counts['errors'] += 1
    return counts
