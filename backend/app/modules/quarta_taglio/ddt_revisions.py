"""Separate a proven row removal inside a *still visible* document from window expiry.

Runs only for transitions between complete snapshots. No inference of lineage from
timestamps, equal quantities or order numbers. No file/network I/O in the transaction.
"""
from collections import defaultdict
from decimal import Decimal
import secrets

from sqlalchemy import select

from app.modules.quarta_taglio.models import (DdtShipmentChange as Change, DdtWordRepair as Repair,
    QuartaTaglioDdtWorkItem as Item, QuartaTaglioFinalCertificate as Certificate,
    QuartaTaglioCertificatePdfVersion as Version)

REMOVED = 'ddt_row_withdrawn'
FIELDS = ('id_documento','id_riga_doc','rif_lotto_alfanum','cod_odp','cod_f3',
          'ddt_raw','cliente','ordine_cliente','conferma_ordine','quantita','certification_unit_key')


def snapshot_rows(items, *, include_absent=False):
    docs = defaultdict(dict)
    for item in items:
        if item.source_present or include_absent:
            data = {k: getattr(item,k) for k in FIELDS}
            data['quantita'] = str(Decimal(item.quantita).normalize()) if item.quantita is not None else None
            docs[item.id_documento][item.source_key] = dict(data, item_id=item.id)
    return docs


def family(row):
    return (row['cod_odp'], row['cod_f3'])


def printed(row, group):
    if not row:
        return None
    peers = [r for r in group.values() if family(r) == family(row)]
    qty = [r['quantita'] for r in peers]
    total = (sum(Decimal(v) for v in qty) if len(qty)>1 and None not in qty else None)
    return ([row[k] for k in FIELDS], len(qty)>1, total)


def apply_transitions(db, before, after, now):
    # Remember the last *observed* membership. Imported history cannot establish
    # that an entire document was ever seen together in a successful live read.
    for doc in before.keys() - after.keys():
        rows=list(before[doc].values())
        db.add(Change(document=doc,ddt=rows[0]['ddt_raw'] or doc,before=rows,after=[],
            withdrawals=[],delivery='outside_window',email_status='none',created_at=now))
    returning=list(after.keys() - before.keys())
    for offset in range(0,len(returning),300):
        for prior in db.scalars(select(Change).where(Change.document.in_(returning[offset:offset+300]),
                                                     Change.delivery=='outside_window')):
            doc=prior.document
            items={i.id:i.source_key for i in db.scalars(select(Item).where(Item.id_documento==doc))}
            if all(r['item_id'] in items for r in prior.before):
                before[doc]={items[r['item_id']]:r for r in prior.before}
            prior.delivery='returned'
    for doc in before.keys() & after.keys():  # never retire a whole missing DDT
        first, last = before[doc], after[doc]
        if first != last:
            record_change(db,doc,first,last,now)


def record_change(db, doc, first, last, now):
    current_ids = {r['item_id'] for r in last.values()}
    gone = [r for r in first.values() if r['item_id'] not in current_ids]
    for r in gone:
        db.get(Item,r['item_id']).source_review_reason = REMOVED
    # Match the certificate to its source facts, not its number (siblings share it).
    certificates = list(db.scalars(select(Certificate).where(
        Certificate.esolver_id_documento==doc).order_by(Certificate.id).with_for_update()
        .execution_options(populate_existing=True)))
    by_item = {r['item_id']: r for r in last.values()}
    affected, repairs, withdrawals = [], [], []
    for c in certificates:
        if (c.shipment_context or {}).get('retired'):
            continue
        pending=db.get(Repair,c.id)
        old = next((r for r in first.values() if bound(c,r) or pending and r['item_id']==pending.item_id),None)
        # Old records may predate the derived unit key. Only a unique exact
        # physical document, line, lot, OL and article is evidence of ownership.
        if not old and c.esolver_id_riga_doc and c.esolver_rif_lotto_alfanum and c.cod_odp and c.cod_f3:
            matches=[r for r in first.values() if
                     (r['id_riga_doc'],r['rif_lotto_alfanum'],*family(r))==
                     (c.esolver_id_riga_doc,c.esolver_rif_lotto_alfanum,c.cod_odp,c.cod_f3)]
            if len(matches)==1:
                old=matches[0]
        new = next((r for r in last.values() if bound(c,r)),None)
        if old is None and new is None:
            continue
        if old and not new:
            same = by_item.get(old['item_id'])
            if same and family(same)==family(old) and same['rif_lotto_alfanum']==old['rif_lotto_alfanum']:
                new = same  # same physical row; only its shipment fields changed
        if printed(old, first)==printed(new, last):
            # The printed total can stay identical while two *other* shares are
            # redistributed. An unchanged closed PDF is valid. An open Word's
            # shipment fingerprint, however, must advance or its PDF would be
            # blocked forever by require_current(), with no visible edit to make.
            if not (old and new and c.status=='draft' and c.storage_key_docx and c.shipment_context and
                    {k:r for k,r in first.items() if family(r)==family(old)} !=
                    {k:r for k,r in last.items() if family(r)==family(new)}):
                continue
        affected.append((c,old,new))
    if not gone and not affected:
        return
    for c,old,new in affected:
        # Keep original files/versions. Clearing the current pointer removes SQL/API
        # export; rotating the token also revokes a URL cached by eSolver.
        if c.status=='pdf_final' and c.storage_key_pdf:
            versions=list(db.scalars(select(Version).where(Version.certificate_id==c.id,Version.status=='active')))
            for v in versions:
                v.status='withdrawn'
                v.annulled_at=now
                v.annulment_reason='Dati spedizione modificati in eSolver'
            withdrawals.append(dict(id=c.id,ol=c.cod_odp,f3=c.cod_f3,numero=c.certificate_number,riga=c.esolver_id_riga_doc,
                pezzi=c.quantita,versions=[v.version for v in versions],file=c.pdf_file_name,
                storage_key=c.storage_key_pdf))
            c.storage_key_pdf=None
            c.download_token=secrets.token_urlsafe(32)
        pending = db.get(Repair,c.id)
        if new is None or not c.storage_key_docx and any(w['id']==c.id for w in withdrawals):
            # Frozen like a final cert: not editable, not downloadable as current.
            c.status='pdf_final'
            c.shipment_context=dict(c.shipment_context or {},retired=True,
                withdrawn_pdf=any(w['id']==c.id for w in withdrawals))
            if pending:
                db.delete(pending)
        elif c.storage_key_docx:
            c.status='draft'
            c.closed_at=None
            repairs.append((c,new,pending))
    event=Change(document=doc,ddt=next(iter(last.values()))['ddt_raw'] or doc,
        before=list(first.values()),after=list(last.values()),withdrawals=withdrawals,
        delivery='unknown' if withdrawals else 'none',email_status='pending' if withdrawals else 'none',created_at=now)
    db.add(event)
    db.flush()
    for c,new,pending in repairs:
        # Prefer a unique number actually published for this document AND family.
        numbers={cert.certificate_number for cert in certificates if
                 (cert.cod_odp,cert.cod_f3)==family(new) and cert.certificate_number and
                 (cert.status=='pdf_final' and cert.storage_key_pdf or
                  any(w['id']==cert.id for w in withdrawals))}
        repair=pending or Repair(certificate_id=c.id)
        repair.change_id,repair.item_id=event.id,new['item_id']
        if numbers:
            repair.number=next(iter(numbers)) if len(numbers)==1 else None
        repair.error='Numero del DDT ambiguo' if len(numbers)>1 else None
        # Make the current row navigable even if the uploaded Word lacks controls.
        # The job remains a hard publication fence until the FILE has been verified.
        c.unit_key=new['certification_unit_key']
        c.ddt=new['ddt_raw']
        c.ordine_cliente=new['ordine_cliente']
        c.quantita=float(new['quantita']) if new['quantita'] is not None else None
        c.shipment_context=dict(c.shipment_context or {},ddt_repair_pending=True)
        db.add(repair)
    return event


def guard(db,c):
    from fastapi import HTTPException
    if (c.shipment_context or {}).get('retired'):
        raise HTTPException(409,'Certificato ritirato: la riga DDT non è più attuale.')
    from app.core.config import settings
    if settings.ddt_revisions_enabled or (c.shipment_context or {}).get('ddt_repair_pending'):
        pending=db.get(Repair,c.id,populate_existing=True)
        if pending:
            raise HTTPException(409,pending.error or 'Aggiornamento dei campi di spedizione in corso. Riprova dopo l’aggiornamento.')
        if (c.shipment_context or {}).get('ddt_repair_pending'):
            raise HTTPException(409,'Correzione dei campi di spedizione non ancora verificata.')


def repair_word(db, task, created, *, verified_finished_description=None):
    from types import SimpleNamespace
    from app.modules.quarta_taglio import ddt_shipments as ship, ddt_word_reuse as reuse, service, word_reference as refs
    from app.modules.quarta_taglio.ddt_decisions import latest_decisions
    from app.modules.quarta_taglio.ddt_archive import archived_ids
    c=db.get(Certificate,task.certificate_id)
    service._lock_certificate_register_for_ol(db,cod_odp=c.cod_odp)
    item=db.get(Item,task.item_id,with_for_update=True,populate_existing=True)
    db.refresh(c,with_for_update=True)
    decision=latest_decisions(db,[item.id]).get(item.id) if item else None
    if (not item or item.source_review_reason or not item.ddt_date or item.quantita is None
        or item.id in archived_ids(db,[item]) or decision and decision.action in {'exclude','review'}
        or c.status!='draft' or c.storage_key_pdf or not c.storage_key_docx
        or (c.cod_odp,c.cod_f3,c.esolver_id_documento,c.esolver_id_riga_doc,c.esolver_rif_lotto_alfanum)
          !=(item.cod_odp,item.cod_f3,item.id_documento,item.id_riga_doc,item.rif_lotto_alfanum)):
        raise ValueError('Identità della riga o decisione Qualità da verificare')
    others=list(db.scalars(select(Certificate).where(Certificate.cod_odp==c.cod_odp,
        Certificate.cod_f3==c.cod_f3,Certificate.esolver_id_documento==item.id_documento)))
    authoritative={p.certificate_number for p in others if p.status=='pdf_final' and p.certificate_number
                   and (p.storage_key_pdf or (p.shipment_context or {}).get('withdrawn_pdf'))}
    if len(authoritative)>1 or task.number and authoritative and task.number not in authoritative:
        raise ValueError('Numero del DDT ambiguo')
    n=task.number or next(iter(authoritative),None) or ship.number_plan(db,item,c,c)['number']
    if (not n or db.scalar(select(Certificate.id).where(Certificate.certificate_number==n,
        ((Certificate.cod_odp!=c.cod_odp)|(Certificate.cod_f3!=c.cod_f3)|
         (Certificate.esolver_id_documento.is_not(None)&(Certificate.esolver_id_documento!=item.id_documento)))).limit(1))):
        raise ValueError('Numero già assegnato a un’altra spedizione')
    pinned=refs.before_automatic(c)
    base_key=service._certificate_manual_base_docx_storage_key(c)
    base_path=service._certificate_storage_path(base_key)
    controls,_=reuse.word_facts(c.storage_key_docx)
    values=reuse.shipment_values(item,c,controls,db=db)
    values['CERT_NUMBER']=n
    # Only the one-off recovery supplies this value after independently checking
    # CertiOL, the approved Word and both full packages. Never replace user text.
    if verified_finished_description is not None:
        if (not verified_finished_description or controls.get('FINISHED_DESCRIPTION') != ''
            or 'QUANTITY_FINISHED' not in values or base_path.is_file()):
            raise ValueError('Descrizione del finito non recuperabile automaticamente')
        values['FINISHED_DESCRIPTION']=verified_finished_description
    _,technical=reuse.word_facts(c.storage_key_docx,peer_fields=set(values))
    if any(controls.get(k)!=str(v) for k,v in values.items()):
        key=service._certificate_docx_storage_key(c.cod_odp)
        path=service._certificate_storage_path(key)
        created.append(path)
        service.update_docx_content_controls(service._certificate_storage_path(c.storage_key_docx),
            path,values,normalize_layout=False)
        actual,preserved=reuse.word_facts(key,peer_fields=set(values))
        if preserved!=technical or any(actual.get(k)!=str(v) for k,v in values.items()):
            raise ValueError('Il Word non conserva integralmente i contenuti originali')
        c.storage_key_docx=key
    refs.after_automatic(c,pinned,origin='ddt_revision')
    if n != c.certificate_number:
        # Extra pages follow a NUMBER (shared by siblings); PDF attachments follow an ID.
        # Never move the older shipment's page, nor replace a different explicit page.
        import shutil
        from app.modules.quarta_taglio.models import QuartaTaglioCertificateExtraPages as Pages
        prior=service._additional_pages_for_certificate(db,certificate_number=c.certificate_number)
        destination=service._additional_pages_for_certificate(db,certificate_number=n)
        if prior:
            if prior.cod_odp!=c.cod_odp or destination and (destination.cod_odp!=c.cod_odp or
                reuse.file_hash(prior.storage_key_docx)!=reuse.file_hash(destination.storage_key_docx)):
                raise ValueError('Seconde pagine diverse per i due numeri: originali conservati')
            if not destination:
                key=service._certificate_extra_pages_storage_key(n,original_name=prior.original_filename or 'pagina.docx')
                dest=service._certificate_storage_path(key)
                dest.parent.mkdir(parents=True,exist_ok=True)
                created.append(dest)
                shutil.copy2(service._certificate_storage_path(prior.storage_key_docx),dest)
                db.add(Pages(certificate_number=n,cod_odp=c.cod_odp,storage_key_docx=key,
                    original_filename=prior.original_filename,uploaded_by_user_id=prior.uploaded_by_user_id))
        for attachment in service._pdf_attachments_for_certificate(db,certificate=c):
            attachment.certificate_number=n
    c.certificate_number=n
    c.draft_number=n
    if base_path.is_file() and base_key!=service._certificate_manual_base_docx_storage_key(c):
        new_base=service._certificate_manual_base_docx_storage_key(c)
        dest=service._certificate_storage_path(new_base)
        if dest.exists():
            raise ValueError('Base manuale di destinazione già presente')
        _,old_base=reuse.word_facts(base_key,peer_fields=set(values))
        created.append(dest)
        service.update_docx_content_controls(base_path,dest,values,normalize_layout=False)
        base_controls,check_base=reuse.word_facts(new_base,peer_fields=set(values))
        if old_base!=check_base or any(base_controls.get(k)!=str(v) for k,v in values.items()):
            raise ValueError('Base Word manuale non verificabile')
    c.ddt=item.ddt_raw
    c.unit_key=item.certification_unit_key
    c.quantita=float(item.quantita)
    c.ordine_cliente=item.ordine_cliente
    c.cdo_lega=item.conferma_ordine or item.ordine_cliente
    c.fornitore_cliente=item.cliente
    c.cert_date=service._certificate_datetime_from_ddt(item.ddt_raw)
    base=ship.base_number(SimpleNamespace(certificate_number=n))
    seq=int(n.split('/')[0].split('_')[3]) if len(n.split('/')[0].split('_'))==4 else 0
    ship.record(db,c,item,dict(base_number=base,sequence=seq,number=n))
    db.delete(task)


def process_repairs(factory):
    from fastapi import HTTPException
    from app.modules.quarta_taglio.ddt_snapshot import _LOCK_NAMESPACE,_LOCK_ID
    from sqlalchemy import text
    with factory() as db:
        ids=list(db.scalars(select(Repair.certificate_id).order_by(Repair.certificate_id)))
    for cid in ids:
        created=[]
        with factory() as db:
            task=None
            try:
                if db.get_bind().dialect.name=='postgresql' and not db.scalar(text(
                    'SELECT pg_try_advisory_xact_lock_shared(:n,:i)'),dict(n=_LOCK_NAMESPACE,i=_LOCK_ID)):
                    return
                task=db.scalar(select(Repair).where(Repair.certificate_id==cid).with_for_update(skip_locked=True))
                if task:
                    try:
                        with db.begin_nested():
                            repair_word(db,task,created)
                            db.flush()
                    except Exception as exc:
                        for path in created:
                            path.unlink(missing_ok=True)
                        task.error=('Aggiornamento Word non completato: ' +
                            (str(exc.detail) if isinstance(exc,HTTPException) else
                             str(exc) if isinstance(exc,ValueError) else 'file o campi non verificabili') +
                            '. Il Word originale è conservato; verificare i campi di spedizione.')
                    db.commit()
            except Exception:
                db.rollback()
                # On uncertain commit outcome never remove a possibly published file.
                from app.core.logs.service import log_service
                log_service.record('ddt_revision','Aggiornamento Word rinviato: riprovare al prossimo ciclo.')


def bound(c,r):
    return bool(r['certification_unit_key'] and c.unit_key==r['certification_unit_key'] and
                c.cod_odp==r['cod_odp'] and c.cod_f3==r['cod_f3'] and
                c.esolver_id_riga_doc==r['id_riga_doc'] and
                c.esolver_rif_lotto_alfanum==r['rif_lotto_alfanum'])
