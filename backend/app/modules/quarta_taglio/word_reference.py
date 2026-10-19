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
    source = reference or certificate or (sources[0] if len(sources) == 1 else None)
    info = detail.word_info
    if certificate and certificate.storage_key_docx:
        try:
            info.current_word_file_hash = reuse.file_hash(certificate.storage_key_docx)
        except OSError:
            pass
    info.reference_conflict = reason == 'different_word_sources'
    info.reference_certificate_id = source.id if source else None
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
