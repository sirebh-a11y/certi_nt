"""One audited Beta document only. Preview is read-only. Never generate a PDF."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.database import SessionLocal
from app.startup import bootstrap as _models  # Register mappers, do NOT bootstrap.
from app.modules.quarta_taglio import ddt_context, ddt_revisions as rev, ddt_shipments, ddt_snapshot, ddt_word_reuse as reuse, word_reference, word_standard
from app.modules.quarta_taglio.ddt_recovery import alpha_database_identity
from app.modules.quarta_taglio.ddt_word_recovery import lock_inputs
from scripts.recover_ddt_alpha import check_backup

DOC, OL, F3, DDT = '5296723', 'OL2026001058', '520002360', '2866-20/11/2026'
NUMBER, BASE = '7028_00_60_01/26', '7028_00_60/26'
EXPECTED = {'1': (495,4320,'4500247815-22/07/2026'), '4': (496,3966,'4500247815-22/07/2026'),
            '6': (497,354,'4500247816-22/07/2026')}
SHIP = {'CERT_NUMBER','CERT_DATE','PURCHASER','ORDER_CLIENT','CONFIRM_ORDER','DDT_FINISHED','QUANTITY_FINISHED'}
DESCRIPTION = 'FINISHED_DESCRIPTION'
# Full evidence from the read-only Beta audit. A fresh preview must NOT
# authorize silent drift since that inspection, even with the same number.
AUDITED = {
    268: ('7319007f64cf142d3611e127fc09b0fdad4051cde1fd0a0d283afd126542d2ef','bda8262ce8676b2c256c2c2dd8cf5b5ca2838749213f3a1f58181796f771d971'),
    495: ('2d5ec42879e8dbe38cb17741820649f1fff42cce61364d3d50b2feeabaf4c5dc','dfae9e623d9015df64a26589e9fa00aa280df55aa89f87af9a11d95695207cd7'),
    496: ('336049f4bd3ec9fa914ddca9b1f599257b9a7b1d7f6919db70570149eab37b4f',None),
    497: ('fb0fe0ada2d31f1fbd2b2a12e14d0159e05473113103cb4f8959a9b94006c341',None),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_audited_files(db):
    for cid, hashes in AUDITED.items():
        c=db.get(rev.Certificate,cid)
        require(c and (reuse.file_hash(c.storage_key_docx),
                       reuse.file_hash(c.storage_key_pdf) if c.storage_key_pdf else None)==hashes,
                f'File {cid} cambiato rispetto alla verifica Beta: fermarsi')


def validate_word_chain(db, descriptions):
    root,approved=(db.get(rev.Certificate,cid) for cid in (268,495))
    reference=word_reference.declared(word_reference.sources_for(db,OL,F3))
    require(root and approved and reference is root and word_reference.metadata(root).get('revision'),
            'Riferimento tecnico 268 cambiato')
    meta=word_reference.metadata(approved)
    require(meta.get('kind')=='copy' and meta.get('source_id')==root.id and
            meta.get('revision')==word_reference.metadata(root)['revision'],'Catena 268/495 diversa')
    require(descriptions and all(isinstance(d,str) and d.strip() and d==descriptions[0] for d in descriptions),
            'Descrizione CertiOL assente o ambigua')
    description=descriptions[0]
    src,signature=reuse.word_facts(approved.storage_key_docx,peer_fields=SHIP|{DESCRIPTION})
    require(src.get(DESCRIPTION)==description and src.get('COD_F3_FINISHED')==F3,
            'Descrizione CertiOL diversa dal Word approvato')
    for cid in (268,495,496,497):
        c=db.get(rev.Certificate,cid)
        require(c and (c.cod_odp,c.cod_f3)==(OL,F3) and
                not reuse.service._pdf_attachments_for_certificate(db,certificate=c)
                and not reuse.service._manual_word_base_path(c),'Allegati, base manuale o identità variati')
        word_reference.require_integrity(c)
        word_standard.require_current(db,c,for_reuse=True)
        require(c.cdq_values and not word_reference.material_changed(db,c) and
                reuse.service._certificate_conformity_status(c)=='conforme','Materiale o conformità da verificare')
        if cid not in (496,497):
            continue
        tags,signature_draft=reuse.word_facts(c.storage_key_docx,peer_fields=SHIP|{DESCRIPTION})
        require(not c.word_reference and tags.get(DESCRIPTION)=='' and SHIP.issubset(tags)
                and signature_draft==signature and
                (c.certified_by_user_id,c.quality_manager_user_id)==(approved.certified_by_user_id,approved.quality_manager_user_id),
                f'Word {cid}: differenza tecnica, firma o provenienza non prevista')
    require(not any(reuse.service._additional_pages_for_certificate(db,certificate_number=n) for n in (BASE,NUMBER)),
            'Seconde pagine separate cambiate: fermarsi')
    return description


def preview(db, target, live, descriptions):
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
                and i.conferma_ordine==('635-23/07/2026' if cid==497 else '634-23/07/2026')
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
    description=validate_word_chain(db,descriptions)
    digest=reuse.digest(['2866-v2',target,inputs,description,previous.word_reference,
        reuse.file_hash(previous.storage_key_docx),reuse.file_hash(previous.storage_key_pdf)])
    return digest, {k:v for k,v in all_rows.items() if k not in current},current


def repair_case(db, first, last, descriptors, created):
    description=validate_word_chain(db,descriptors)
    root,approved=(db.get(rev.Certificate,cid) for cid in (268,495))
    originals={key:reuse.file_hash(key) for c in (root,approved) for key in (c.storage_key_docx,c.storage_key_pdf)}
    root_state=(root.storage_key_docx,root.storage_key_pdf,root.certificate_number,word_reference.metadata(root).get('revision'))
    approved_pdf,previous_token=approved.storage_key_pdf,approved.download_token
    _,approved_technical=reuse.word_facts(approved.storage_key_docx,peer_fields=SHIP)
    ev=rev.record_change(db,DOC,first,last,datetime.now(timezone.utc))
    db.flush()
    tasks=list(db.scalars(select(rev.Repair).where(rev.Repair.change_id==ev.id)))
    require([w['id'] for w in ev.withdrawals]==[495] and sorted(t.certificate_id for t in tasks)==[496,497],'perimetro inatteso')
    for task in tasks:
        c=db.get(rev.Certificate,task.certificate_id)
        old_key=c.storage_key_docx
        old_hash=reuse.file_hash(old_key)
        rev.repair_word(db,task,created,verified_finished_description=description)
        tags,technical=reuse.word_facts(c.storage_key_docx,peer_fields=SHIP)
        require(technical==approved_technical and tags[DESCRIPTION]==description and reuse.file_hash(old_key)==old_hash,
                'Documento tecnico diverso dal Word approvato: rollback')
        reuse.service._apply_word_file_state(c,reuse.service._certificate_storage_path(c.storage_key_docx),source='ddt_reused')
        word_reference.mark_copy(c,root)  # 495 proves equivalence; 268 owns the current revision.
        c.word_reference=dict(c.word_reference,verified_against=495,automatic_history=[
            dict(storage_key=old_key,file_hash=old_hash,origin='2866_verified_legacy_recovery')])
        db.flush()
    for cid,qty in [(496,3966),(497,354)]:
        c=db.get(rev.Certificate,cid)
        item=db.get(rev.Item,next(r['item_id'] for r in last.values() if r['id_riga_doc']==c.esolver_id_riga_doc))
        tags,_=reuse.word_facts(c.storage_key_docx)
        expected=reuse.shipment_values(item,c,tags,db=db)
        word_reference.require_integrity(c)
        word_standard.require_current(db,c)
        rev.guard(db,c)
        ddt_shipments.require_current(db,c)
        word_reference.require_current_material(db,c)
        require(ddt_context.certificate_for_saved_ddt(db,item) is c
                and c.status=='draft' and not c.storage_key_pdf and c.certificate_number==NUMBER
                and tags['QUANTITY_FINISHED']==f'{qty} of 4320' and all(tags[k]==str(v) for k,v in expected.items()),
                'Word non pronto: rollback')
    version=db.scalars(select(rev.Version).where(rev.Version.certificate_id==495)).one()
    require(not approved.storage_key_pdf and approved.download_token!=previous_token and
            version.version==1 and version.status=='withdrawn' and version.annulled_at is not None and
            version.storage_key_pdf==approved_pdf and ev.delivery=='unknown' and ev.email_status=='pending' and
            root_state==(root.storage_key_docx,root.storage_key_pdf,root.certificate_number,word_reference.metadata(root).get('revision')) and
            all(reuse.file_hash(key)==expected for key,expected in originals.items()),
            'Ritiro, notifica o conservazione degli originali non verificati: rollback')
    return ev


def rehearsal_target(db):
    url=make_url(settings.database_url)
    require(settings.app_env=='test' and url.get_backend_name()=='postgresql'
            and url.host in {'localhost','127.0.0.1','pg-2866-clone'} and url.database=='certi_ddt_test_2866'
            and Path(settings.document_storage_root).resolve().name=='storage-2866-rehearsal',
            'Richiesti database e storage dedicati al collaudo isolato')
    require(db.scalar(text('SELECT current_database()'))==url.database,'Database di collaudo diverso')
    return dict(environment='isolated-rehearsal',database=url.database)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview',action='store_true')
    mode.add_argument('--apply-digest')
    mode.add_argument('--source-evidence',action='store_true',help='Solo lettura: esporta le due righe e la descrizione per la prova offline')
    mode.add_argument('--rehearse',type=Path,metavar='EVIDENZA_JSON',help='Solo clone isolato: prova il recupero e annulla tutto')
    parser.add_argument('--maintenance-confirmed',action='store_true')
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--storage-backup',type=Path)
    args=parser.parse_args()
    require(not any((settings.ddt_word_reuse_enabled,settings.ddt_snapshot_enabled,settings.ddt_revisions_enabled)),
            'disattivare i worker nel container una tantum')
    if args.apply_digest is not None:
        require(args.maintenance_confirmed and args.backup and args.storage_backup,'richiesti manutenzione e backup verificati')
        check_backup(args.backup)
        require(args.storage_backup.is_absolute() and args.storage_backup.is_file() and args.storage_backup.stat().st_size,'backup storage richiesto')
    created=[]
    committing=False
    try:
        with SessionLocal() as db:
            if args.preview or args.source_evidence: db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            if args.rehearse:
                target=rehearsal_target(db)
                evidence=json.loads(args.rehearse.read_text(encoding='utf-8-sig'))
                live,descriptors=evidence['rows'],evidence['descriptions']
                require(len(live)==2 and all(str(r['IdDocumento']).strip()==DOC for r in live),'Fotografia fuori perimetro')
            else:
                target=alpha_database_identity(db,settings)
                live=[r for r in ddt_snapshot._fetch_complete_snapshot(db) if str(r['IdDocumento']).strip()==DOC]
                descriptors=[r.des_f3 for r in reuse.service._fetch_certiol_rows_batch(db,[OL]).get(OL,[]) if r.cod_f3==F3]
            if args.source_evidence:
                require(len(live)==2 and descriptors,'Fotografia 2866 incompleta')
                print(json.dumps(dict(rows=live,descriptions=descriptors),default=str))
                return
            if args.apply_digest is not None or args.rehearse: lock_inputs(db)
            verify_audited_files(db)
            digest,first,last=preview(db,target,live,descriptors)
            if args.preview:
                print(json.dumps(dict(digest=digest,ritiro='495 v1',word_da_aggiornare=[496,497],
                    totale=4320,numero=NUMBER,DDT_2575='invariato',pdf_generati=0)))
                return
            if not args.rehearse: require(digest==args.apply_digest,'anteprima non più valida')
            repair_case(db,first,last,descriptors,created)
            if args.rehearse:
                db.rollback()
                print('Prova isolata riuscita: verificati 495, 496 e 497. Transazione annullata; nessun PDF generato.')
                return
            committing=True
            db.commit()
            print('Solo 495 ritirato e Word 496/497 aggiornati. Segnalazione Qualità in coda. Nessun PDF generato.')
    finally:
        if not committing:
            for path in created: path.unlink(missing_ok=True)


if __name__=='__main__':
    main()
