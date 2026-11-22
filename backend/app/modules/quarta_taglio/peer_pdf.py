"""A worked Word belongs to its physical share, not to the last sibling edited.

Read-only exception to reference freshness for PDF publication only. Never
select a source, update a Word, or transfer consent to a different revision.
"""
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.quarta_taglio import ddt_shipments as shipments
from app.modules.quarta_taglio import ddt_word_reuse as reuse, word_standard
from app.modules.quarta_taglio.ddt_context import certificate_for_saved_ddt, resolve_saved_ddt
from app.modules.quarta_taglio.ddt_decisions import latest_decisions
from app.modules.quarta_taglio.models import QuartaTaglioDdtWorkItem as Item


QUESTION = 'Il Word di questa riga è diverso dal riferimento (es. seconda pagina). Vuoi generare il PDF con questo Word?'


@dataclass(frozen=True)
class PeerPdf:
    token: str | None  # None: only verified shipment fields differ.


def evaluate(db, target, reference):
    from app.modules.quarta_taglio import word_reference as refs
    pair = (target, reference)
    if (not target.esolver_id_documento or not target.esolver_id_riga_doc
            or not reference.esolver_id_riga_doc or target.esolver_id_riga_doc == reference.esolver_id_riga_doc
            or not target.certificate_number or any(getattr(target, k) != getattr(reference, k) for k in
                ('cod_odp', 'cod_f3', 'ddt', 'esolver_id_documento', 'certificate_number'))
            or any(refs.metadata(c).get('kind') != 'reference' or not c.shipment_context for c in pair)):
        return None
    try:
        rows = [resolve_saved_ddt(db, cod_odp=c.cod_odp, certificate=c) for c in pair]
        if any(r is None or certificate_for_saved_ddt(db, r) is not c for r, c in zip(rows, pair)):
            return None
        decision = latest_decisions(db, [rows[0].id]).get(rows[0].id)
        if decision and decision.action in {'exclude', 'review'}:
            return None
        group = shipments.facts(db, rows[0])
        if shipments.number_plan(db, rows[0], reference, target)['number'] != target.certificate_number:
            return None
        # A historical share mixed with a replacement is not proof of a split.
        if db.scalar(select(Item.id).where(Item.cod_odp == target.cod_odp, Item.cod_f3 == target.cod_f3,
                Item.id_documento == target.esolver_id_documento, Item.source_present.is_(False),
                Item.source_review_reason.is_distinct_from(shipments.REMOVED)).limit(1)):
            return None
        materials = refs.current_materials(db, target.cod_odp)
        fingerprints, pins, other_branches = [], [], []
        for c, row in zip(pair, rows):
            ctx = c.shipment_context
            if (ctx.get('group') != group['group'] or ctx.get('revision') != group['revision']
                    or ctx.get('number') != c.certificate_number or ctx.get('count') != group['count']
                    or Decimal(str(ctx.get('total'))) != Decimal(group['total'])
                    or not c.cdq_values or refs.material_changed(db, c, current=materials)
                    or word_standard.is_stale(c, db, for_reuse=True)
                    or reuse.service._certificate_conformity_status(c) != 'conforme'):
                return None
            facts = reuse.word_facts(c.storage_key_docx)
            if refs.integrity_reason(c, facts=facts):
                return None
            controls = facts[0]
            expected = reuse.shipment_values(row, c, controls, db=db)
            if (any(controls.get(key) != str(value) for key, value in expected.items())
                    or any((controls.get('DDT_' + b) or controls.get('QUANTITY_' + b))
                           and not controls.get('COD_F3_' + b) for b in ('RAW', 'FINISHED'))):
                return None
            # A different DDT/quantity in the other article column is not a
            # discretionary edit (e.g. an extra page); never approve it as one.
            other = 'FINISHED' if 'DDT_RAW' in expected else 'RAW'
            other_branches.append((other, *(controls.get(k + other, '') for k in
                                            ('COD_F3_', 'DDT_', 'QUANTITY_'))))
            observed, template = reuse.word_facts(c.storage_key_docx, peer_fields=set(expected))
            if observed != controls:
                return None
            attachments = [(a.original_filename, reuse.file_hash(a.storage_key_pdf))
                           for a in reuse.service._pdf_attachments_for_certificate(db, certificate=c)]
            fingerprints.append([template, attachments, c.certified_by_user_id, c.quality_manager_user_id])
            pins.append([c.id, refs.metadata(c)['revision'], fingerprints[-1]])
        if other_branches[0] != other_branches[1]:
            return None
        if fingerprints[0] == fingerprints[1]:
            return PeerPdf(None)
        return PeerPdf(reuse.digest([pins, group['revision'], [reuse.file_hash(c.storage_key_docx) for c in pair]]))
    except (HTTPException, OSError, ValueError, TypeError, KeyError, ArithmeticError,
            reuse.zipfile.BadZipFile, reuse.etree.XMLSyntaxError):
        return None  # Cannot prove both shares: keep the original block.
