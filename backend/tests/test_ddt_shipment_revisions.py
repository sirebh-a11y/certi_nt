from datetime import datetime, timezone
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from sqlalchemy import select
from fastapi import HTTPException
from app.core.config import Settings, settings
from app.modules.quarta_taglio import ddt_revisions as rev, ddt_shipments as ship, ddt_snapshot as snap
from app.modules.quarta_taglio import ddt_quality_notices as notices, ddt_word_reuse as reuse, service, word_reference as refs
from app.modules.quarta_taglio.ddt_router import confirm_customer_delivery
from app.modules.esolver_export.service import list_esolver_pdf_certificates
import test_quarta_taglio_ddt_word_reuse as reuse_fixture


class QualityRecipientSettingsTests(unittest.TestCase):
    def test_internal_default_explicit_override_and_pause(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings(_env_file=None).ddt_quality_email, 'certi@forgialluminio.it')
            self.assertFalse(Settings(_env_file=None).ddt_revisions_enabled)
            for value in ('quality@example.invalid', ''):
                with patch.dict(os.environ, DDT_QUALITY_EMAIL=value):
                    self.assertEqual(Settings(_env_file=None).ddt_quality_email, value)


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
        with patch.object(notices.email_service,'_send_with_config') as send:
            with patch.object(settings,'ddt_quality_email',''):
                notices.dispatch_emails(self.t.factory)
                send.assert_not_called()
                self.assertEqual(notices.quality_cases(self.db)[0]['email_status'],'pending')
            with patch.dict(os.environ, {}, clear=True):
                default_recipient=Settings(_env_file=None).ddt_quality_email
            with patch.object(settings,'ddt_quality_email',default_recipient):
                notices.dispatch_emails(self.t.factory); notices.dispatch_emails(self.t.factory)
            self.assertEqual(send.call_count,1)
            self.assertEqual(send.call_args.args[0].to_email,'certi@forgialluminio.it')
            self.assertIn('DIFFERENT-ORDER',send.call_args.args[0].body)
            self.assertIsNone(send.call_args.args[1].mail_always_cc_email)
        case=notices.quality_cases(self.db)[0]
        self.assertEqual(len(case['current']),2)
        confirm_customer_delivery(case['id'],'sent',self.db,self.t.actor)
        self.assertEqual(notices.quality_cases(self.db)[0]['delivery'],'sent')
        confirm_customer_delivery(case['id'],'close_notice',self.db,self.t.actor)
        self.assertEqual(notices.quality_cases(self.db),[])
        self.assertEqual(confirm_customer_delivery(case['id'],'close_notice',self.db,self.t.actor),
                         {'delivery':'sent_notice_closed'})
        self.assertEqual(self.db.get(rev.Change,case['id']).decided_by,self.t.actor.name)
        current={r.id_riga_doc:r for r in self.t.read().items}
        self.assertTrue({'4','6'} <= current.keys())  # Closing a notice never completes a share.
        self.assertTrue(all(current[k].state!='completed' for k in ('4','6')))

    def test_split_scope_and_no_delayed_mail_when_quality_finished(self):
        i,c=self.t.base_word()
        other=self.t.item(IdDocumento=i.id_documento,IdRigaDoc='9',ORP='OTHER-OL',
            CodF3='OTHER-F3',RifLottoAlfanum='other',DDT=i.ddt_raw)
        self.sync(self.raw(i,IdRigaDoc='4',QtaUmMag=3966),self.raw(i,IdRigaDoc='6',QtaUmMag=354),
                  self.raw(other,ODVCli='UNRELATED-ORDER'))
        ev=self.db.scalar(select(rev.Change))
        rows=notices.current_rows(self.db,ev)
        self.assertEqual({r.id_riga_doc for r in rows},{'4','6'})
        self.assertNotIn('UNRELATED-ORDER',notices.quality_email(ev).body)
        with self.assertRaises(HTTPException) as blocked:
            confirm_customer_delivery(ev.id,'close_notice',self.db,self.t.actor)
        self.assertEqual(blocked.exception.status_code,409)
        confirm_customer_delivery(ev.id,'not_sent',self.db,self.t.actor)
        self.t.cert(rows[0],pdf=True,certificate_number=c.certificate_number)
        self.assertTrue(notices.quality_cases(self.db))
        self.assertIn('non è stato inviato',notices.quality_email(ev).body)
        self.t.cert(rows[1],pdf=True,certificate_number=c.certificate_number)
        self.assertFalse(notices.quality_cases(self.db))
        with patch.object(notices.email_service,'_send_with_config') as send:
            with patch.object(settings,'ddt_quality_email',''):
                notices.dispatch_emails(self.t.factory)
            notices.dispatch_emails(self.t.factory)
            send.assert_not_called()
        self.db.refresh(ev)
        self.assertEqual((ev.delivery,ev.email_status),('done_not_sent','not_needed'))
        self.assertIn(other.id,[r.id for r in self.t.read().items])

    def test_closed_notice_cancels_retries_but_a_distinct_later_withdrawal_notifies(self):
        i,_=self.t.base_word()
        new=self.raw(i,IdRigaDoc='4',QtaUmMag=3966)
        self.sync(new)
        ev=self.db.scalar(select(rev.Change))
        with patch.object(settings,'ddt_quality_email','quality@example.invalid'),patch.object(
            notices.email_service,'_send_with_config',side_effect=notices.EmailNotSubmitted) as send:
            notices.dispatch_emails(self.t.factory); self.db.refresh(ev)
            self.assertEqual(ev.email_status,'retry')
            confirm_customer_delivery(ev.id,'sent',self.db,self.t.actor)
            confirm_customer_delivery(ev.id,'close_notice',self.db,self.t.actor)
            notices.dispatch_emails(self.t.factory)
            self.assertEqual(send.call_count,1)
            self.assertEqual(ev.email_status,'not_needed')
            item=self.db.scalar(select(rev.Item).where(rev.Item.id_riga_doc=='4'))
            self.t.cert(item,pdf=True,certificate_number='fake')
            self.sync(dict(new,QtaUmMag=999))
            send.side_effect=None
            notices.dispatch_emails(self.t.factory); notices.dispatch_emails(self.t.factory)
            self.assertEqual(send.call_count,2)
            self.assertNotEqual(notices.quality_cases(self.db)[0]['id'],ev.id)

    def test_known_non_delivery_retries_once_recovered_uncertain_delivery_never_retries(self):
        i,_=self.t.base_word()
        self.sync(self.raw(i,IdRigaDoc='4'))
        ev=self.db.scalar(select(rev.Change))
        with patch.object(settings,'ddt_quality_email','quality@example.invalid'),patch.object(
                notices.email_service,'_send_with_config',side_effect=[notices.EmailNotSubmitted(),None]) as send:
            notices.dispatch_emails(self.t.factory); self.db.refresh(ev)
            self.assertEqual(ev.email_status,'retry')
            notices.dispatch_emails(self.t.factory); notices.dispatch_emails(self.t.factory)
            self.db.refresh(ev)
            self.assertEqual((send.call_count,ev.email_status),(2,'sent'))
        item=self.db.scalar(select(rev.Item).where(rev.Item.id_riga_doc=='4'))
        self.t.cert(item,pdf=True,certificate_number='fake')
        self.sync(self.raw(item,QtaUmMag=888))
        with patch.object(settings,'ddt_quality_email','quality@example.invalid'),patch.object(
                notices.email_service,'_send_with_config',side_effect=TimeoutError()) as send:
            notices.dispatch_emails(self.t.factory); notices.dispatch_emails(self.t.factory)
            self.assertEqual(send.call_count,1)
            newest=self.db.scalar(select(rev.Change).order_by(rev.Change.id.desc()))
            self.assertEqual(newest.email_status,'verify')

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

    def test_later_reuse_of_retired_row_number_does_not_resurrect_it(self):
        a,closed=self.t.base_word()
        b=self.raw(a,IdRigaDoc='2',QtaUmMag=2000)
        self.sync(b)
        self.assertEqual(a.source_review_reason,rev.REMOVED)
        new=self.raw(a,RifLottoAlfanum='lot-c',QtaUmMag=1000)
        self.sync(b,new); self.sync(b,new)
        self.assertEqual(a.source_review_reason,rev.REMOVED)
        self.assertIsNone(closed.storage_key_pdf)
        self.assertNotIn(a.id,[r.id for r in self.t.read().items])
        rows=list(self.db.scalars(select(rev.Item).where(rev.Item.source_present.is_(True))))
        self.assertEqual(len(rows),2)
        self.assertTrue(all(not r.source_review_reason for r in rows))
        self.assertEqual({ship.quantity_text(self.db,r) for r in rows},{'2000 of 3000','1000 of 3000'})
        # Even if the original physical share returns, its withdrawn PDF stays historical.
        self.sync(b,self.raw(a))
        from app.modules.quarta_taglio import ddt_context
        self.assertTrue(a.source_present)
        self.assertIsNone(a.source_review_reason)
        self.assertIsNone(ddt_context.certificate_for_saved_ddt(self.db,a))
        self.assertIsNone(closed.storage_key_pdf)
        self.assertEqual(self.db.scalar(select(rev.Version.status).where(rev.Version.certificate_id==closed.id)),'withdrawn')

    def test_retired_missing_ol_is_not_promoted_to_a_new_share(self):
        a=self.t.item(ORP=None)
        b=self.raw(a,IdRigaDoc='2',RifLottoAlfanum='other-lot',ORP='OL2')
        self.sync(b)
        self.assertEqual(a.source_review_reason,rev.REMOVED)
        self.sync(b,self.raw(a,ORP='OL1'))
        self.assertFalse(a.source_present)
        self.assertIsNone(a.cod_odp)
        current=self.db.scalar(select(rev.Item).where(rev.Item.cod_odp=='OL1'))
        self.assertNotEqual(current.id,a.id)
        self.assertIsNone(current.source_review_reason)

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

    def test_quantity_changes_while_pdf_is_converting_never_publishes_stale_file(self):
        first,_=self.t.base_word()
        item=self.t.later()
        self.assertEqual(self.t.run_worker()['prepared'],1)
        c=self.db.scalar(select(rev.Certificate).where(rev.Certificate.unit_key==item.certification_unit_key))
        c.conformity_status='conforme'; self.db.commit()
        rows=[self.raw(first),self.raw(item,QtaUmMag=200)]
        attempted=[]
        def convert(word,pdf):
            attempted.append(pdf)
            pdf.parent.mkdir(parents=True,exist_ok=True)
            pdf.write_bytes(b'%PDF stale simulation')
            with self.t.factory.begin() as concurrent:
                snap._apply_snapshot(concurrent,rows,now=datetime.now(timezone.utc))
        with patch.object(service,'_build_standard_conformity',return_value=('conforme',[])),patch.object(service,'convert_docx_to_pdf',side_effect=convert):
            with self.assertRaises(HTTPException) as result:
                service.generate_quarta_taglio_certificate_pdf(self.db,certificate_id=c.id,actor=self.t.actor)
        self.assertEqual(result.exception.status_code,409)
        self.assertEqual(len(attempted),1)
        self.assertFalse(attempted[0].exists())
        self.assertIsNone(c.storage_key_pdf)
        self.assertIsNone(self.db.scalar(select(rev.Version.id).where(rev.Version.certificate_id==c.id)))

    def test_beta_2866_preview_rejects_drift_and_replays_only_the_expected_files(self):
        from scripts import recover_ddt_2866 as cli
        _,template=self.t.base_word()
        self.t.material(ol=cli.OL)
        evidence=['BLOQUEUR PRO L00483 VER.04 JAUNE BRILLANT']
        common=dict(cdq_values=template.cdq_values,cdq_key=template.cdq_key,cdq_signature=template.cdq_signature,
            conformity_status='conforme',certified_by_user_id=self.t.actor.id,quality_manager_user_id=self.t.actor.id)
        previous=self.t.item(IdDocumento='5258566',ORP=cli.OL,CodF3=cli.F3,DDT='2575-22/10/2026',QtaUmMag=1074)
        previous_cert=self.t.cert(previous,id=268,pdf=True,certificate_number=cli.BASE,**common)
        source=service._certificate_storage_path(template.storage_key_docx)
        service.update_docx_content_controls(source,service._certificate_storage_path(previous_cert.storage_key_docx),
            dict(CERT_NUMBER=cli.BASE,FINISHED_DESCRIPTION=evidence[0],COD_F3_FINISHED=cli.F3),normalize_layout=False)
        refs.publish(self.db,previous_cert,actor_id=self.t.actor.id,origin='manual')
        previous_hash=reuse.file_hash(previous_cert.storage_key_pdf)
        live=[]
        for row,(cid,qty,order) in cli.EXPECTED.items():
            i=self.t.item(IdDocumento=cli.DOC,IdRigaDoc=row,ORP=cli.OL,CodF3=cli.F3,DDT=cli.DDT,
                RifLottoAlfanum='2026001058',RagSoc='PETZL',ODVCli=order,QtaUmMag=qty,
                ODVF3='635-23/07/2026' if cid==497 else '634-23/07/2026')
            n=cli.NUMBER if cid==495 else cli.BASE
            c=self.t.cert(i,id=cid,certificate_number=n,draft_number=n,pdf=cid==495,
                          word_source='ddt_reused' if cid==495 else 'inherited',**common)
            service.update_docx_content_controls(source,
                service._certificate_storage_path(c.storage_key_docx),
                dict(CERT_NUMBER=n,ORDER_CLIENT=order,QUANTITY_FINISHED=str(qty),DDT_FINISHED=cli.DDT,
                     COD_F3_FINISHED=cli.F3,FINISHED_DESCRIPTION=evidence[0] if cid==495 else ''),normalize_layout=False)
            if cid!=495: live.append(self.raw(i))
            else:
                i.source_present=False
                refs.mark_copy(c,previous_cert)
            self.db.commit()
        target={'database':'disposable-test'}
        digest,before,after=cli.preview(self.db,target,live,evidence)
        self.assertEqual(digest,cli.preview(self.db,target,live,evidence)[0])
        for conflicting in ([*live,live[0]],[dict(live[0],QtaUmMag=4000),live[1]]):
            with self.assertRaisesRegex(ValueError,'vista eSolver'):cli.preview(self.db,target,conflicting,evidence)
        for conflicting in ([],['ALTRO'],[evidence[0],'ALTRO']):
            with self.assertRaisesRegex(ValueError,'Descrizione CertiOL'):cli.preview(self.db,target,live,conflicting)
        draft=self.db.get(rev.Certificate,497)
        with self.assertRaisesRegex(ValueError,'differenza tecnica'),self.db.begin_nested():
            draft.certified_by_user_id=None
            cli.preview(self.db,target,live,evidence)
        path=service._certificate_storage_path(draft.storage_key_docx)
        original=path.read_bytes()
        from docx import Document
        changed=Document(path); changed.add_paragraph('Nota di Qualità'); changed.save(path)
        with self.assertRaisesRegex(ValueError,'differenza tecnica'):cli.preview(self.db,target,live,evidence)
        path.write_bytes(original)
        original_hashes={cid:reuse.file_hash(self.db.get(rev.Certificate,cid).storage_key_docx) for cid in (268,495,496,497)}
        attempts=[]
        mark=refs.mark_copy
        def reject_last(c,root):
            if c.id==497: raise ValueError('injected second Word failure')
            mark(c,root)
        with self.assertRaisesRegex(ValueError,'second Word failure'),self.db.begin_nested(),patch.object(refs,'mark_copy',side_effect=reject_last):
            cli.repair_case(self.db,before,after,evidence,attempts)
        for path in attempts:path.unlink(missing_ok=True)
        self.assertFalse(self.db.scalar(select(rev.Change.id)))
        self.assertTrue(self.db.get(rev.Certificate,495).storage_key_pdf)
        self.assertEqual(original_hashes,{cid:reuse.file_hash(self.db.get(rev.Certificate,cid).storage_key_docx) for cid in original_hashes})
        files=[]
        ev=cli.repair_case(self.db,before,after,evidence,files)
        self.assertEqual([w['id'] for w in ev.withdrawals],[495])
        self.assertEqual(len(files),2)
        for cid,qty in [(496,3966),(497,354)]:
            c=self.db.get(rev.Certificate,cid)
            controls,_=reuse.word_facts(c.storage_key_docx)
            self.assertEqual((controls['QUANTITY_FINISHED'],controls['CERT_NUMBER'],controls['ORDER_CLIENT']),
                (f'{qty} of 4320',cli.NUMBER,cli.EXPECTED[c.esolver_id_riga_doc][2]))
            self.assertFalse(c.storage_key_pdf)
            self.assertEqual((refs.metadata(c)['source_id'],refs.metadata(c)['verified_against']),(268,495))
            self.assertEqual(refs.pdf_reference_check(self.db,c),(None,None))
            self.assertEqual(controls[cli.DESCRIPTION],evidence[0])
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
            self._close_fixture(c)
            self.assertEqual(c.status,'pdf_final')
        self.assertEqual(reuse.file_hash(previous_cert.storage_key_pdf),previous_hash)
