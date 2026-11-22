"""Persistent internal Quality notices. No automatic communication to customers."""
from dataclasses import replace
from decimal import Decimal
from sqlalchemy import or_, select
from app.core.config import settings
from app.core.email.schemas import NotificationEmail
from app.core.email.service import EmailNotSubmitted, email_service
from app.core.email.settings_service import get_effective_email_settings
from app.modules.quarta_taglio.ddt_revisions import Certificate, Change, Item, Version, REMOVED, family


ACTIVE = ('unknown', 'sent', 'not_sent', 'customer_informed')  # Last value: legacy only.
FOLLOW_PDFS = ('not_sent', 'customer_informed')
UNSENT = ('pending', 'retry')
CLOSED_NOTICE = 'sent_notice_closed'  # Old PDF reported sent; no assertion about contacting the customer.


def withdrawn_families(ev):
    return {(w['ol'], w['f3']) for w in ev.withdrawals}


def current_rows(db, ev):
    groups=withdrawn_families(ev)
    return [i for i in db.scalars(select(Item).where(Item.id_documento==ev.document,
        Item.source_review_reason.is_distinct_from(REMOVED)).order_by(Item.id))
        if (i.cod_odp,i.cod_f3) in groups]


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
    for ev in db.scalars(select(Change).where(Change.delivery.in_(ACTIVE)).order_by(Change.id.desc())):
        rows=current_rows(db,ev)
        if ev.delivery in FOLLOW_PDFS and work_finished(db,rows):
            continue
        result.append(dict(id=ev.id,ddt=ev.ddt,delivery=ev.delivery,email_status=ev.email_status,
            previous=[{k:w[k] for k in ('id','numero','riga','pezzi','ol')} for w in ev.withdrawals],
            current=[dict(id=i.id,ol=i.cod_odp,riga=i.id_riga_doc,pezzi=float(i.quantita) if i.quantita is not None else None,
                ordine=i.ordine_cliente) for i in rows]))
    return result


def notice_active(db, ev):
    """Called under the change's row lock, never on a read-only queue request."""
    if ev.delivery in FOLLOW_PDFS and work_finished(db, current_rows(db, ev)):
        ev.delivery = 'done_' + ev.delivery
    return ev.delivery in ACTIVE


def quality_email(ev):
    groups = withdrawn_families(ev)
    previous = '; '.join(f"{w['numero']} (riga {w['riga']}, {w['pezzi']} pezzi)" for w in ev.withdrawals)
    current = '; '.join(
        f"riga {r['id_riga_doc']}: {format(Decimal(r['quantita']),'f') if r['quantita'] else '?'} pezzi, ordine {r['ordine_cliente'] or '-'}"
        for r in ev.after if family(r) in groups
    ) or 'nessuna per la precedente lavorazione'
    action = {
        'unknown': 'Verifica con Amministrazione se il PDF ritirato è già stato inviato al cliente.',
        'sent': 'Il vecchio PDF è già stato inviato. Concorda con Amministrazione come avvisare il cliente e sostituire il documento.',
        'not_sent': 'È già registrato che il vecchio PDF non è stato inviato. Completa i PDF delle righe attuali.',
        'customer_informed': 'Completa i PDF delle righe attuali.',
    }[ev.delivery]
    return NotificationEmail(to_email=settings.ddt_quality_email,
        subject=f'CERTI – DDT {ev.ddt} modificato: non inviare il PDF precedente',
        body=f'PDF ritirato: {previous}.\nRighe alla rilevazione: {current}.\n{action}\nApri DDT da certificare in CERTI.')


def dispatch_emails(factory):
    with factory() as db:
        ids = list(db.scalars(select(Change.id).where(or_(
            Change.email_status.in_(UNSENT), Change.delivery.in_(FOLLOW_PDFS))).order_by(Change.id)))
    for cid in ids:
        with factory.begin() as db:
            ev = db.get(Change, cid, with_for_update={'skip_locked': True})
            if not ev:
                continue
            if not notice_active(db, ev):
                if ev.email_status in UNSENT:
                    ev.email_status = 'not_needed'
                continue
            if ev.email_status not in UNSENT or not settings.ddt_quality_email:
                continue
            ev.email_status = 'verify'  # Durable claim; a crash may not trigger a duplicate.
        with factory.begin() as db:
            # Re-read after the claim: a user may already have closed the notice.
            # Serialize this one bounded SMTP attempt with closure of THIS event only.
            ev = db.get(Change, cid, with_for_update=True)
            if not ev or ev.email_status != 'verify':
                continue
            if not notice_active(db, ev):
                ev.email_status = 'not_needed'  # Our claim; SMTP has not started.
                continue
            try:
                mail = quality_email(ev)
                config = replace(get_effective_email_settings(db), mail_always_cc_email=None)
            except Exception:
                # Also covers an unreadable stored SMTP credential. No connection
                # has been attempted yet; do not mark this case as possibly sent.
                ev.email_status = 'retry'
                continue
            try:
                email_service._send_with_config(mail, config, timeout=10, track_delivery=True)
            except EmailNotSubmitted:
                ev.email_status = 'retry'
            except Exception:
                continue  # Uncertain after submission. Keep 'verify', including on restart.
            else:
                ev.email_status = 'sent'
