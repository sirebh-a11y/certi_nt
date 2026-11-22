from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
from sqlalchemy import select
from fastapi import HTTPException
from app.core.config import settings
from app.modules.quarta_taglio import ddt_revisions as rev, ddt_shipments as ship, ddt_snapshot as snap
from app.modules.quarta_taglio import ddt_quality_notices as notices, ddt_word_reuse as reuse, service, word_reference as refs
from app.modules.quarta_taglio.ddt_router import confirm_customer_delivery
from app.modules.esolver_export.service import list_esolver_pdf_certificates
import test_quarta_taglio_ddt_word_reuse as reuse_fixture


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.t=reuse_fixture.DdtWordReuseTest()
        self.t.setUp()
        self.addCleanup(self.t.doCleanups)
        flag=patch.object(settings,'ddt_revisions_enabled',True)
        flag.start(); self.addCleanup(flag.stop)
        self.db=self.t.db

    def sync(self,*rows):
        snap._apply_snapshot(self.db,list(rows),now=datetime.now(timezone.utc))
        self.db.commit()

    def raw(self,item,**changes):
        fields=('id_documento','id_riga_doc','rif_lotto_alfanum','cod_odp','cod_f3','ddt_raw',
                'cliente','ordine_cliente','conferma_ordine','quantita','certificato_presente_esolver')
        return dict(dict(zip(snap._COLUMNS,[getattr(item,k) for k in fields])),**changes)

    def test_split_closed_and_no_cross_ddt_or_double_notification(self):
        original,other=self.t.base_word()
        a=self.t.later(IdRigaDoc='1',QtaUmMag=4320)
        self.assertEqual(self.t.run_worker()['prepared'],1)
        c=self.db.scalar(select(rev.Certificate).where(rev.Certificate.unit_key==a.certification_unit_key))
        c.status='pdf_final'; c.storage_key_pdf='old.pdf'; c.closed_at=datetime.now(timezone.utc)
        c.download_token='old-token'; self.db.add(rev.Version(certificate_id=c.id,version=1,status='active',storage_key_pdf='old.pdf'))
        Path(self.t.files.name,'old.pdf').write_bytes(b'original PDF')
        self.db.commit()
        base=self.raw(original)
        b=self.raw(a,IdRigaDoc='4',QtaUmMag=3966)
        d=self.raw(a,IdRigaDoc='6',QtaUmMag=354,ODVCli='DIFFERENT-ORDER')
        self.sync(base,b,d); self.sync(base,b,d)
        self.assertEqual(self.db.query(rev.Change).count(),1)
        self.assertEqual(a.source_review_reason,rev.REMOVED)
        self.assertIsNone(c.storage_key_pdf)
        self.assertTrue(c.shipment_context['retired'])
        self.assertEqual(Path(self.t.files.name,'old.pdf').read_bytes(),b'original PDF')
        with self.assertRaises(HTTPException):service.get_quarta_taglio_certificate_pdf_file(self.db,certificate_id=c.id,download_token='old-token')
        self.assertNotIn(c.id,[x.id_certi for x in list_esolver_pdf_certificates(self.db,public_base_url='http://local').items])
        self.assertEqual(self.t.run_worker()['prepared'],2)
        for rid,q in [('4','3966 of 4320'),('6','354 of 4320')]:
            new=self.db.scalar(select(rev.Certificate).where(rev.Certificate.esolver_id_riga_doc==rid))
            fields,_=reuse.word_facts(new.storage_key_docx)
            self.assertEqual((fields['QUANTITY_RAW'],fields['CERT_NUMBER']),(q,c.certificate_number))
        self.assertNotIn(a.id,[r.id for r in self.t.read().items])
        self.assertEqual(other.status,'pdf_final')
        with patch.object(settings,'ddt_quality_email','quality@example.invalid'),patch.object(notices.email_service,'_send_with_config') as send:
            notices.dispatch_emails(self.t.factory); notices.dispatch_emails(self.t.factory)
            self.assertEqual(send.call_count,1)
            self.assertIn('DIFFERENT-ORDER',send.call_args.args[0].body)
            self.assertIsNone(send.call_args.args[1].mail_always_cc_email)
        case=notices.quality_cases(self.db)[0]
        self.assertEqual(len(case['current']),2)
        confirm_customer_delivery(case['id'],'sent',self.db,self.t.actor)
        self.assertEqual(notices.quality_cases(self.db)[0]['delivery'],'sent')
        confirm_customer_delivery(case['id'],'customer_informed',self.db,self.t.actor)
        self.assertEqual(notices.quality_cases(self.db)[0]['delivery'],'customer_informed')  # new PDFs still due

    def test_order_and_quantity_update_on_existing_word_preserves_reference_revision(self):
        i,c=self.t.base_word(closed=False)
        from docx import Document
        from shutil import copyfile
        path=service._certificate_storage_path(c.storage_key_docx)
        word=Document(path)
        word.add_page_break()
        word.add_paragraph('Seconda pagina: nota tecnica di Qualità.')
        word.save(path)
        manual_base=service._certificate_storage_path(service._certificate_manual_base_docx_storage_key(c))
        manual_base.parent.mkdir(parents=True,exist_ok=True)
        copyfile(path,manual_base)
        refs.publish(self.db,c,actor_id=self.t.actor.id,origin='manual_second_page')
        self.db.commit()
        revision=refs.metadata(c)['revision']; old=c.storage_key_docx
        unchanged=reuse.file_hash(old)
        self.sync(self.raw(i,ODVCli='CORRECTED',QtaUmMag=4320))
        with self.assertRaises(HTTPException):rev.guard(self.db,c)
        rev.process_repairs(self.t.factory); self.db.expire_all()
        task=self.db.get(rev.Repair,c.id)
        self.assertIsNone(task,task.error if task else '')
        h,_=reuse.word_facts(c.storage_key_docx)
        self.assertEqual((h['ORDER_CLIENT'],h['QUANTITY_RAW']),('CORRECTED','4320'))
        self.assertEqual(c.unit_key,i.certification_unit_key)
        self.assertEqual(refs.metadata(c)['revision'],revision)
        self.assertIsNone(refs.integrity_reason(c))
        self.assertEqual(reuse.file_hash(old),unchanged)
        self.assertEqual(Document(service._certificate_storage_path(c.storage_key_docx)).paragraphs[-1].text,
            'Seconda pagina: nota tecnica di Qualità.')
        self.assertEqual(Document(service._manual_word_base_path(c)).paragraphs[-1].text,
            'Seconda pagina: nota tecnica di Qualità.')
        self.assertEqual(reuse.word_facts(service._certificate_manual_base_docx_storage_key(c))[0]['QUANTITY_RAW'],'4320')
        self.assertEqual(notices.quality_cases(self.db),[])

    def test_expiry_unrelated_ddt_and_source_flag_do_not_withdraw(self):
        i,c=self.t.base_word()
        self.sync(self.raw(i,CertificatoPresente=1))
        self.sync(self.raw(i,IdDocumento='another',DDT='2-20/11/2026'))
        self.assertFalse(i.source_present)
        self.assertIsNone(i.source_review_reason)
        self.assertTrue(c.storage_key_pdf)
        self.assertEqual(notices.quality_cases(self.db),[])
        self.sync(self.raw(i))
        self.assertTrue(c.storage_key_pdf)
        self.assertEqual(notices.quality_cases(self.db),[])

    def test_disappears_then_returns_split_and_old_record_has_no_unit_key(self):
        i,c=self.t.base_word()
        c.unit_key=None
        self.db.commit()
        other=self.raw(i,IdDocumento='another',DDT='2-20/11/2026')
        self.sync(other)
        self.assertTrue(c.storage_key_pdf)
        self.sync(other,self.raw(i,IdRigaDoc='4',QtaUmMag=2000),self.raw(i,IdRigaDoc='6',QtaUmMag=1000))
        self.assertIsNone(c.storage_key_pdf)
        self.assertTrue(c.shipment_context['retired'])
        self.assertEqual(len(notices.quality_cases(self.db)),1)

    def test_untrusted_manual_file_is_preserved_and_pdf_blocked(self):
        i,c=self.t.base_word(closed=False)
        refs.publish(self.db,c,actor_id=self.t.actor.id,origin='upload')
        self.db.commit()
        path=service._certificate_storage_path(c.storage_key_docx)
        path.write_bytes(b'unexpected manual file')
        self.sync(self.raw(i,QtaUmMag=999))
        rev.process_repairs(self.t.factory); self.db.expire_all()
        with self.assertRaises(HTTPException):rev.guard(self.db,c)
        self.assertEqual(path.read_bytes(),b'unexpected manual file')

    def test_unchanged_display_total_updates_open_word_fingerprint_without_rewriting_word(self):
        i,c=self.t.base_word(closed=False)
        a=self.raw(i)
        peer=self.raw(i,IdRigaDoc='2',QtaUmMag=100)
        self.sync(a,peer)
        rev.process_repairs(self.t.factory); self.db.expire_all()
        self.assertFalse(self.db.get(rev.Repair,c.id))
        old_key=c.storage_key_docx
        old_revision=c.shipment_context['revision']
        self.sync(a,dict(peer,QtaUmMag=70),dict(peer,IdRigaDoc='3',QtaUmMag=30))
        rev.process_repairs(self.t.factory); self.db.expire_all()
        self.assertFalse(self.db.get(rev.Repair,c.id))
        self.assertEqual(c.storage_key_docx,old_key)
        self.assertNotEqual(c.shipment_context['revision'],old_revision)
        ship.require_current(self.db,c)
        self.assertEqual(notices.quality_cases(self.db),[])

    def test_replay_existing_inherited_words_preserves_edits_and_allows_both_pdfs(self):
        original,base=self.t.base_word()
        old=self.t.later(IdRigaDoc='1',QtaUmMag=4320)
        self.t.run_worker()
        obsolete=self.db.scalar(select(rev.Certificate).where(rev.Certificate.unit_key==old.certification_unit_key))
        self._close_fixture(obsolete)
        first=rev.snapshot_rows([old])[old.id_documento]
        # Two legacy inherited drafts with the earlier DDT's number and no tracked total.
        a=self.t.later(IdRigaDoc='4',QtaUmMag=3966)
        b=self.t.later(IdRigaDoc='6',QtaUmMag=354,ODVCli='OTHER ORDER')
        current=[]
        for i in (a,b):
            c=self.t.cert(i,certificate_number=base.certificate_number,draft_number=base.certificate_number,
                cdq_key=base.cdq_key,cdq_values=base.cdq_values,cdq_signature=base.cdq_signature,
                conformity_status='conforme',word_source='inherited')
            path=service._certificate_storage_path(c.storage_key_docx)
            service.build_forgialluminio_draft_docx(detail=self.t.detail(i),output_path=path,
                draft_number=c.certificate_number,certified_by=self.t.actor,quality_manager=self.t.actor)
            refs.publish(self.db,c,actor_id=self.t.actor.id,origin='inherited_creation')
            current.append(c)
        old.source_present=False
        self.db.commit()
        ev=rev.record_change(self.db,old.id_documento,first,rev.snapshot_rows([a,b])[a.id_documento],datetime.now(timezone.utc))
        self.db.commit()
        rev.process_repairs(self.t.factory)
        self.db.expire_all()
        self.assertFalse([r.error for r in self.db.scalars(select(rev.Repair))])
        self.assertEqual(self.db.get(rev.Certificate,base.id).status,'pdf_final')
        for c,i,q in zip(current,(a,b),('3966 of 4320','354 of 4320')):
            self.assertEqual(c.certificate_number,obsolete.certificate_number)
            self.assertNotEqual(c.certificate_number,base.certificate_number)
            fields,_=reuse.word_facts(c.storage_key_docx)
            self.assertEqual((fields['ORDER_CLIENT'],fields['QUANTITY_RAW'],fields['CERT_NUMBER']),
                             (i.ordine_cliente,q,c.certificate_number))
            # No discretionary changes in either Word: no override/consent token.
            hard,peer=refs.pdf_reference_check(self.db,c)
            self.assertIsNone(hard)
            self.assertFalse(peer and peer.token)
            self._close_fixture(c)
        confirm_customer_delivery(ev.id,'not_sent',self.db,self.t.actor)
        self.assertEqual(notices.quality_cases(self.db),[])
        self.assertEqual(self.t.run_worker()['prepared'],0)

    def _close_fixture(self,c):
        def convert(word,pdf):
            pdf.parent.mkdir(parents=True,exist_ok=True)
            pdf.write_bytes(b'%PDF offline converter fixture')
        c.conformity_status='conforme'
        self.db.commit()
        with patch.object(service,'_build_standard_conformity',return_value=('conforme',[])),patch.object(service,'convert_docx_to_pdf',side_effect=convert):
            service.generate_quarta_taglio_certificate_pdf(self.db,certificate_id=c.id,actor=self.t.actor)

    def test_beta_2866_preview_rejects_drift_and_replays_only_the_expected_files(self):
        from scripts import recover_ddt_2866 as cli
        _,template=self.t.base_word()
        previous=self.t.item(IdDocumento='5258566',ORP=cli.OL,CodF3=cli.F3,DDT='2575-23/10/2026')
        previous_cert=self.t.cert(previous,id=268,pdf=True,certificate_number=cli.BASE)
        previous_hash=reuse.file_hash(previous_cert.storage_key_pdf)
        live=[]
        for row,(cid,qty,order) in cli.EXPECTED.items():
            i=self.t.item(IdDocumento=cli.DOC,IdRigaDoc=row,ORP=cli.OL,CodF3=cli.F3,DDT=cli.DDT,
                RifLottoAlfanum='2026001058',RagSoc='PETZL',ODVCli=order,QtaUmMag=qty)
            n=cli.NUMBER if cid==495 else cli.BASE
            c=self.t.cert(i,id=cid,certificate_number=n,draft_number=n,pdf=cid==495,word_source='inherited')
            service.update_docx_content_controls(service._certificate_storage_path(template.storage_key_docx),
                service._certificate_storage_path(c.storage_key_docx),
                dict(CERT_NUMBER=n,ORDER_CLIENT=order,QUANTITY_FINISHED=str(qty),DDT_FINISHED=cli.DDT,
                     COD_F3_FINISHED=cli.F3))
            if cid!=495: live.append(self.raw(i))
            else: i.source_present=False
            self.db.commit()
        target={'database':'disposable-test'}
        digest,before,after=cli.preview(self.db,target,live)
        self.assertEqual(digest,cli.preview(self.db,target,live)[0])
        for conflicting in ([*live,live[0]],[dict(live[0],QtaUmMag=4000),live[1]]):
            with self.assertRaisesRegex(ValueError,'vista eSolver'):cli.preview(self.db,target,conflicting)
        ev=rev.record_change(self.db,cli.DOC,before,after,datetime.now(timezone.utc))
        self.db.flush()
        self.assertEqual([w['id'] for w in ev.withdrawals],[495])
        tasks=list(self.db.scalars(select(rev.Repair).order_by(rev.Repair.certificate_id)))
        self.assertEqual([t.certificate_id for t in tasks],[496,497])
        files=[]
        for t in tasks:
            rev.repair_word(self.db,t,files)
            self.db.flush()
        for cid,qty in [(496,3966),(497,354)]:
            c=self.db.get(rev.Certificate,cid)
            controls,_=reuse.word_facts(c.storage_key_docx)
            self.assertEqual((controls['QUANTITY_FINISHED'],controls['CERT_NUMBER'],controls['ORDER_CLIENT']),
                (f'{qty} of 4320',cli.NUMBER,cli.EXPECTED[c.esolver_id_riga_doc][2]))
            self.assertFalse(c.storage_key_pdf)
            # Optional end-to-end conversion in disposable storage, not a publication.
            import os
            if binary:=os.getenv('CERTI_QA_REAL_PDF'):
                import fitz
                pdf=Path(self.t.files.name,f'preview-{cid}.pdf')
                with patch.object(settings,'libreoffice_bin',binary),patch.object(settings,'pdf_conversion_enabled',True):
                    service.convert_docx_to_pdf(service._certificate_storage_path(c.storage_key_docx),pdf)
                with fitz.open(pdf) as rendered:
                    printed=' '.join(' '.join(p.get_text() for p in rendered).split())
                for expected in (f'{qty} of 4320',cli.NUMBER,cli.EXPECTED[c.esolver_id_riga_doc][2]):
                    self.assertIn(expected,printed)
        self.assertEqual(reuse.file_hash(previous_cert.storage_key_pdf),previous_hash)
