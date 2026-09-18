import copy
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa
from app.core.users.models import User  # noqa
from app.modules.notes.models import AcquisitionRowNoteTemplate, NoteTemplate  # noqa
from app.modules.suppliers.models import Supplier
from app.modules.acquisition.models import AcquisitionRow, AutonomousProcessingRun, Document, DocumentEvidence, DocumentPage
from app.modules.acquisition import service as s
from app.modules.acquisition import leichtmetall_type_workflow as w
from app.modules.acquisition.document_type_guard import DocumentTypeReviewRequired, validate_document_type_response


def check(kind='ddt', assigned='ddt'):
    return {'detected_type': kind, 'matches_assigned': None if kind=='incerto' else kind==assigned,
            'evidence': [] if kind=='incerto' else [{'page_number': 1, 'quote': 'Delivery Note' if kind=='ddt' else 'Inspection Certificate'}]}


class TypeContractTest(unittest.TestCase):
    def validate(self, value, assigned='ddt', status='completed'):
        return validate_document_type_response(NS(status=status, output_text=json.dumps(value)), assigned=assigned, page_numbers={1,2})

    def test_valid_contract_does_not_change_extraction(self):
        p = {'document_check': check(), 'rows':[{'batch_raw':'94668'}]}
        original = copy.deepcopy(p)
        self.assertEqual(self.validate(p), check())
        self.assertEqual(p, original)

    def test_wrong_mixed_uncertain_stop_before_extraction(self):
        for kind in ('certificato','misto','incerto'):
            with self.subTest(kind=kind), self.assertRaises(DocumentTypeReviewRequired) as error:
                self.validate({'document_check': check(kind), 'rows':[{'batch_raw':'MUST NOT APPLY'}]})
            self.assertFalse(s._is_retryable_processing_error(error.exception))

    def test_invalid_contracts_fail_closed(self):
        cases = [{}, {'document_check': {}}, {'document_check': {**check(), 'matches_assigned':'true'}},
                 {'document_check': {**check(), 'detected_type':['ddt']}},
                 {'document_check': {**check(), 'evidence':[]}},
                 {'document_check': {**check(), 'evidence':[{'page_number':3,'quote':'x'}]}},
                 {'document_check': {**check(), 'evidence':[{'page_number':True,'quote':'x'}]}},
                 {'document_check': {**check(), 'evidence':[{'page_number':1,'text':'x'}]}}]
        for p in cases:
            with self.subTest(payload=p), self.assertRaises(DocumentTypeReviewRequired):
                self.validate(p)
        with self.assertRaises(DocumentTypeReviewRequired):
            self.validate({'document_check':check()},status='incomplete')
        with self.assertRaises(DocumentTypeReviewRequired):
            validate_document_type_response(NS(status='completed',output_text='not JSON'),assigned='ddt',page_numbers={1})

    def test_ocr_typo_and_lost_title(self):
        for title in ('Delivery N0te','De1ivery Note','Delivery Note',''):
            doc=NS(nome_file_originale='80008535.pdf', pages=[NS(testo_estratto=
                f'LEICHTMETALL Packing List {title} 80008535 Transportnummer 2 Order Confirmation 3 Purchase Number 4 Net KG Batch Inspection Certificate 3.1 according to EN 10204',ocr_text=None)])
            self.assertEqual(s._detect_document_type(doc),'ddt')

    def test_mask_is_type_neutral_and_keeps_title(self):
        image=Image.new('RGB',(1000,1400),'white')
        lines=[{'text':'Inspection Certificate 3.1','left':50,'right':950,'top':150,'bottom':175}]
        with patch.object(s,'_extract_ocr_line_blocks',return_value=lines), patch.object(s,'_extract_ocr_word_blocks',return_value=[]):
            cert=s._build_leichtmetall_certificate_masked_page(image)
            ddt=s._build_leichtmetall_ddt_masked_page(image)
        self.assertEqual(cert.tobytes(),ddt.tobytes())
        self.assertEqual(cert.getpixel((850,160)),(255,255,255))
        self.assertEqual(cert.getpixel((850,80)),(0,0,0))


class TypeWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine,autoflush=False)()
        self.supplier=Supplier(ragione_sociale='Leichtmetall Aluminium Giesserei Hannover GmbH')
        self.db.add(self.supplier)
        self.db.commit()
        self.cache={}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def doc(self, kind='ddt', persistent=False):
        d=Document(tipo_documento=kind,stato_upload='persistente' if persistent else 'temporaneo',
                   fornitore_id=self.supplier.id,nome_file_originale='sample.pdf',storage_key=f'doc-{self.db.query(Document).count()}.pdf',numero_pagine=1)
        self.db.add(d)
        self.db.commit()
        return d

    def preflight(self, docs):
        return w.preflight_documents(self.db,docs,explicit_ids={d.id for d in docs},certificate_ai_cache=self.cache,
                                     api_key='not-a-real-key',actor_id=None,actor_email='test@example.invalid')

    def test_correct_ddt_read_once_cached(self):
        d=self.doc()
        payload=[NS(cdq='94668')]
        with patch.object(w,'read_document',return_value=(payload,check())) as read:
            accepted,failed=self.preflight([d])
            self.preflight([d])
            result=s._extract_leichtmetall_ddt_row_groups_with_vision(self.db,ddt_document=d,openai_api_key='unused')
        self.assertEqual(read.call_count,1)
        self.assertIs(result,payload)
        self.assertEqual(accepted,[d])
        self.assertFalse(failed)

    def test_reroute_both_directions_then_cache(self):
        for initial,target in [('ddt','certificato'),('certificato','ddt')]:
            d=self.doc(initial)
            mismatch=DocumentTypeReviewRequired('wrong',check=check(target,initial))
            payload={'match_values':{'numero_certificato_certificato':'94668'}} if target=='certificato' else ['ddt-row']
            with patch.object(w,'read_document',side_effect=[mismatch,(payload,check(target,target))]) as read:
                accepted,failed=self.preflight([d])
            self.assertEqual(read.call_count,2)
            self.assertEqual(d.tipo_documento,target)
            self.assertEqual(accepted,[d])
            self.assertFalse(failed)
            self.assertEqual(self.db.query(AcquisitionRow).count(),0)

    def test_loop_or_timeout_on_second_read_keeps_original_type(self):
        for second in (DocumentTypeReviewRequired('wrong again',check=check('ddt','certificato')),HTTPException(502,'timeout')):
            d=self.doc()
            with patch.object(w,'read_document',side_effect=[DocumentTypeReviewRequired('wrong',check=check('certificato','ddt')),second]) as read:
                accepted,failed=self.preflight([d])
            self.assertEqual(read.call_count,2)
            self.assertEqual(d.tipo_documento,'ddt')
            self.assertEqual(d.stato_elaborazione,'errore')
            self.assertFalse(accepted)
            self.assertTrue(failed)
            self.assertNotIn(d.id,self.cache)

    def test_used_and_persistent_documents_never_retyped(self):
        for persistent,linked in [(True,False),(False,True)]:
            d=self.doc(persistent=persistent)
            if linked:
                row=AcquisitionRow(document_ddt_id=d.id,validata_finale=True,qualita_valutazione='accettato',qualita_note='saved')
                self.db.add(row)
                self.db.commit()
            with patch.object(w,'read_document',side_effect=DocumentTypeReviewRequired('wrong',check=check('certificato','ddt'))) as read:
                _,failed=self.preflight([d])
            self.assertEqual(read.call_count,1)
            self.assertEqual(d.tipo_documento,'ddt')
            self.assertTrue(failed)
            if linked:
                self.db.refresh(row)
                self.assertTrue(row.validata_finale)
                self.assertEqual(row.qualita_note,'saved')
                self.assertIn(row.id,w.blocked_row_ids(self.db))

    def test_one_bad_file_does_not_stop_good_file_or_other_supplier(self):
        bad,good,other=self.doc(),self.doc(),self.doc()
        impol=Supplier(ragione_sociale='Impol d.o.o.')
        self.db.add(impol)
        self.db.commit()
        other.fornitore_id=impol.id
        self.db.commit()
        self.db.refresh(other)
        with patch.object(w,'read_document',side_effect=[HTTPException(502,'timeout'),([],check())]) as read:
            accepted,failed=self.preflight([bad,good,other])
        self.assertEqual(read.call_count,2)
        self.assertEqual([d.id for d in accepted],[good.id,other.id])
        self.assertEqual(len(failed),1)

    def test_partial_pages_never_sent(self):
        d=self.doc()
        d.numero_pagine=2
        self.db.add(DocumentPage(document_id=d.id,numero_pagina=1,immagine_pagina_storage_key='p1.png'))
        self.db.commit()
        self.db.expire(d,['pages'])
        with patch.object(s,'_ensure_document_page_images',return_value=d), patch.object(s,'_make_openai_client') as client:
            with self.assertRaises(DocumentTypeReviewRequired):
                w.read_document(self.db,d,'ddt','unused')
        client.assert_not_called()

    def test_blocked_rows_excluded_from_both_link_directions(self):
        ddt,cert=self.doc(),self.doc('certificato')
        a=AcquisitionRow(document_ddt_id=ddt.id,fornitore_id=self.supplier.id)
        b=AcquisitionRow(document_certificato_id=cert.id,fornitore_id=self.supplier.id)
        self.db.add_all([a,b])
        self.db.commit()
        self.db.info[w.BLOCKED_KEY]={ddt.id,cert.id}
        self.assertEqual(s._candidate_rows_for_incoming_certificate_link(self.db,supplier_id=self.supplier.id),[])
        self.assertEqual(s._candidate_rows_for_incoming_ddt_link(rows=[b],supplier_id=self.supplier.id,blocked_document_ids={cert.id}),[])

    def test_manual_certificate_without_images_stops_without_empty_cache(self):
        d=self.doc('certificato')
        with patch.object(s,'_index_document_from_path',return_value=d), patch.object(s,'_ensure_document_page_images',return_value=d), patch.object(s,'_make_openai_client') as client:
            with self.assertRaises(DocumentTypeReviewRequired):
                s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=d,openai_api_key='unused',certificate_ai_cache=self.cache)
        self.assertNotIn(d.id,self.cache)
        client.assert_not_called()

    def run_fixture(self, d, responses):
        run=AutonomousProcessingRun(ddt_document_ids=json.dumps([d.id] if d.tipo_documento=='ddt' else []),
                                    certificate_document_ids=json.dumps([d.id] if d.tipo_documento=='certificato' else []))
        self.db.add(run)
        self.db.commit()
        run_id,doc_id,initial=run.id,d.id,d.tipo_documento
        with ExitStack() as stack:
            stack.enter_context(patch.object(s,'SessionLocal',return_value=self.db))
            stack.enter_context(patch.object(w,'read_document',side_effect=responses))
            stack.enter_context(patch.object(s,'prepare_document_for_reader',side_effect=lambda db,doc:doc))
            stack.enter_context(patch.object(s,'build_document_row_split_plan',return_value=NS(row_split_candidates=[])))
            create_ddt=stack.enter_context(patch.object(s,'_ensure_autonomous_rows_with_ai',return_value=([],0)))
            create_cert=stack.enter_context(patch.object(s,'_ensure_certificate_first_rows',return_value=(0,0)))
            stack.enter_context(patch.object(s,'_run_cross_run_auto_rematch',return_value=0))
            notify=stack.enter_context(patch.object(s,'_send_autonomous_run_notification'))
            s.run_autonomous_processing(run_id=run_id,ddt_document_ids=[doc_id] if initial=='ddt' else [],
                certificate_document_ids=[doc_id] if initial=='certificato' else [],actor_id=None,
                actor_email='test@example.invalid',openai_api_key='unused',use_ddt_vision=True,use_ai_intervention=True)
        return self.db.get(AutonomousProcessingRun,run_id),self.db.get(Document,doc_id),create_ddt,create_cert,notify

    def test_full_run_does_not_reenter_rejected_certificate_or_reset_its_error(self):
        d=self.doc('certificato')
        run,doc,create_ddt,create_cert,notify=self.run_fixture(d,[DocumentTypeReviewRequired('misto',check=check('misto','certificato'))])
        self.assertEqual(run.stato,'completato')
        self.assertIn('da verificare',run.messaggio_corrente)
        self.assertEqual(doc.stato_elaborazione,'errore')
        self.assertEqual(doc.tipo_documento,'certificato')
        create_ddt.assert_not_called()
        create_cert.assert_not_called()
        self.assertTrue(notify.call_args.kwargs['failed_items'])
        self.assertEqual(self.db.query(AcquisitionRow).count(),0)

    def test_full_run_moves_corrected_document_to_ddt_phase(self):
        d=self.doc('certificato')
        run,doc,create_ddt,create_cert,_=self.run_fixture(d,[DocumentTypeReviewRequired('wrong',check=check('ddt','certificato')),([],check())])
        self.assertEqual(run.stato,'completato')
        self.assertEqual(json.loads(run.ddt_document_ids),[doc.id])
        self.assertEqual(json.loads(run.certificate_document_ids),[])
        self.assertEqual(doc.tipo_documento,'ddt')
        self.assertEqual(create_ddt.call_count,1)
        create_cert.assert_not_called()

    def test_recorded_ai_type_cannot_be_overwritten_by_upload_ocr(self):
        d=self.doc('ddt')
        w.record_check(self.db,d,initial_type='certificato',decision='corretto',checks=[check()],actor_id=None)
        with patch.object(s,'_detect_document_type',return_value='certificato'), patch.object(s,'_detect_document_supplier_id',return_value=None), patch.object(s,'_document_identity_text',return_value='LEICHTMETALL'):
            result=s._apply_document_identity_detection(self.db,d)
        self.assertEqual(result.tipo_documento,'ddt')


if __name__=='__main__':
    unittest.main()
