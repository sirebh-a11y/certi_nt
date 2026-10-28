"""An explicit Word edit, rather than a shipment copy, defines the reusable Word.

No legacy winner is inferred from created_at/updated_at. Historical conflicts
require one explicit adoption; normal uploads/generation publish automatically.
"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, inspect, text

from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as Certificate


def metadata(certificate):
    return getattr(certificate, 'word_reference', None) or {}


def declared(sources):
    """Only explicit publications advance the reference; automatic copies cannot."""
    references = [c for c in sources if metadata(c).get('kind') == 'reference']
    if not references:
        return None
    return max(references, key=lambda c: (metadata(c).get('published_at', ''), c.id or 0))


def sources_for(db, ol, f3):
    return list(db.scalars(select(Certificate).where(
        Certificate.cod_odp == ol, Certificate.cod_f3 == f3,
        Certificate.storage_key_docx.is_not(None), Certificate.certificate_number.is_not(None))))


MESSAGES = {
    'reference_file_changed': 'Il Word di riferimento non coincide con la versione registrata: verifica tecnica necessaria. Il documento viene conservato.',
    'source_file_or_controls_invalid': 'Il Word di riferimento o i suoi campi automatici non sono verificabili. Il documento viene conservato.',
    'different_word_sources': 'Sono presenti versioni Word diverse: occorre verificare quale documento completo usare come riferimento.',
    'no_compatible_word': 'Il Word esistente non copre il materiale attuale dell’OL. Verifica Incoming e aggiorna il Word.',
    'target_material_changed': 'Il materiale della riga è cambiato rispetto al Word: verifica Incoming e aggiorna il Word.',
    'legacy_or_changed_identity': 'I riferimenti della riga DDT sono cambiati: nessuna riassegnazione automatica del certificato.',
    'manual_copy_requires_review': 'Questa copia Word è stata lavorata separatamente: non viene sostituita automaticamente.',
    'target_content_requires_review': 'Questa riga ha documenti o versioni precedenti da conservare: aggiornamento automatico non applicabile.',
}


def integrity_reason(certificate):
    """Validate a tracked file without accepting unpublished changes or writing it."""
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    meta = metadata(certificate)
    if meta.get('kind') not in {'reference', 'copy'}:
        return None  # Legacy provenance is not retroactively invented.
    try:
        controls, template = reuse.word_facts(certificate.storage_key_docx)
        if controls.get('CERT_NUMBER') and controls['CERT_NUMBER'] != certificate.certificate_number:
            return 'source_file_or_controls_invalid'
        if meta['kind'] == 'reference' and template != meta.get('template_hash'):
            return 'reference_file_changed'
        if meta['kind'] == 'copy' and reuse.file_hash(certificate.storage_key_docx) != meta.get('file_hash'):
            return 'manual_copy_requires_review'
    except (OSError, ValueError, HTTPException, reuse.zipfile.BadZipFile, reuse.etree.XMLSyntaxError, TypeError):
        return 'source_file_or_controls_invalid'
    return None


def require_integrity(certificate):
    reason = integrity_reason(certificate)
    if reason:
        raise HTTPException(409, MESSAGES[reason])


def before_automatic(certificate):
    """Pin a valid source BEFORE an app-owned rewrite; never heal an old mismatch."""
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    require_integrity(certificate)
    try:
        file_hash = reuse.file_hash(certificate.storage_key_docx)
    except (OSError, ValueError, TypeError):
        raise HTTPException(409, MESSAGES['source_file_or_controls_invalid']) from None
    return dict(metadata=deepcopy(metadata(certificate)), storage_key=certificate.storage_key_docx,
                file_hash=file_hash)


def check_source_unchanged(certificate, before):
    """Recheck trusted input; explicit edits publish separately from this guard."""
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    try:
        current_hash = reuse.file_hash(before['storage_key'])
    except (OSError, ValueError, TypeError):
        raise HTTPException(409, MESSAGES['source_file_or_controls_invalid']) from None
    if current_hash != before['file_hash']:
        raise HTTPException(409, 'Il Word sorgente è cambiato durante l’aggiornamento: nessuna sostituzione automatica.')
    if metadata(certificate) != before['metadata']:
        raise HTTPException(409, 'Il riferimento Word è cambiato durante l’aggiornamento: riprova.')


def after_automatic(certificate, before, *, origin):
    """Maintain provenance for a trusted rewrite, not a new user publication.

    Callers validate/pin the old file, write to a fresh path and own the transaction.
    Revision/source_id remain unchanged: automatic copies can never elect themselves.
    """
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    previous = before['metadata']
    check_source_unchanged(certificate, before)
    if not previous:
        return
    current = deepcopy(previous)
    if before['storage_key'] != certificate.storage_key_docx:
        history = current.setdefault('automatic_history', [])
        history.append(dict(storage_key=before['storage_key'], file_hash=before['file_hash'], origin=origin))
    current['storage_key'] = certificate.storage_key_docx
    if current.get('kind') == 'reference':
        _, current['template_hash'] = reuse.word_facts(certificate.storage_key_docx)
    elif current.get('kind') == 'copy':
        current['file_hash'] = reuse.file_hash(certificate.storage_key_docx)
    certificate.word_reference = current


def conversion_state(db, certificate, *, refresh=False):
    """Identity of the Word actually converted, including the reusable source."""
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    if refresh:
        db.refresh(certificate)
    reference = declared(sources_for(db, certificate.cod_odp, certificate.cod_f3))
    if reference is not None and refresh:
        db.refresh(reference)
    # The converted document is byte-pinned below. Its separate source is pinned
    # by technical content/revision: source-only shipment headers or a maintained
    # storage path must not cancel this PDF when its own Word did not change.
    try:
        source = None if reference is None else dict(id=reference.id,
            revision=metadata(reference).get('revision'),
            template=reuse.word_facts(reference.storage_key_docx)[1])
        word_hash = reuse.file_hash(certificate.storage_key_docx)
    except (OSError, ValueError, HTTPException, reuse.zipfile.BadZipFile, reuse.etree.XMLSyntaxError):
        raise HTTPException(409, MESSAGES['source_file_or_controls_invalid']) from None
    # Expose the SAME hash to the frozen-input check. Independently hashing an
    # older path would let a new record snapshot authorize an old document.
    return dict(word_hash=word_hash, state_hash=reuse.digest(dict(
        record={col.key:getattr(certificate, col.key) for col in certificate.__table__.columns
                if col.key not in {'created_at', 'updated_at'}},
        word_hash=word_hash, reference=source)))


def choose(db, sources):
    """Validate explicit publication, or conservatively compare unmarked legacy files."""
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    chosen = declared(sources)
    candidates, fingerprints = [], set()
    for c in [chosen] if chosen is not None else sources:
        try:
            controls, template = reuse.word_facts(c.storage_key_docx)
            if 'CERT_NUMBER' in controls and controls['CERT_NUMBER'] != c.certificate_number:
                return None, 'source_file_or_controls_invalid'
            if chosen is not None and template != metadata(c).get('template_hash'):
                return None, 'reference_file_changed'
            from app.modules.quarta_taglio.ddt_shipments import base_number
            _, comparison = reuse.word_facts(c.storage_key_docx, ignore_number=True)
            attachments = [(a.storage_key_pdf, a.original_filename, reuse.file_hash(a.storage_key_pdf))
                           for a in reuse.service._pdf_attachments_for_certificate(db, certificate=c)]
            fingerprints.add(reuse.digest([base_number(c), comparison, attachments,
                                          c.conformity_status, c.conformity_issues]))
            candidates.append((c, {}, attachments))
        except (OSError, ValueError, HTTPException, reuse.zipfile.BadZipFile, reuse.etree.XMLSyntaxError):
            return None, 'source_file_or_controls_invalid'
    if not candidates:
        return None, 'word_not_prepared'
    if len(fingerprints) != 1:
        return None, 'different_word_sources'
    equivalent = reuse._equivalent_source(candidates)
    return (equivalent[0], None) if equivalent else (None, 'different_word_sources')


def publish(db, certificate, *, actor_id=None, origin):
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    if not certificate.storage_key_docx or not certificate.cod_f3 or not certificate.certificate_number:
        raise HTTPException(409, 'Preparare prima un Word numerato per questa lavorazione.')
    db.flush()
    _, template = reuse.word_facts(certificate.storage_key_docx)
    previous = metadata(certificate)
    history = deepcopy(previous.get('history', []))
    if previous.get('kind') == 'reference':
        history.append({k: v for k, v in previous.items() if k != 'history'})
    certificate.word_reference = dict(kind='reference', revision=uuid4().hex,
        published_at=datetime.now(timezone.utc).isoformat(), actor_id=actor_id,
        origin=origin, template_hash=template, storage_key=certificate.storage_key_docx, history=history)
    db.add(certificate)


def mark_copy(target, source):
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    history = deepcopy(metadata(target).get('history', []))
    previous = metadata(target)
    if previous.get('kind') == 'copy' and previous.get('storage_key'):
        history.append({k: v for k, v in previous.items() if k != 'history'})
    target.word_reference = dict(kind='copy', source_id=source.id, history=history,
        revision=metadata(source).get('revision'),
        storage_key=target.storage_key_docx, file_hash=reuse.file_hash(target.storage_key_docx))


def current_materials(db, ol):
    from app.modules.quarta_taglio import service
    return [dict(cdq=r.cdq, colata=r.colata, cod_art=r.cod_art, lotti=r.cod_lotti, qta_totale=r.qta_totale)
            for r in service._load_quarta_rows_for_detail(db, cod_odp=ol)]


def material_changed(db, certificate, *, current=None):
    from app.modules.quarta_taglio.ddt_word_reuse import _compatible_materials
    # Incomplete legacy metadata is not evidence of a known material change.
    return bool(certificate and certificate.cdq_values and not _compatible_materials(
        certificate.cdq_values, current if current is not None else current_materials(db, certificate.cod_odp)))


def material_message(db, certificate, *, current=None):
    current = current if current is not None else current_materials(db, certificate.cod_odp)
    old_keys = {(v.get('cdq'), v.get('colata')) for v in certificate.cdq_values or []}
    added = sorted({str(v['cdq']) for v in current if (v.get('cdq'), v.get('colata')) not in old_keys})
    return ('Il materiale dell’OL è cambiato rispetto al Word preparato. '
            + (f'Certificati fornitori aggiunti o con colata diversa: {", ".join(added)}. ' if added else '')
            + 'Verifica il materiale in Incoming, poi aggiorna il Word prima di preparare il PDF.')


def pending_message(db, certificate, *, sources=None):
    if certificate is None or certificate.status == 'pdf_final':
        return None
    reference = declared(sources if sources is not None else sources_for(db, certificate.cod_odp, certificate.cod_f3))
    if reference is None or reference.id == certificate.id:
        return None
    if metadata(reference).get('revision') != metadata(certificate).get('revision'):
        return ('Il Word di riferimento è stato aggiornato. Questa copia deve essere aggiornata prima del PDF.'
                if certificate.word_source == 'ddt_reused' else
                'Il Word di riferimento è stato aggiornato. Questa copia è stata lavorata separatamente: verifica prima di sostituirla.')
    return None


def require_current_material(db, certificate):
    if certificate.status == 'pdf_final':
        return
    if material_changed(db, certificate):
        raise HTTPException(409, material_message(db, certificate))
    pending = pending_message(db, certificate)
    if pending:
        raise HTTPException(409, pending)


def decorate_detail(db, detail, certificate):
    from app.modules.quarta_taglio import ddt_word_reuse as reuse
    f3 = detail.header.get('codice_f3')
    sources = sources_for(db, detail.cod_odp, f3) if f3 else []
    reference, reason = choose(db, sources)
    source = reference or declared(sources) or certificate or (sources[0] if len(sources) == 1 else None)
    info = detail.word_info
    info.reference_reason = reason
    if certificate and certificate.storage_key_docx:
        try:
            info.current_word_file_hash = reuse.file_hash(certificate.storage_key_docx)
        except OSError:
            pass
    info.reference_conflict = reason == 'different_word_sources'
    info.reference_certificate_id = source.id if source else None
    if source:
        info.reference_number = source.certificate_number
        info.reference_download_url = reuse.service._serialize_word_info(source).download_url
        info.reference_detail_url = f'/quarta-taglio/{source.cod_odp}?certificateId={source.id}'
    info.is_reference = bool(certificate and reference and certificate.id == reference.id
                             and metadata(reference).get('kind') == 'reference')
    if source and source.storage_key_docx:
        try:
            info.reference_file_hash = reuse.file_hash(source.storage_key_docx)
        except OSError:
            pass
        info.material_changed = material_changed(db, source)
        if info.material_changed:
            info.reference_message = material_message(db, source)
    pending = pending_message(db, certificate)
    if pending:
        info.copy_update_required = True
        info.reference_message = pending
    if info.reference_conflict and not info.reference_message:
        info.reference_message = ('Sono presenti Word storici diversi. Apri il Word completo e confermalo '
                                  'come riferimento per i prossimi DDT e per l’ereditarietà.')
    if reason in MESSAGES and not info.reference_message:
        info.reference_message = MESSAGES[reason]
    if info.reference_message and reason:
        detail.display_status_label, detail.display_status_color = 'Word da verificare', 'yellow'
    if info.material_changed or pending:
        if certificate is None or certificate.status != 'pdf_final':
            detail.display_status_label, detail.display_status_color = 'Word da aggiornare', 'yellow'


def adopt(db, certificate, actor, expected_hash):
    from app.modules.quarta_taglio import service, ddt_word_reuse as reuse, word_standard
    if not service.is_quality_area_user(actor):
        raise HTTPException(403, 'Solo Qualità o IT possono aggiornare il riferimento Word.')
    service._lock_certificate_register_for_ol(db, cod_odp=certificate.cod_odp)
    db.refresh(certificate)
    if reuse.file_hash(certificate.storage_key_docx) != expected_hash:
        raise HTTPException(409, 'Il Word è cambiato: aggiorna la pagina e verifica il documento.')
    word_standard.require_current(db, certificate, for_reuse=True)
    if material_changed(db, certificate):
        raise HTTPException(409, material_message(db, certificate))
    publish(db, certificate, actor_id=actor.id, origin='explicit_adoption')
    db.commit()
    refresh_copies(db, certificate)
    return certificate


def replace_open_copy(db, certificate, actor, expected_hash):
    """User explicitly confirms replacing a manually worked OPEN shipment copy."""
    from app.modules.quarta_taglio import service, ddt_word_reuse as reuse
    from app.modules.quarta_taglio.ddt_context import resolve_saved_ddt
    if not service.is_quality_area_user(actor):
        raise HTTPException(403, 'Solo Qualità o IT possono aggiornare il Word.')
    service._lock_certificate_register_for_ol(db, cod_odp=certificate.cod_odp)
    db.refresh(certificate)
    service._ensure_certificate_word_is_editable(certificate)
    if reuse.file_hash(certificate.storage_key_docx) != expected_hash:
        raise HTTPException(409, 'Il Word è cambiato: aggiorna la pagina prima di sostituirlo.')
    reference = declared(sources_for(db, certificate.cod_odp, certificate.cod_f3))
    if reference is None or reference.id == certificate.id:
        raise HTTPException(409, 'Non è disponibile un altro Word di riferimento per questa lavorazione.')
    item = resolve_saved_ddt(db, cod_odp=certificate.cod_odp, certificate=certificate, lock=True)
    if item is None:
        raise HTTPException(409, 'Quota DDT non identificata: verifica il collegamento.')
    history = deepcopy(metadata(certificate).get('history', []))
    history.append(dict(origin='manual_copy_replacement', previous_key=certificate.storage_key_docx,
                        previous_hash=expected_hash, actor_id=actor.id,
                        published_at=datetime.now(timezone.utc).isoformat()))
    certificate.word_source = 'ddt_reused'
    certificate.word_reference = dict(kind='copy', revision=None, file_hash=expected_hash, history=history)
    created = []
    try:
        plan = reuse.plan_item(db, item)
        if plan['action'] != 'reuse':
            raise HTTPException(409, 'Aggiornamento non possibile: verificare Incoming, materiale, standard e versioni PDF.')
        reuse.apply_item(db, item, plan, created)
        db.commit()
    except Exception:
        db.rollback()
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return certificate


def refresh_copies(db, certificate):
    """Separate transactions after a successful explicit edit; same test/app bind."""
    from sqlalchemy.orm import sessionmaker
    from app.modules.quarta_taglio.ddt_word_reuse import sync_ddt_words
    return sync_ddt_words(session_factory=sessionmaker(bind=db.get_bind(), autoflush=False),
                          cod_odp=certificate.cod_odp, cod_f3=certificate.cod_f3)


def ensure_schema(connection):
    """Additive migration only: no selection/backfill, files, or application bootstrap."""
    schema = connection.get_execution_options().get('schema_translate_map', {}).get(None)
    table = Certificate.__tablename__
    inspector = inspect(connection)
    if not inspector.has_table(table, schema=schema):
        raise ValueError('certificate_table_required')
    if 'word_reference' in {c['name'] for c in inspector.get_columns(table, schema=schema)}:
        return False
    quote = connection.dialect.identifier_preparer
    qualified = (quote.quote_schema(schema) + '.' if schema else '') + quote.quote(table)
    connection.execute(text(f'ALTER TABLE {qualified} ADD COLUMN word_reference JSON'))
    return True
