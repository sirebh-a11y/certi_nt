"""One audited Beta document only. Preview is read-only. Never generate a PDF."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from app.core.config import settings
from app.core.database import SessionLocal
from app.startup import bootstrap as _models  # Register mappers, do NOT bootstrap.
from app.modules.quarta_taglio import ddt_revisions as rev, ddt_snapshot, ddt_word_reuse as reuse, word_reference, word_standard
from app.modules.quarta_taglio.ddt_recovery import alpha_database_identity
from app.modules.quarta_taglio.ddt_word_recovery import lock_inputs
from scripts.recover_ddt_alpha import check_backup

DOC, OL, F3, DDT = '5296723', 'OL2026001058', '520002360', '2866-20/11/2026'
NUMBER, BASE = '7028_00_60_01/26', '7028_00_60/26'
EXPECTED = {'1': (495,4320,'4500247815-22/07/2026'), '4': (496,3966,'4500247815-22/07/2026'),
            '6': (497,354,'4500247816-22/07/2026')}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def preview(db, target, live):
    items=list(db.scalars(select(rev.Item).where(rev.Item.id_documento==DOC).order_by(rev.Item.id)))
    certs=list(db.scalars(select(rev.Certificate).where(rev.Certificate.esolver_id_documento==DOC).order_by(rev.Certificate.id)))
    require(len(items)==len(certs)==3 and {i.id_riga_doc for i in items}==set(EXPECTED),'righe differenti: fermarsi')
    all_rows=rev.snapshot_rows(items,include_absent=True)[DOC]
    current=rev.snapshot_rows(items)[DOC]
    require(len(current)==2,'documento non più nello stato atteso')
    normalized=[ddt_snapshot._normalize(raw) for raw in live if str(raw['IdDocumento']).strip()==DOC]
    live_rows={r['source_key']:r for r in normalized}
    require(len(normalized)==len(live_rows) and set(current)==set(live_rows) and all(all(getattr(i,k)==live_rows[i.source_key][k] for k in rev.FIELDS)
        for i in items if i.source_present),'CERTI e vista eSolver non coincidono: ripetere audit')
    inputs=[]
    for i in items:
        cid,qty,order=EXPECTED[i.id_riga_doc]
        c=next((c for c in certs if c.id==cid),None)
        require((i.cod_odp,i.cod_f3,i.ddt_raw,i.rif_lotto_alfanum,i.quantita,i.ordine_cliente)==
                (OL,F3,DDT,'2026001058',qty,order) and i.source_present==(cid!=495)
                and not i.source_review_reason and c and rev.bound(c,all_rows[i.source_key]),'identità mutata')
        require((c.status,c.certificate_number,c.quantita)==
            (('pdf_final',NUMBER,qty) if cid==495 else ('draft',BASE,qty)),'certificato cambiato')
        require(cid==495 or c.word_source=='inherited' and not c.shipment_context,
                'bozza già lavorata o collegata: fermarsi')
        require(not db.get(rev.Repair,cid),'altra correzione già aperta')
        versions=list(db.scalars(select(rev.Version).where(rev.Version.certificate_id==cid)))
        require((len(versions)==1 and versions[0].version==1 and versions[0].status=='active'
                 and versions[0].annulled_at is None and c.storage_key_pdf==versions[0].storage_key_pdf and c.storage_key_pdf) if cid==495
            else (not versions and not c.storage_key_pdf),'versioni PDF diverse dal previsto')
        word_reference.require_integrity(c)
        controls,_=reuse.word_facts(c.storage_key_docx)
        require(controls.get('CERT_NUMBER')==c.certificate_number and controls.get('ORDER_CLIENT')==order
            and controls.get('QUANTITY_FINISHED')==str(qty),'contenuto Word diverso dal previsto')
        keys=[c.storage_key_docx]+([c.storage_key_pdf] if c.storage_key_pdf else [])
        keys.extend(a.storage_key_pdf for a in reuse.service._pdf_attachments_for_certificate(db,certificate=c))
        base= reuse.service._manual_word_base_path(c)
        if base: keys.append(reuse.service._certificate_manual_base_docx_storage_key(c))
        inputs.append(dict(id=cid,row=all_rows[i.source_key],metadata=c.word_reference,
            updated=str(c.updated_at),files={k:reuse.file_hash(k) for k in keys}))
    previous=db.get(rev.Certificate,268)
    require(previous and previous.esolver_id_documento=='5258566' and previous.certificate_number==BASE
        and previous.status=='pdf_final' and previous.storage_key_pdf,'verificare DDT 2575')
    pages=[reuse.service._additional_pages_for_certificate(db,certificate_number=n) for n in (BASE,NUMBER)]
    digest=reuse.digest([target, inputs, reuse.file_hash(previous.storage_key_pdf),
        [(p.id,p.storage_key_docx,reuse.file_hash(p.storage_key_docx)) for p in pages if p]])
    return digest, {k:v for k,v in all_rows.items() if k not in current},current


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview',action='store_true')
    mode.add_argument('--apply-digest')
    parser.add_argument('--maintenance-confirmed',action='store_true')
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--storage-backup',type=Path)
    args=parser.parse_args()
    require(not settings.ddt_word_reuse_enabled and not settings.ddt_snapshot_enabled,'disattivare i worker nel container una tantum')
    if args.apply_digest:
        require(args.maintenance_confirmed and args.backup and args.storage_backup,'richiesti manutenzione e backup verificati')
        check_backup(args.backup)
        require(args.storage_backup.is_absolute() and args.storage_backup.is_file() and args.storage_backup.stat().st_size,'backup storage richiesto')
    created=[]
    committing=False
    try:
        with SessionLocal() as db:
            if args.preview: db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            target=alpha_database_identity(db,settings)
            live=ddt_snapshot._fetch_complete_snapshot(db)
            if args.apply_digest: lock_inputs(db)
            digest,first,last=preview(db,target,live)
            if args.preview:
                print(json.dumps(dict(digest=digest,ritiro='495 v1',word_da_aggiornare=[496,497],
                    totale=4320,numero=NUMBER,DDT_2575='invariato',pdf_generati=0)))
                return
            require(digest==args.apply_digest,'anteprima non più valida')
            ev=rev.record_change(db,DOC,first,last,datetime.now(timezone.utc))
            db.flush()
            tasks=list(db.scalars(select(rev.Repair).where(rev.Repair.change_id==ev.id)))
            require([w['id'] for w in ev.withdrawals]==[495] and sorted(t.certificate_id for t in tasks)==[496,497],'perimetro inatteso')
            for task in tasks: rev.repair_word(db,task,created); db.flush()
            for cid,qty in [(496,3966),(497,354)]:
                c=db.get(rev.Certificate,cid)
                word_reference.require_integrity(c)
                word_standard.require_current(db,c)
                hard,_=word_reference.pdf_reference_check(db,c)
                require(not hard and c.status=='draft' and not c.storage_key_pdf and c.certificate_number==NUMBER
                    and reuse.word_facts(c.storage_key_docx)[0]['QUANTITY_FINISHED']==f'{qty} of 4320','Word non pronto: rollback')
            committing=True
            db.commit()
            print('Solo 495 ritirato e Word 496/497 aggiornati. Segnalazione Qualità in coda. Nessun PDF generato.')
    finally:
        if not committing:
            for path in created: path.unlink(missing_ok=True)


if __name__=='__main__':
    main()
