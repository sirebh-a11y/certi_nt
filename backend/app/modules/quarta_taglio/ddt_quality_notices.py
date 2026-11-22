"""Persistent internal Quality notices. No automatic communication to customers."""
from dataclasses import replace
from decimal import Decimal
from smtplib import SMTPRecipientsRefused
from sqlalchemy import select
from app.core.config import settings
from app.core.email.schemas import NotificationEmail
from app.core.email.service import email_service
from app.core.email.settings_service import get_effective_email_settings
from app.modules.quarta_taglio.ddt_revisions import Certificate, Change, Item, Version, REMOVED, family


def current_rows(db, ev):
    groups={(w['ol'],w['f3']) for w in ev.withdrawals}
    before={r['item_id']: r for r in ev.before}
    changed={r['item_id'] for r in ev.after if before.get(r['item_id'])!=r}
    return [i for i in db.scalars(select(Item).where(Item.id_documento==ev.document,
        Item.source_review_reason.is_distinct_from(REMOVED)).order_by(Item.id))
        if (i.cod_odp,i.cod_f3) in groups or i.id in changed]


def work_finished(db, rows):
    from app.modules.quarta_taglio.ddt_context import exact_certificate, quantity_matches
    from app.modules.quarta_taglio.ddt_decisions import latest_decisions, exclusion_valid
    decisions=latest_decisions(db,[i.id for i in rows])
    for i in rows:
        if decisions.get(i.id) and exclusion_valid(i, decisions[i.id]):
            continue
        candidates=db.scalars(select(Certificate).join(Version, Version.certificate_id==Certificate.id).where(
            Certificate.unit_key==i.certification_unit_key, Certificate.status=='pdf_final',
            Certificate.storage_key_pdf.is_not(None),Version.status=='active',Version.annulled_at.is_(None)))
        if not any(exact_certificate(i,c) and quantity_matches(i,c) for c in candidates):
            return False
    return True


def quality_cases(db):
    if not settings.ddt_revisions_enabled:
        return []
    result=[]
    for ev in db.scalars(select(Change).where(Change.delivery.in_(['unknown','sent','customer_informed','not_sent'])).order_by(Change.id.desc())):
        rows=current_rows(db,ev)
        if ev.delivery in {'customer_informed','not_sent'} and work_finished(db,rows):
            continue
        result.append(dict(id=ev.id,ddt=ev.ddt,delivery=ev.delivery,email_status=ev.email_status,
            previous=[{k:w[k] for k in ('id','numero','riga','pezzi','ol')} for w in ev.withdrawals],
            current=[dict(id=i.id,ol=i.cod_odp,riga=i.id_riga_doc,pezzi=float(i.quantita) if i.quantita is not None else None,
                ordine=i.ordine_cliente) for i in rows]))
    return result


def dispatch_emails(factory):
    with factory() as db:
        for case in db.scalars(select(Change).where(Change.delivery.in_(['customer_informed','not_sent'])).with_for_update(skip_locked=True)):
            if work_finished(db,current_rows(db,case)):
                case.delivery='done_'+case.delivery
        db.commit()
    if not settings.ddt_quality_email:
        return  # Keep pending, never send to an invented address.
    with factory() as db:
        ids=list(db.scalars(select(Change.id).where(Change.email_status=='pending')))
    for cid in ids:
        with factory() as db:
            ev=db.scalar(select(Change).where(Change.id==cid,Change.email_status=='pending').with_for_update(skip_locked=True))
            if not ev:
                continue
            previous='; '.join(f"{w['numero']} (riga {w['riga']}, {w['pezzi']} pezzi)" for w in ev.withdrawals)
            groups={(w['ol'],w['f3']) for w in ev.withdrawals}
            before={r['item_id']:r for r in ev.before}
            current='; '.join(f"riga {r['id_riga_doc']}: {format(Decimal(r['quantita']),'f') if r['quantita'] else '?'} pezzi, ordine {r['ordine_cliente'] or '-'}"
                for r in ev.after if family(r) in groups or before.get(r['item_id'])!=r) or 'nessuna per la precedente lavorazione'
            mail=NotificationEmail(to_email=settings.ddt_quality_email,subject=f'CERTI – DDT {ev.ddt} modificato: non inviare il PDF precedente',
                body=f'PDF ritirato: {previous}.\nRighe alla rilevazione: {current}.\nVerificare con Amministrazione se il PDF precedente è stato inviato; in tal caso avvisare il cliente. Registrare l’esito in CERTI, DDT da certificare.')
            config=replace(get_effective_email_settings(db),mail_always_cc_email=None)
            ev.email_status='verify'
            db.commit()  # Claim before SMTP: never silently send twice on an uncertain receipt.
            try:
                email_service._send_with_config(mail,config,timeout=10)
            except (ConnectionRefusedError, SMTPRecipientsRefused):
                ev.email_status='pending'
            except Exception:
                continue  # 'verify' remains visible, including after process restart.
            else:
                ev.email_status='sent'
            db.commit()
