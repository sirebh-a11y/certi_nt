"""Explicit technical-page refresh retaining the existing appended body/relations."""
import secrets

from docx import Document
from docxcompose.composer import Composer
from fastapi import HTTPException

from app.modules.quarta_taglio import service, word_reference, word_standard
from app.modules.quarta_taglio.certificate_docx import normalize_certificate_docx_layout
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as Certificate, QuartaTaglioCertificatePdfAttachment as Attachment


def preserve_additional_body(source, generated):
    """Keep all body content AFTER the generated mechanical table, including images.

    Composer imports relationships/styles, unlike raw XML insertion. Recognize
    the technical boundary strictly; an unknown custom layout is not discarded.
    """
    from docx.table import Table
    old = Document(source)
    children = list(old.element.body)
    boundary = None
    for index, node in enumerate(children):
        if node.tag.endswith('}tbl'):
            table = Table(node, old._body)
            labels = [r.cells[0].text.strip() for r in table.rows]
            if len(labels) == 3 and labels[1:] == ['Min.', 'Spec.']:
                boundary = index
                break
        elif node.tag.endswith('}p') and ''.join(node.itertext()).find('No mechanical properties available.') >= 0:
            boundary = index
            break
    if boundary is None:
        raise HTTPException(409, 'La pagina tecnica del Word ha un formato personalizzato non riconosciuto. '
                            'Conserva il documento e verifica la struttura prima di aggiornarlo.')
    for node in children[:boundary + 1]:
        old.element.body.remove(node)
    # Empty old tail: nothing to append. Keep section properties on the fresh document.
    if any(n.tag.rsplit('}', 1)[-1] != 'sectPr' for n in old.element.body):
        composer = Composer(Document(generated))
        composer.append(old)
        composer.save(generated)
    normalize_certificate_docx_layout(generated)


def update_material(db, source, actor, expected_hash, *, force_non_conforming=False):
    from app.modules.quarta_taglio.ddt_word_reuse import file_hash
    if not service.is_quality_area_user(actor):
        raise HTTPException(403, 'Solo Qualità o IT possono aggiornare il Word.')
    service._lock_certificate_register_for_ol(db, cod_odp=source.cod_odp)
    db.refresh(source)
    if file_hash(source.storage_key_docx) != expected_hash:
        raise HTTPException(409, 'Il Word è cambiato: aggiorna la pagina prima di aggiornarlo.')
    # Readiness/conformity are evaluated on ALL current materials of the OL.
    detail = service.get_quarta_taglio_detail(db, cod_odp=source.cod_odp, certificate_id=source.id)
    # A generic detail refresh may commit; reacquire the OL lock before editing.
    service._lock_certificate_register_for_ol(db, cod_odp=source.cod_odp)
    db.refresh(source)
    if file_hash(source.storage_key_docx) != expected_hash:
        raise HTTPException(409, 'Il Word è cambiato durante la verifica: aggiorna la pagina.')
    materials_before = word_reference.current_materials(db, source.cod_odp)
    service._ensure_word_draft_can_be_created(detail)
    if detail.conformity_issues and not force_non_conforming:
        raise HTTPException(409, 'Sono presenti valori fuori standard: conferma esplicitamente l’aggiornamento non conforme.')
    selected_standard = word_standard.snapshot(db, source.cod_odp)
    key = service._certificate_docx_storage_key(source.cod_odp)
    output = service._certificate_storage_path(key)
    target = source
    try:
        service.build_forgialluminio_draft_docx(detail=detail, output_path=output,
            draft_number=source.certificate_number, certified_by=actor,
            quality_manager=service._select_quality_manager(db))
        preserve_additional_body(service._certificate_storage_path(source.storage_key_docx), output)
        word_standard.require_unchanged(db, source.cod_odp, selected_standard)
        if word_reference.current_materials(db, source.cod_odp) != materials_before:
            raise HTTPException(409, 'Il materiale dell’OL è cambiato durante l’aggiornamento: riprova.')
        if source.status == 'pdf_final' or source.storage_key_pdf:
            # A new reference is independent of the old closed shipment/PDF.
            target = Certificate(cod_odp=source.cod_odp, cod_f3=source.cod_f3,
                certificate_number=source.certificate_number, draft_number=source.certificate_number,
                status='draft', created_by_user_id=actor.id)
            db.add(target)
            db.flush()
            for a in service._pdf_attachments_for_certificate(db, certificate=source):
                db.add(Attachment(certificate_id=target.id, certificate_number=target.certificate_number,
                    cod_odp=target.cod_odp, storage_key_pdf=a.storage_key_pdf,
                    original_filename=a.original_filename, sort_order=a.sort_order,
                    uploaded_by_user_id=a.uploaded_by_user_id))
        target.cdq_values = service._cdq_values_from_detail(detail)
        target.cdq_signature = service._cdq_signature_from_detail(detail)
        target.cdq_key = service._cdq_key_from_detail(detail)
        target.word_standard_snapshot = word_standard.provenance(selected_standard, 'material_updated')
        target.storage_key_docx, target.download_token = key, secrets.token_urlsafe(32)
        target.certified_by_user_id = actor.id
        manager = service._select_quality_manager(db)
        target.quality_manager_user_id = manager.id if manager else None
        target.pdf_attachments_initialized = True
        service._apply_certificate_conformity(target, detail)
        service._apply_word_file_state(target, output, source='user_uploaded', original_filename=source.word_original_filename)
        word_reference.publish(db, target, actor_id=actor.id, origin='material_updated')
        db.commit()
    except Exception:
        db.rollback()
        output.unlink(missing_ok=True)
        raise
    word_reference.refresh_copies(db, target)
    return target
