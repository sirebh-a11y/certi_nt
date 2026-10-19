"""Local shipment facts; no remote reads, historical renumbering or PDF writes.

Number allocation is called inside the existing per-OL advisory transaction
lock. Each row stores its allocation, independent of the reusable Word version.
Totals include physical shares, even if hidden/excluded from the work queue.
"""
import hashlib
import json
import re
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import inspect, select, text

from app.modules.quarta_taglio.models import QuartaTaglioDdtWorkItem as Item, QuartaTaglioFinalCertificate as Certificate
from app.modules.quarta_taglio.ddt_decisions import source_revision

MESSAGE = 'Le righe o il totale del DDT sono cambiati: aggiornare il Word prima di generare il PDF.'


def base_number(certificate):
    context = getattr(certificate, 'shipment_context', None) or {}
    number = str(getattr(certificate, 'certificate_number', None) or '')
    # Only the NEW fourth segment is shipment sequence; old OL/F3 segments stay.
    return context.get('base_number') or re.sub(r'^(\d+_\d+_\d+)_\d+(/\d{2})$', r'\1\2', number)


def group_key(item):
    return [item.cod_odp, item.cod_f3, item.id_documento]


def facts(db, item):
    if not all(group_key(item)) or not item.ddt_raw:
        raise HTTPException(409, 'Identità DDT incompleta: totale non calcolabile.')
    rows = list(db.scalars(select(Item).where(Item.cod_odp == item.cod_odp,
        Item.cod_f3 == item.cod_f3, Item.id_documento == item.id_documento).order_by(Item.source_key)
        .execution_options(populate_existing=True)))
    if not rows or item.id not in {r.id for r in rows}:
        raise HTTPException(409, 'Righe DDT non disponibili: totale non calcolabile.')
    total = Decimal(0)
    physical = set()
    for row in rows:
        physical_key = (row.id_riga_doc, row.rif_lotto_alfanum)
        if (not row.id_riga_doc or physical_key in physical or row.source_review_reason
                or row.ddt_raw != item.ddt_raw or (row.quantita is None and len(rows) > 1)):
            raise HTTPException(409, 'Righe DDT ambigue o incomplete: verificare il totale spedito.')
        physical.add(physical_key)
        if row.quantita is None:
            continue  # A preliminary single-share Word may still have no quantity.
        quantity = Decimal(str(row.quantita))
        if not quantity.is_finite() or quantity < 0:
            raise HTTPException(409, 'Quantità DDT non valida: verificare il totale spedito.')
        total += quantity
    fingerprint = hashlib.sha256(json.dumps([(r.source_key, source_revision(r)) for r in rows]).encode()).hexdigest()
    return dict(group=group_key(item), revision=fingerprint,
                total=format(total, 'f') if item.quantita is not None else None, count=len(rows))


def quantity_text(db, item, group=None):
    group = group or facts(db, item)
    if item.quantita is None:
        return ''
    def number(value):
        return format(Decimal(str(value)), 'f').rstrip('0').rstrip('.') if '.' in format(Decimal(str(value)), 'f') else format(Decimal(str(value)), 'f')
    own = number(item.quantita)
    return f"{own} of {number(group['total'])}" if group['count'] > 1 else own


def item_for_certificate(db, certificate):
    if not certificate.unit_key:
        return None
    items = list(db.scalars(select(Item).where(Item.certification_unit_key == certificate.unit_key,
                                              Item.cod_odp == certificate.cod_odp)))
    if len(items) > 1:
        raise HTTPException(409, 'Più quote DDT per il certificato: verifica richiesta.')
    return items[0] if items else None


def number_plan(db, item, source, target=None):
    """Read-only allocation preview; writers replan under the same OL lock."""
    base = base_number(source)
    if not re.fullmatch(r'\d+_\d+_\d+/\d{2}', base):
        raise HTTPException(409, 'Formato numero storico da verificare prima di numerare nuovi DDT.')
    certificates = list(db.scalars(select(Certificate).where(Certificate.cod_odp == item.cod_odp,
                                                              Certificate.cod_f3 == item.cod_f3)))
    peers = [c for c in certificates if c.esolver_id_documento == item.id_documento and c.certificate_number]
    peer_numbers = {c.certificate_number for c in peers}
    def checked(allocation):
        owner = db.scalar(select(Certificate.id).where(
            Certificate.certificate_number == allocation['number'],
            (Certificate.cod_odp != item.cod_odp) | (Certificate.cod_f3 != item.cod_f3)).limit(1))
        if owner is not None:
            raise HTTPException(409, 'Numero già usato da un altro OL/lavorazione: verifica richiesta.')
        return allocation
    if len(peer_numbers) > 1:
        raise HTTPException(409, 'Numeri diversi per lo stesso DDT: verifica richiesta.')
    # Never change an already assigned number (including an existing open Word).
    assigned = target.certificate_number if target is not None and target.certificate_number else next(iter(peer_numbers), None)
    if assigned:
        if peer_numbers and assigned not in peer_numbers:
            raise HTTPException(409, 'Numero del certificato diverso dalle altre righe DDT.')
        chosen_base = base_number(next((c for c in peers if c.certificate_number == assigned), target) or source)
        suffix = re.fullmatch(re.escape(chosen_base.rsplit('/',1)[0]) + r'_(\d+)/\d{2}', assigned)
        return checked(dict(base_number=chosen_base, sequence=int(suffix[1]) if suffix else 0, number=assigned))
    related = [c for c in certificates if c.certificate_number and base_number(c) == base]
    used = {c.certificate_number for c in related}
    has_previous = any(c.ddt or c.esolver_id_documento for c in related)
    sequence = 0
    if has_previous:
        sequence = 1
        prefix, year = base.rsplit('/',1)
        for c in related:
            match = re.fullmatch(re.escape(prefix) + r'_(\d+)/' + year, c.certificate_number)
            if match:
                sequence = max(sequence, int(match[1]) + 1)
    number = base if sequence == 0 else base.replace('/', f'_{sequence:02d}/')
    if number in used and sequence:
        raise HTTPException(409, 'Progressivo DDT già assegnato: aggiornare la vista.')
    return checked(dict(base_number=base, sequence=sequence, number=number))


def record(db, certificate, item, allocation=None):
    group = facts(db, item)
    allocation = allocation or number_plan(db, item, certificate, certificate)
    certificate.shipment_context = dict(version=1, **allocation, **group)


def prepare(db, certificate, item, candidate, *, explicit=False):
    if item is None or certificate.status == 'pdf_final':
        return candidate
    # Existing Word numbers are not migrated on ordinary page reads.
    if certificate.storage_key_docx and not certificate.shipment_context and not explicit:
        return candidate
    source = SimpleNamespace(certificate_number=candidate, shipment_context=certificate.shipment_context)
    allocation = number_plan(db, item, source, certificate)
    record(db, certificate, item, allocation)
    return allocation['number']


def require_current(db, certificate):
    if not getattr(certificate, 'shipment_context', None) or certificate.status == 'pdf_final':
        return
    item = item_for_certificate(db, certificate)
    if item is None or facts(db, item)['revision'] != certificate.shipment_context.get('revision'):
        raise HTTPException(409, MESSAGE)


def lock_snapshot_for_pdf(db, certificate):
    """Short shared lock against snapshot commit, not held for LO conversion.

    Non-blocking also avoids lock-order inversion with old callers already
    holding one share. A busy snapshot is retried, never interrupted.
    """
    if not getattr(certificate, 'shipment_context', None) or db.get_bind().dialect.name != 'postgresql':
        return
    from app.modules.quarta_taglio.ddt_snapshot import _LOCK_NAMESPACE, _LOCK_ID
    if not db.scalar(text('SELECT pg_try_advisory_xact_lock_shared(:namespace,:key)'),
                     dict(namespace=_LOCK_NAMESPACE,key=_LOCK_ID)):
        raise HTTPException(409, 'Aggiornamento DDT in corso: riprovare la generazione PDF tra pochi istanti.')


def queue_revision(db, item):
    group = facts(db, item)
    own = source_revision(item)
    return hashlib.sha256((own + group['revision']).encode()).hexdigest() if group['count'] > 1 else own


def ensure_schema(connection):
    schema = connection.get_execution_options().get('schema_translate_map', {}).get(None)
    inspector = inspect(connection)
    if not inspector.has_table(Certificate.__tablename__, schema=schema):
        raise ValueError('certificate_table_required')
    if 'shipment_context' in {c['name'] for c in inspector.get_columns(Certificate.__tablename__, schema=schema)}:
        return False
    quote = connection.dialect.identifier_preparer
    table = (quote.quote_schema(schema) + '.' if schema else '') + quote.quote(Certificate.__tablename__)
    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN shipment_context JSON'))
    return True


def preview_legacy(db):
    """Pre-deploy SELECT only, also BEFORE the new column exists. No file I/O."""
    from collections import defaultdict
    columns = [getattr(Certificate, name) for name in ('id','cod_odp','cod_f3',
        'esolver_id_documento','ddt','certificate_number','status','storage_key_docx')]
    rows = list(db.execute(select(*columns)).mappings())
    groups = defaultdict(list)
    for row in rows:
        if row['certificate_number']:
            groups[(row['cod_odp'], row['cod_f3'], row['certificate_number'])].append(row)
    return dict(certificates=len(rows), closed=sum(r['status']=='pdf_final' for r in rows),
        open_words=[r['id'] for r in rows if r['status']!='pdf_final' and r['storage_key_docx']],
        historical_same_number_multiple_ddt=[dict(ol=key[0],f3=key[1],number=key[2],
            ids=[r['id'] for r in group]) for key,group in groups.items()
            if len({r['esolver_id_documento'] or r['ddt'] for r in group if r['ddt']})>1],
        proposed_historical_renumbering=0)
