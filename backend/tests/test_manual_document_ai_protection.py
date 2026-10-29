"""No paid calls, no app DB: manual policy must not freeze or simplify matches."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.modules.acquisition import service as s
from app.modules.acquisition import leichtmetall_type_workflow as types
from app.modules.acquisition.ai_usage import usage_scope
from app.modules.acquisition.certificate_ai_reuse import cached_payload, reuse_certificate_payload
from app.modules.acquisition.manual_document_protection import (
    MANUAL_ENTRY_EVIDENCE, allow_explicit_ai, automatic_ai_disabled, manual_document_reason, mark_manual_entry,
)
from app.modules.acquisition.models import (
    AcquisitionRow, AutonomousProcessingRun, CertificateMatch, Document, DocumentAiExtraction,
    DocumentAiUsage, DocumentEvidence, DocumentPage, ManualMatchBlock, ReadValue,
)
from app.modules.acquisition.schemas import ManualDocumentRowCreateRequest, DocumentSideFieldsConfirmRequest, DocumentMatchDetachRequest
from app.modules.suppliers.models import Supplier
from test_certificate_ai_reuse import metalba_raw


class ManualDocumentProtectionTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.supplier = Supplier(ragione_sociale='Arconic Extrusions Hannover GmbH')
        self.db.add(self.supplier); self.db.commit()
        self.index = 0

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def doc(self, side='certificato', manual=False):
        self.index += 1
        doc = Document(tipo_documento=side,fornitore_id=self.supplier.id,nome_file_originale=f'f{self.index}.pdf',
            storage_key=f'f{self.index}.pdf',hash_file=hashlib.sha256(str(self.index).encode()).hexdigest(),
            stato_upload='persistente',stato_elaborazione='letto')
        self.db.add(doc); self.db.flush()
        self.db.add(DocumentPage(document_id=doc.id,numero_pagina=1,immagine_pagina_storage_key='unused.png',testo_estratto=''))
        if manual:
            mark_manual_entry(self.db,doc,actor_id=None)
        self.db.commit()
        return doc

    def row(self, doc, fields=None, method='utente', confirmed=True, with_ddt=False):
        ddt = self.doc('ddt') if with_ddt else None
        row = AcquisitionRow(fornitore_id=self.supplier.id,fornitore_raw=self.supplier.ragione_sociale,
             document_ddt_id=doc.id if doc.tipo_documento=='ddt' else (ddt.id if ddt else None),
             document_certificato_id=doc.id if doc.tipo_documento=='certificato' else None)
        self.db.add(row); self.db.flush()
        fields = fields if fields is not None else (
            {'numero_certificato_certificato':'EEP70000-44444444','colata_certificato':'CAST1',
             'diametro_certificato':'33','lega_certificato':'6082 F','peso_certificato':'120'}
             if doc.tipo_documento=='certificato' else
            {'numero_certificato_ddt':'EEP70000-44444444','colata':'CAST1','diametro':'33','lega':'6082 F','peso':'120'})
        for field,value in fields.items():
            self.db.add(ReadValue(acquisition_row_id=row.id,blocco='match' if doc.tipo_documento=='certificato' else 'ddt',
                campo=field,valore_grezzo=value,valore_finale=value,valore_standardizzato=value,
                stato='confermato' if confirmed else 'proposto',metodo_lettura=method,
                fonte_documentale=doc.tipo_documento))
        self.db.commit(); self.db.expire(row,['values'])
        return row

    def test_manual_creation_marks_document_and_not_only_disposable_row_history(self):
        doc=self.doc()
        response=s.create_manual_document_row(self.db,document=doc,
            payload=ManualDocumentRowCreateRequest(side='certificato',fornitore_id=self.supplier.id,
                fields={'cdq':'EEP70000-44444444','lega_base':'6082 F','diametro':'33','colata':'CAST1','peso':'120'}),
            actor_id=None,actor_email='test@example.invalid')
        self.assertEqual(manual_document_reason(self.db,doc),'explicit_manual_entry')
        marker=self.db.query(DocumentEvidence).filter_by(tipo_evidenza=MANUAL_ENTRY_EVIDENCE).one()
        self.assertIsNone(marker.acquisition_row_id)
        self.db.delete(self.db.get(AcquisitionRow,response.id)); self.db.commit()
        self.assertTrue(automatic_ai_disabled(self.db,doc))

    def test_manual_pending_document_needs_no_fields_to_be_protected(self):
        doc=self.doc(manual=True)
        self.assertTrue(automatic_ai_disabled(self.db,doc))
        self.assertEqual(s._ensure_certificate_first_rows(db=self.db,certificate_documents=[doc],actor_id=None,
            actor_email='test',openai_api_key='unused',use_ai_intervention=True,run_id=1), (0,0))
        self.assertEqual(self.db.query(AcquisitionRow).count(),0)

    def test_legacy_manual_is_per_side_not_row_run_or_note(self):
        cert=self.doc(); row=self.row(cert,with_ddt=True)
        row.ai_processing_run_id=123; row.note_documento='Certificato caricato in attesa del DDT'
        for field,val in {'colata':'CAST1','diametro':'33','peso':'120'}.items():
            self.db.add(ReadValue(acquisition_row_id=row.id,blocco='ddt',campo=field,valore_finale=val,
                stato='confermato',metodo_lettura='chatgpt',fonte_documentale='ddt'))
        self.db.commit()
        self.assertEqual(manual_document_reason(self.db,cert),'legacy_manual_side_values')
        row.note_documento='Riga CERTIFICATO creata manualmente'; self.db.commit()
        self.assertIsNone(manual_document_reason(self.db,row.ddt_document))

    def test_origin_user_and_one_manual_edit_do_not_classify_an_ai_document_as_manual(self):
        cert=self.doc(); row=self.row(cert,method='chatgpt')
        row.values[0].metodo_lettura='utente'; self.db.commit()
        self.assertIsNone(manual_document_reason(self.db,cert))

    def test_no_synthetic_manual_identity_from_partial_sibling_rows(self):
        doc=self.doc()
        self.row(doc,{'colata_certificato':'CAST1','diametro_certificato':'33'})
        self.row(doc,{'peso_certificato':'120'})
        self.assertIsNone(manual_document_reason(self.db,doc))

    def test_legacy_manual_leichtmetall_type_check_is_not_an_extraction(self):
        self.supplier.ragione_sociale='Leichtmetall'; self.db.commit()
        doc=self.doc(); self.row(doc)
        self.db.add(DocumentEvidence(document_id=doc.id,blocco='documento',tipo_evidenza=types.EVIDENCE_TYPE,
            metodo_estrazione='chatgpt',testo_grezzo=json.dumps({'decision':'confermato'})))
        self.db.commit()
        with patch.object(types,'read_document',side_effect=AssertionError('AI forbidden')):
            accepted,failed=types.preflight_documents(self.db,[doc],explicit_ids={doc.id},certificate_ai_cache={},
                api_key='unused',actor_id=None,actor_email='test')
        self.assertEqual(accepted,[doc]); self.assertEqual(failed,[])
        self.assertIsNone(cached_payload(self.db,doc,'leichtmetall'))

    def test_payload_reader_cannot_send_manual_document_even_if_cache_is_missing(self):
        doc=self.doc(manual=True)
        api=Mock(side_effect=AssertionError('AI forbidden'))
        reader=reuse_certificate_payload('arconic_hannover')(api)
        with self.assertRaises(HTTPException):
            reader(self.db,certificate_document=doc,openai_api_key='unused')
        api.assert_not_called()
        self.assertEqual(self.db.query(DocumentAiUsage).count(),0)

    def test_automatic_block_detection_is_noop_for_manual_data_even_if_incomplete(self):
        doc=self.doc(manual=True); row=self.row(doc,fields={})
        row.validata_finale=True; self.db.commit()
        with patch.object(s,'_make_openai_client',side_effect=AssertionError('AI forbidden')):
            for operation in (s.detect_chemistry,s.detect_properties,s.detect_standard_notes,s._extract_certificate_core_fields_with_vision):
                operation(self.db,row,actor_id=None,openai_api_key='unused')
            s._process_certificate_side_blocks(self.db,row=row,actor_id=None,openai_api_key='unused',use_ai_intervention=True)
        self.assertTrue(row.validata_finale)
        self.assertEqual(self.db.query(ReadValue).count(),0)

    def test_explicit_permission_is_per_document_and_does_not_leak_outside_action(self):
        one,two=self.doc(manual=True),self.doc('ddt',manual=True)
        with allow_explicit_ai(one.id):
            self.assertFalse(automatic_ai_disabled(self.db,one))
            self.assertTrue(automatic_ai_disabled(self.db,two))
        self.assertTrue(automatic_ai_disabled(self.db,one))

    def test_last_guard_rechecks_before_paid_request_if_manual_mode_changed(self):
        doc=self.doc(); client=Mock()
        with usage_scope(self.db,doc):
            mark_manual_entry(self.db,doc,actor_id=None); self.db.commit()
            with self.assertRaises(HTTPException):
                s._create_openai_response(client,model='unused')
        client.responses.create.assert_not_called()

    def test_manual_flag_does_not_freeze_match_and_live_edit_can_remove_candidate(self):
        cert=self.doc(manual=True); self.row(cert,with_ddt=True)
        target=self.row(self.doc('ddt'),method='chatgpt',confirmed=False)
        self.assertTrue(s._has_manual_rematch_candidate(self.db,target,[cert]))
        plans=s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id})
        self.assertIn(target.id,{p.row_id for p in plans})
        value=next(v for v in target.values if v.campo=='colata')
        value.valore_finale='DIFFERENT_CAST'; self.db.commit()
        self.assertFalse(s._has_manual_rematch_candidate(self.db,target,[cert]))
        self.assertNotIn(target.id,{p.row_id for p in s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id})})

    def test_hidden_arconic_fields_are_still_required_by_existing_rematch_rules(self):
        cert=self.doc(manual=True)
        source=self.row(cert,{'colata_certificato':'CAST1','articolo_certificato':'BG123',
            'codice_cliente_certificato':'A456'},with_ddt=True)
        target=self.row(self.doc('ddt'),{'colata':'CAST1','arconic_item_number':'BG123','customer_item_number':'A456'},method='chatgpt')
        self.assertTrue(s._has_manual_rematch_candidate(self.db,target,[cert]))
        original=s.score_bridge_match(s._build_row_ddt_bridge(target),s._build_row_certificate_bridge(source))
        self.assertEqual(original.decision,s.RematchDecision.STRONG)
        for value in target.values:
            if value.campo in {'arconic_item_number','customer_item_number'}:
                value.valore_finale='OTHER'
        self.db.commit()
        weakened=s.score_bridge_match(s._build_row_ddt_bridge(target),s._build_row_certificate_bridge(source))
        self.assertLess(weakened.score,original.score)
        self.assertEqual(weakened.decision,s.RematchDecision.NONE)
        self.assertFalse(s._has_manual_rematch_candidate(self.db,target,[cert]))

    def test_manual_detach_block_is_not_bypassed_by_manual_policy(self):
        cert=self.doc(manual=True); source=self.row(cert,with_ddt=True)
        target=self.row(self.doc('ddt'),method='chatgpt')
        self.db.add(ManualMatchBlock(document_ddt_id=target.document_ddt_id,document_certificato_id=cert.id,
            source_row_id=target.id,certificate_row_id=source.id,attivo=True))
        self.db.commit()
        self.assertFalse(s._has_manual_rematch_candidate(self.db,target,[cert]))
        self.assertNotIn(target.id,{p.row_id for p in s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id})})

    def test_same_pdf_rows_remain_separate_and_select_right_leichtmetall_weight(self):
        self.supplier.ragione_sociale='Leichtmetall'; self.db.commit()
        cert=self.doc(manual=True)
        first=self.row(cert,with_ddt=True)
        second=self.row(cert,with_ddt=True)
        next(v for v in first.values if v.campo=='peso_certificato').valore_finale='91'
        next(v for v in second.values if v.campo=='peso_certificato').valore_finale='29'
        target=self.row(self.doc('ddt'),method='chatgpt')
        next(v for v in target.values if v.campo=='peso').valore_finale='29'; self.db.commit()
        plan=next(p for p in s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id}) if p.row_id==target.id)
        self.assertEqual(plan.candidates[0].source_row_id,second.id)
        self.assertEqual(self.db.query(DocumentAiExtraction).count(),0)

    def run_fixture(self, ddt, certificates=()):
        run=AutonomousProcessingRun(ddt_document_ids=json.dumps([ddt.id] if ddt else []),
            certificate_document_ids=json.dumps([d.id for d in certificates]))
        self.db.add(run); self.db.commit(); run_id=run.id
        run_db=sessionmaker(bind=self.engine,autoflush=False)()
        with ExitStack() as stack:
            stack.enter_context(patch.object(s,'SessionLocal',return_value=run_db))
            stack.enter_context(patch.object(s,'_make_openai_client',side_effect=AssertionError('No paid request permitted')))
            stack.enter_context(patch.object(s,'prepare_document_for_reader',side_effect=lambda db,doc:doc))
            stack.enter_context(patch.object(s,'build_document_row_split_plan',return_value=NS(row_split_candidates=[])))
            stack.enter_context(patch.object(s,'_send_autonomous_run_notification'))
            stack.enter_context(patch.object(s,'_ensure_autonomous_rows_with_ai',side_effect=lambda **kw:
                (list(kw['ddt_document'].rows_as_ddt),0)))
            s.run_autonomous_processing(run_id=run_id,ddt_document_ids=[ddt.id] if ddt else [],
                certificate_document_ids=[d.id for d in certificates],actor_id=None,actor_email='test@example.invalid',
                openai_api_key='unused',use_ddt_vision=True,use_ai_intervention=True)
        self.db.expire_all()
        self.assertEqual(self.db.get(AutonomousProcessingRun,run_id).stato,'completato')
        self.assertEqual(self.db.query(DocumentAiUsage).count(),0)

    def test_full_run_new_ddt_matches_manual_historic_certificate_without_ai(self):
        cert=self.doc(manual=True); source=self.row(cert,with_ddt=True)
        ddt=self.doc('ddt'); target=self.row(ddt,method='chatgpt',confirmed=False)
        self.run_fixture(ddt)
        target=self.db.get(AcquisitionRow,target.id)
        self.assertEqual(target.document_certificato_id,cert.id)
        self.assertEqual(target.certificate_match.stato,'proposto')
        self.assertEqual(self.db.get(AcquisitionRow,source.id).document_certificato_id,cert.id)

    def test_full_run_manual_certificate_arrives_after_ddt_and_merges(self):
        target=self.row(self.doc('ddt'),method='chatgpt',confirmed=False)
        cert=self.doc(manual=True); source=self.row(cert)
        source_id=source.id
        self.run_fixture(None,[cert])
        target=self.db.get(AcquisitionRow,target.id)
        self.assertEqual(target.document_certificato_id,cert.id)
        self.assertIsNone(self.db.get(AcquisitionRow,source_id))
        self.assertTrue(automatic_ai_disabled(self.db,cert))

    def test_full_run_manual_ddt_uses_saved_fields_not_vision_or_regex(self):
        cert=self.doc(manual=True); self.row(cert,with_ddt=True)
        ddt=self.doc('ddt',manual=True); target=self.row(ddt)
        before={v.campo:(v.valore_grezzo,v.valore_finale,v.metodo_lettura) for v in target.values}
        with patch.object(s,'extract_core_fields',side_effect=AssertionError('Do not reread manual DDT')):
            self.run_fixture(ddt)
        target=self.db.get(AcquisitionRow,target.id)
        self.assertEqual(target.document_certificato_id,cert.id)
        self.assertEqual({v.campo:(v.valore_grezzo,v.valore_finale,v.metodo_lettura) for v in target.values if v.blocco=='ddt'},before)

    def test_preview_does_not_offer_manual_documents_for_one_off_ai_read(self):
        from scripts.prepare_certificate_ai_reuse import preview
        cert=self.doc(); self.row(cert)
        ddt=self.doc('ddt',manual=True); self.row(ddt)
        result=preview(self.db)
        self.assertEqual(result['documents'],[{'document_id':cert.id,'status':'manual_no_automatic_ai'}])
        self.assertEqual(result['manual_ddt'][0]['document_id'],ddt.id)

    def test_confirm_incompatible_field_then_explicit_detach_keeps_user_intent_and_hidden_fields(self):
        cert=self.doc(manual=True); row=self.row(cert,with_ddt=True)
        for field,value in {'numero_certificato_ddt':'EEP70000-44444444','colata':'CAST1',
                'diametro':'33','lega':'6082 F','peso':'120','ddt':'D1','ordine':'O1'}.items():
            self.db.add(ReadValue(acquisition_row_id=row.id,blocco='ddt',campo=field,valore_finale=value,
                stato='confermato',metodo_lettura='chatgpt',fonte_documentale='ddt'))
        self.db.add(ReadValue(acquisition_row_id=row.id,blocco='match',campo='articolo_certificato',
            valore_finale='INTERNAL_CODE',stato='confermato',metodo_lettura='utente',fonte_documentale='certificato'))
        self.db.add(CertificateMatch(acquisition_row_id=row.id,document_certificato_id=cert.id,
            stato='confermato',fonte_proposta='utente'));self.db.commit()
        response=s.confirm_document_side_fields(self.db,row=row,actor_id=None,
            payload=DocumentSideFieldsConfirmRequest(side='certificato',fields={
                'cdq':'EEP70000-44444444','colata':'OTHER','diametro':'33','lega_base':'6082 F',
                'peso':'120','ddt':'D1','ordine':'O1'}))
        self.assertEqual(response.document_certificato_id,cert.id)
        self.db.expire(row,['certificate_match'])
        self.assertEqual(row.certificate_match.stato,'proposto')
        self.assertEqual(row.certificate_match.fonte_proposta,'utente')
        result=s.detach_document_match(self.db,row=row,actor_id=None,payload=DocumentMatchDetachRequest())
        target=self.db.get(AcquisitionRow,result.ddt_row.id)
        separate=self.db.get(AcquisitionRow,result.certificate_row.id)
        self.assertIsNone(target.document_certificato_id)
        self.assertEqual(next(v.valore_finale for v in separate.values if v.campo=='articolo_certificato'),'INTERNAL_CODE')
        self.assertTrue(automatic_ai_disabled(self.db,cert))
        self.assertFalse(s._has_manual_rematch_candidate(self.db,target,[cert]))
        self.assertNotIn(target.id,{p.row_id for p in s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id})})

    def test_manual_candidate_does_not_win_over_competing_ai_candidate_by_default(self):
        cert=self.doc(manual=True);self.row(cert,with_ddt=True)
        ai_doc=self.doc(); ai_row=self.row(ai_doc,with_ddt=True,method='chatgpt')
        self.db.add(DocumentEvidence(document_id=ai_doc.id,blocco='match',tipo_evidenza='ai_payload',metodo_estrazione='chatgpt',
            testo_grezzo=json.dumps({'core':{'cert_number':'EEP70000','job_number':'44444444',
                'cast_number':'CAST1','alloy_raw':'6082 F','diameter_raw':'33','weight':'120'}})))
        ddt=self.doc('ddt');target=self.row(ddt,method='chatgpt',confirmed=False);self.db.commit()
        self.run_fixture(ddt)
        self.assertIsNone(self.db.get(AcquisitionRow,target.id).document_certificato_id)
        value=self.db.query(ReadValue).filter_by(acquisition_row_id=ai_row.id,campo='colata_certificato').one()
        value.valore_finale='OTHER';value.metodo_lettura='utente';self.db.commit()
        self.run_fixture(ddt)
        self.assertEqual(self.db.get(AcquisitionRow,target.id).document_certificato_id,cert.id)
        self.assertEqual(value.valore_finale,'OTHER')

    def metalba_ai_pair(self):
        self.supplier.ragione_sociale='Metalba S.p.A.';self.db.commit()
        cert=self.doc()
        self.db.add(DocumentEvidence(document_id=cert.id,blocco='match',tipo_evidenza='ai_payload',metodo_estrazione='chatgpt',
            testo_grezzo=json.dumps(metalba_raw())))
        source=self.row(cert,{'numero_certificato_certificato':'26-1791','lega_certificato':'6082F F',
            'colata_certificato':'26139A','diametro_certificato':'33','peso_certificato':'2827',
            'ordine_cliente_certificato':'169/26'},method='chatgpt',with_ddt=True)
        ddt=self.doc('ddt')
        fields={'numero_certificato_ddt':'26-1791','lega':'6082F F','colata':'26139A','diametro':'33',
            'peso':'2827','ordine':'169/26','vs_rif':'169/26','ddt':'DDT1'}
        target=self.row(ddt,fields,method='chatgpt',confirmed=False)
        target.cdq='26-1791';target.lega_base='6082F F';target.colata='26139A';target.diametro='33'
        target.peso='2827';target.ordine='169/26';target.ddt='DDT1';self.db.commit()
        payload=cached_payload(self.db,cert,'metalba')
        candidate=s._score_certificate_candidate(self.db,row=target,certificate_document=cert,
            ddt_certificate_number=target.cdq,row_ddt_values=fields,certificate_ai_cache={cert.id:payload},ai_only_mode=True)
        self.assertIsNotNone(candidate)
        return cert,source,ddt,target,payload

    def test_old_ai_raw_cannot_recreate_a_match_rejected_by_user_field_correction(self):
        cert,source,ddt,target,payload=self.metalba_ai_pair()
        value=self.db.query(ReadValue).filter_by(acquisition_row_id=source.id,campo='colata_certificato').one()
        value.valore_finale='OTHER_CAST';value.metodo_lettura='utente';self.db.commit()
        self.assertIsNone(manual_document_reason(self.db,cert))  # AI document with a manual override, not manual entry
        self.assertTrue(s._has_manual_rematch_candidate(self.db,target,[cert],certificate_ai_cache={cert.id:payload}))
        self.run_fixture(ddt)
        self.assertIsNone(self.db.get(AcquisitionRow,target.id).document_certificato_id)
        self.assertEqual(value.valore_finale,'OTHER_CAST')

    def test_detach_block_is_also_honoured_by_batch_initial_proposal_not_only_rematch(self):
        cert,source,ddt,target,_=self.metalba_ai_pair()
        self.db.add(ManualMatchBlock(document_ddt_id=ddt.id,document_certificato_id=cert.id,
            source_row_id=target.id,certificate_row_id=source.id,attivo=True));self.db.commit()
        self.assertEqual(s._automatic_certificate_candidates(self.db,target,[cert]),[])
        self.run_fixture(ddt)
        self.assertIsNone(self.db.get(AcquisitionRow,target.id).document_certificato_id)

    def assert_metalba_correction_prevents_rematch(self, field, corrected):
        cert,source,ddt,target,_=self.metalba_ai_pair()
        cert.pages[0].ocr_text='Certificato Nr. 26-1791'
        value=next(v for v in source.values if v.campo==field)
        value.valore_finale=corrected;value.metodo_lettura='utente';self.db.commit()
        self.run_fixture(ddt)
        self.assertIsNone(self.db.get(AcquisitionRow,target.id).document_certificato_id)
        self.assertEqual(value.valore_finale,corrected)

    def test_metalba_manual_alloy_correction_is_not_bypassed_by_rematch(self):
        self.assert_metalba_correction_prevents_rematch('lega_certificato','7075 T6')

    def test_metalba_manual_weight_correction_is_not_bypassed_by_rematch(self):
        self.assert_metalba_correction_prevents_rematch('peso_certificato','9999')

    def test_metalba_manual_order_correction_is_not_bypassed_by_rematch(self):
        self.assert_metalba_correction_prevents_rematch('ordine_cliente_certificato','DIFFERENT')

    def test_lst03_interpretation_remains_a_valid_source_not_a_manual_alloy_conflict(self):
        cert,source,_,target,_=self.metalba_ai_pair()
        value=next(v for v in source.values if v.campo=='lega_certificato')
        value.valore_grezzo='6082F F';value.valore_finale='6082H F'
        value.metodo_lettura=s.METALBA_LST03_METHOD
        source.lega_base='6082H F';self.db.commit()
        plans=s._plan_cross_run_auto_rematch(db=self.db,supplier_ids={self.supplier.id})
        self.assertIn(target.id,{p.row_id for p in plans})
        self.assertEqual(s._build_row_certificate_bridge(source).value('lega'),'6082F F')

    def weak_and_strong_sources(self):
        weak=self.doc(manual=True)
        self.row(weak,{'diametro_certificato':'33','peso_certificato':'120',
                      'ordine_cliente_certificato':'O1'},with_ddt=True)
        strong=self.doc(manual=True);strong_row=self.row(strong,with_ddt=True)
        target=self.row(strong_row.ddt_document,{'numero_certificato_ddt':'EEP70000-44444444',
            'colata':'CAST1','diametro':'33','lega':'6082 F','peso':'120','ordine':'O1'},
            method='chatgpt',confirmed=False)
        return weak,strong,strong_row,target

    def test_protected_best_source_does_not_promote_a_weak_candidate(self):
        _,_,strong_row,target=self.weak_and_strong_sources()
        run=AutonomousProcessingRun();self.db.add(run);self.db.commit()
        with sessionmaker(bind=self.engine,autoflush=False)() as run_db:
            run_db.info[s.AI_PROCESSING_SESSION_RUN_KEY]=run.id
            s._run_cross_run_auto_rematch(db=run_db,supplier_ids={self.supplier.id},actor_id=None,
                run_id=run.id,protected_row_ids={strong_row.id})
        self.db.expire_all()
        self.assertIsNone(self.db.get(AcquisitionRow,target.id).document_certificato_id)

    def test_completed_row_is_still_a_read_only_source_in_the_same_batch(self):
        _,strong,strong_row,target=self.weak_and_strong_sources()
        self.run_fixture(strong_row.ddt_document)
        self.assertEqual(self.db.get(AcquisitionRow,target.id).document_certificato_id,strong.id)
        self.assertEqual(self.db.get(AcquisitionRow,strong_row.id).document_certificato_id,strong.id)

    def test_one_manual_certificate_completes_two_preexisting_ddt_rows(self):
        ddt=self.doc('ddt')
        targets=[self.row(ddt,method='chatgpt',confirmed=False) for _ in range(2)]
        cert=self.doc(manual=True);source=self.row(cert);source_id=source.id
        self.run_fixture(None,[cert])
        self.assertIsNone(self.db.get(AcquisitionRow,source_id))
        self.assertEqual([self.db.get(AcquisitionRow,r.id).document_certificato_id for r in targets],
                         [cert.id,cert.id])
        self.assertTrue(automatic_ai_disabled(self.db,cert))

    def test_two_new_ddt_rows_can_reuse_the_source_absorbed_by_the_first_merge(self):
        cert=self.doc(manual=True);source=self.row(cert);source_id=source.id
        ddt=self.doc('ddt')
        targets=[self.row(ddt,method='chatgpt',confirmed=False) for _ in range(2)]
        self.run_fixture(ddt)
        self.assertIsNone(self.db.get(AcquisitionRow,source_id))
        self.assertEqual([self.db.get(AcquisitionRow,r.id).document_certificato_id for r in targets],
                         [cert.id,cert.id])

    def test_absorbing_a_source_keeps_detach_blocks_for_other_ddt_rows(self):
        cert=self.doc(manual=True);self.row(cert)
        blocked=self.row(self.doc('ddt'),method='chatgpt',confirmed=False)
        targets=[self.row(self.doc('ddt'),method='chatgpt',confirmed=False) for _ in range(2)]
        self.db.add(ManualMatchBlock(document_ddt_id=blocked.document_ddt_id,
            document_certificato_id=cert.id,source_row_id=blocked.id,attivo=True));self.db.commit()
        self.run_fixture(None,[cert])
        self.assertIsNone(self.db.get(AcquisitionRow,blocked.id).document_certificato_id)
        self.assertEqual([self.db.get(AcquisitionRow,r.id).document_certificato_id for r in targets],
                         [cert.id,cert.id])

    def test_validated_coupled_source_is_reused_without_reopening_or_rewriting_it(self):
        cert=self.doc(manual=True);source=self.row(cert,with_ddt=True)
        source.validata_finale=True;self.db.commit()
        before={v.campo:(v.valore_finale,v.metodo_lettura,v.stato) for v in source.values}
        ddt=self.doc('ddt');target=self.row(ddt,method='chatgpt',confirmed=False)
        self.run_fixture(ddt)
        self.assertEqual(self.db.get(AcquisitionRow,target.id).document_certificato_id,cert.id)
        source=self.db.get(AcquisitionRow,source.id)
        self.assertTrue(source.validata_finale)
        self.assertEqual({v.campo:(v.valore_finale,v.metodo_lettura,v.stato) for v in source.values},before)


if __name__=='__main__':
    unittest.main()
