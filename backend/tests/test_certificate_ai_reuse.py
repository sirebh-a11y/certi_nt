"""Offline regression tests: no app DB, no Alpha and no paid API calls."""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition import certificate_ai_reuse as reuse
from app.modules.acquisition import service as s
from app.modules.acquisition import leichtmetall_type_workflow as type_workflow
from app.modules.acquisition.document_type_guard import DocumentTypeReviewRequired
from app.modules.acquisition.ai_usage import usage_scope
from app.modules.acquisition.models import (
    AcquisitionRow, Document, DocumentAiExtraction, DocumentAiUsage,
    DocumentEvidence, DocumentPage, ReadValue,
)
from app.modules.suppliers.models import Supplier


def metalba_raw(number="26-1791", weight="2827"):
    return {
        "core": {"numero_certificato": number, "ordine_cliente": "169/26", "lega": "6082F F",
                 "colata": "26139A", "peso_netto": weight, "commessa_raw": "26/0903/1",
                 "product_description_raw": "ESTRUSO A.A. 6082F F BARRA TONDA DIAM 33 mm", "diameter_raw": "33 mm"},
        "chemistry_raw": {"Si": "1.0713", "Mg": "0.7664"},
        "mechanical_raw": {"measured_rows": [{"Rm":"409","Rp0.2":"378","A%":"8,3"},
                                            {"Rm":"396","Rp0.2":"365","A%":"11,1"}]},
        "notes_raw": {}, "mechanical_requirement_raw": {"customer_requirement_quote_raw":"Materiale secondo specifica LST03"},
    }


class CertificateAiReuseTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.supplier = Supplier(ragione_sociale="Metalba S.p.A.")
        self.db.add(self.supplier)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def document(self, key="first", supplier=None):
        doc = Document(tipo_documento="certificato", nome_file_originale=key+".pdf", storage_key=key+".pdf",
                       hash_file=hashlib.sha256(key.encode()).hexdigest(), fornitore_id=(supplier or self.supplier).id)
        self.db.add(doc)
        self.db.flush()
        page = DocumentPage(document_id=doc.id, numero_pagina=1, testo_estratto="", immagine_pagina_storage_key="unused.png")
        self.db.add(page)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def legacy(self, doc, raw):
        e = DocumentEvidence(document_id=doc.id, document_page_id=doc.pages[0].id,
                             blocco="match", tipo_evidenza="ai_payload", metodo_estrazione="chatgpt",
                             testo_grezzo=json.dumps(raw))
        self.db.add(e)
        self.db.commit()
        return e

    def call(self, doc, cache=None):
        return s._get_supplier_certificate_ai_payload(self.db, supplier_key="metalba",
            certificate_document=doc, openai_api_key="unused", certificate_ai_cache=cache)

    @contextmanager
    def live_reader(self, raw=None):
        raw = raw or metalba_raw()
        reader = Mock(return_value=deepcopy(raw))
        with patch.multiple(s,
            _ensure_document_page_images=lambda db, doc: doc,
            _build_certificate_safe_crops=lambda pages, **kw: {"page1_core_context":{
                "page_id":pages[0].id,"page_number":1,"role":"certificate_core_context","storage_key":"unused.png"}},
            _extract_metalba_certificate_payload_from_openai=reader):
            yield reader

    def test_new_read_survives_next_run_and_mutation_isolation(self):
        doc = self.document()
        with self.live_reader() as patched:
            first = self.call(doc, {})
            first['match_values']['peso_certificato'] = 'WRONG_OTHER_ROW'
            self.db.commit()
            self.db.close()
            self.db = self.Session()
            doc = self.db.get(Document, doc.id)
            second = self.call(doc, {})
            self.assertEqual(second['match_values']['peso_certificato'], '2827')
            patched.assert_called_once()
        self.assertEqual(self.db.query(DocumentAiExtraction).count(), 1)
        self.assertEqual(self.db.query(AcquisitionRow).count(), 0)

    def test_legacy_raw_reused_without_images_or_ai(self):
        doc = self.document()
        evidence = self.legacy(doc, metalba_raw())
        with (patch.object(s, '_extract_metalba_certificate_payload_from_openai', side_effect=AssertionError('AI forbidden')),
              patch.object(s, '_build_certificate_safe_crops', side_effect=AssertionError('Images forbidden'))):
            payload = self.call(doc, {})
        self.assertEqual(payload['match_values']['numero_certificato_certificato'], '26-1791')
        self.assertEqual(self.db.query(DocumentAiExtraction).one().source_evidence_id, evidence.id)

    def test_change_hash_never_reuses_old_json_or_run_cache(self):
        doc = self.document()
        self.legacy(doc, metalba_raw())
        memory = {}
        self.call(doc, memory)
        doc.hash_file = hashlib.sha256(b'REPLACED_CONTENT').hexdigest()
        self.db.commit()
        with self.live_reader(metalba_raw(number='26-9999')) as patched:
            payload = self.call(doc, memory)
        self.assertEqual(payload['match_values']['numero_certificato_certificato'], '26-9999')
        patched.assert_called_once()
        self.assertEqual(self.db.query(DocumentAiExtraction).count(), 2)

    def test_same_supplier_different_documents_never_share_cache(self):
        one, two = self.document('one'), self.document('two')
        self.legacy(one, metalba_raw('26-1111'))
        self.legacy(two, metalba_raw('26-2222'))
        self.assertEqual(self.call(one)['match_values']['numero_certificato_certificato'], '26-1111')
        self.assertEqual(self.call(two)['match_values']['numero_certificato_certificato'], '26-2222')

    def test_optional_absences_and_incomplete_mechanics_do_not_trigger_rereads(self):
        doc = self.document()
        raw = metalba_raw()
        raw['mechanical_raw'] = {'measured_rows':[]}
        raw['chemistry_raw'] = {}
        self.legacy(doc, raw)
        with patch.object(s, '_extract_metalba_certificate_payload_from_openai', side_effect=AssertionError('AI forbidden')):
            for _ in range(3):
                self.assertEqual(self.call(doc, {})['properties'], {})

    def test_explicit_reread_once_per_action_not_per_block(self):
        doc = self.document()
        self.legacy(doc, metalba_raw())
        self.call(doc)
        with self.live_reader(metalba_raw(weight='3000')) as patched:
            with reuse.explicit_refresh(doc.id):
                self.assertEqual(self.call(doc)['match_values']['peso_certificato'], '3000')
                self.call(doc)
                self.call(doc)
            patched.assert_called_once()

    def test_loading_does_not_rewrite_manual_fields_or_validation(self):
        doc = self.document()
        self.legacy(doc, metalba_raw())
        row = AcquisitionRow(document_certificato_id=doc.id, fornitore_id=self.supplier.id, validata_finale=True)
        self.db.add(row); self.db.flush()
        value = ReadValue(acquisition_row_id=row.id, blocco='match', campo='lega_certificato',
                          valore_grezzo='6082H', valore_finale='6082H', stato='confermato',
                          metodo_lettura='utente', fonte_documentale='certificato')
        self.db.add(value); self.db.commit()
        self.call(doc)
        self.assertEqual(value.valore_finale, '6082H')
        self.assertTrue(row.validata_finale)

    def manual_source(self, doc, weight):
        row = AcquisitionRow(document_certificato_id=doc.id, fornitore_id=self.supplier.id,
                             cdq='26-1791', lega_base='HIGH_LEVEL_FROM_DDT', peso='HIGH_LEVEL_FROM_DDT')
        self.db.add(row); self.db.flush()
        for field,val in {'numero_certificato_certificato':'26-1791','ordine_cliente_certificato':'169/26',
                          'lega_certificato':'6082F F','diametro_certificato':'33','colata_certificato':'26139A',
                          'peso_certificato':weight}.items():
            self.db.add(ReadValue(acquisition_row_id=row.id, blocco='match', campo=field,
                        valore_grezzo=val,valore_finale=val,stato='confermato',metodo_lettura='utente',fonte_documentale='certificato'))
        self.db.commit()
        return row

    def test_multiple_rows_do_not_become_one_document_wide_weight(self):
        doc = self.document()
        self.legacy(doc, metalba_raw(weight='10971'))
        one, two = self.manual_source(doc, '2438'), self.manual_source(doc, '8533')
        with self.live_reader(metalba_raw(weight='10971')) as reader:
            payload=self.call(doc)
            self.assertEqual(payload['match_values']['peso_certificato'],'10971')
            self.call(doc,{})
            reader.assert_not_called()
        for row,weight in ((one,'2438'),(two,'8533')):
            actual=self.db.query(ReadValue).filter_by(acquisition_row_id=row.id,campo='peso_certificato').one()
            self.assertEqual(actual.valore_finale,weight)

    def test_document_delete_cascades_cache_and_retains_usage_without_document(self):
        doc = self.document()
        self.legacy(doc, metalba_raw())
        self.call(doc)
        # Remove only fixture evidence before deleting its fixture document.
        self.db.query(DocumentEvidence).filter_by(document_id=doc.id).delete()
        usage = DocumentAiUsage(document_id=doc.id, model='test', response_status='completed',input_tokens=1)
        self.db.add(usage); self.db.commit()
        self.db.delete(doc); self.db.commit(); self.db.expire_all()
        self.assertEqual(self.db.query(DocumentAiExtraction).count(), 0)
        self.assertIsNone(self.db.query(DocumentAiUsage).one().document_id)

    def test_usage_actual_counts_and_unknown_timeout_not_zero(self):
        doc = self.document()
        self.db.info['acquisition_ai_processing_run_id'] = 123
        response = SimpleNamespace(id='resp_test',model='gpt-5.5',status='completed',usage=SimpleNamespace(
            input_tokens=100,output_tokens=40,total_tokens=140,
            input_tokens_details=SimpleNamespace(cached_tokens=0),output_tokens_details=SimpleNamespace(reasoning_tokens=10)))
        client = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=response)))
        with usage_scope(self.db, doc):
            self.assertIs(s._create_openai_response(client,model='gpt-5.5'), response)
            client.responses.create.side_effect = TimeoutError('not recorded in ledger')
            with self.assertRaises(TimeoutError):
                s._create_openai_response(client,model='gpt-5.5')
        actual, failed = self.db.query(DocumentAiUsage).order_by(DocumentAiUsage.id).all()
        self.assertEqual((actual.input_tokens,actual.output_tokens,actual.cached_input_tokens,actual.reasoning_tokens), (100,40,0,10))
        self.assertEqual(actual.run_id,123)
        self.assertIsNone(failed.total_tokens)
        self.assertEqual(failed.error_type,'TimeoutError')

    def test_lst03_uses_documentary_alloy_without_overwriting_interpreted_value(self):
        doc=self.document()
        row=self.manual_source(doc,'2827')
        value=self.db.query(ReadValue).filter_by(acquisition_row_id=row.id,campo='lega_certificato').one()
        value.metodo_lettura='metalba_lst03';value.valore_grezzo='6082F F';value.valore_finale='6082H F'
        self.db.commit()
        with self.live_reader():
            payload=self.call(doc)
        self.assertEqual(payload['match_values']['lega_certificato'],'6082F F')
        self.assertEqual(value.valore_finale,'6082H F')

    def test_corrupt_payload_and_wrong_page_are_not_silently_accepted(self):
        doc=self.document()
        self.legacy(doc,metalba_raw())
        self.call(doc)
        cached=self.db.query(DocumentAiExtraction).one()
        payload=json.loads(cached.payload_json)
        payload['chemistry']['Si']['page_id']='not-a-page'
        cached.payload_json=json.dumps(payload);self.db.commit()
        with patch.object(s,'_extract_metalba_certificate_payload_from_openai',side_effect=AssertionError('AI forbidden')):
            recovered=self.call(doc)
        self.assertEqual(recovered['chemistry']['Si']['page_id'],doc.pages[0].id)

    def leichtmetall(self):
        supplier=Supplier(ragione_sociale='Leichtmetall Aluminium Giesserei Hannover GmbH')
        self.db.add(supplier);self.db.commit()
        doc=self.document('leicht',supplier)
        doc.numero_pagine=1;self.db.commit()
        raw=metalba_raw()
        raw['core'].update(numero_certificato='95094',colata='95094',po_no='169',charge_cast_no='95094',
                           alloy_raw='6082 F',diameter_raw='33',weight_raw='2827')
        raw['document_check']={'detected_type':'certificato','matches_assigned':True,
                               'evidence':[{'page_number':1,'quote':'Inspection certificate'}]}
        return doc,raw

    def test_leichtmetall_preflight_uses_successful_read_without_second_ai_call(self):
        doc,raw=self.leichtmetall()
        with self.live_reader():
            with patch.object(s,'_extract_leichtmetall_certificate_payload_from_openai',return_value=raw) as reader:
                s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=doc,openai_api_key='unused')
                cache={}
                accepted,failed=type_workflow.preflight_documents(self.db,[doc],explicit_ids={doc.id},
                    certificate_ai_cache=cache,api_key='unused',actor_id=None,actor_email='test')
                self.assertEqual(accepted,[doc]);self.assertFalse(failed)
                self.assertIn(doc.id,cache)
                reader.assert_called_once()

    def test_type_block_always_wins_over_in_memory_cache(self):
        doc,raw=self.leichtmetall()
        self.legacy(doc,raw)
        payload=reuse.cached_payload(self.db,doc,'leichtmetall')
        self.db.info['leichtmetall_type_blocked']={doc.id}
        with self.assertRaises(DocumentTypeReviewRequired):
            s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=doc,
                openai_api_key='unused',certificate_ai_cache={doc.id:payload})

    def test_incomplete_page_set_cannot_bypass_type_guard_via_cache(self):
        doc,raw=self.leichtmetall();self.legacy(doc,raw)
        payload=reuse.cached_payload(self.db,doc,'leichtmetall',persist_legacy=True)
        doc.numero_pagine=2;self.db.commit()
        self.assertIsNone(reuse.cached_payload(self.db,doc,'leichtmetall'))
        with self.assertRaises(DocumentTypeReviewRequired),patch.object(s,'_extract_leichtmetall_certificate_payload_from_openai',
                side_effect=AssertionError('AI must not read incomplete pages')):
            s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=doc,
                openai_api_key='unused',certificate_ai_cache={doc.id:payload})

    def test_successful_guarded_reread_supersedes_previous_failed_check(self):
        doc,raw=self.leichtmetall()
        self.legacy(doc,raw)
        reuse.cached_payload(self.db,doc,'leichtmetall')
        self.db.add(DocumentEvidence(document_id=doc.id,blocco='documento',tipo_evidenza=type_workflow.EVIDENCE_TYPE,
            metodo_estrazione='chatgpt',testo_grezzo=json.dumps({'decision':'da_verificare'})))
        self.db.commit()
        self.assertIsNone(reuse.cached_payload(self.db,doc,'leichtmetall'))
        with self.live_reader():
            with patch.object(s,'_extract_leichtmetall_certificate_payload_from_openai',return_value=raw) as reader:
                with reuse.explicit_refresh(doc.id):
                    s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=doc,openai_api_key='unused')
                self.assertIsNotNone(reuse.cached_payload(self.db,doc,'leichtmetall'))
                reader.assert_called_once()

    def test_failed_explicit_type_reread_cannot_resurrect_previous_cache(self):
        doc,raw=self.leichtmetall()
        self.legacy(doc,raw)
        reuse.cached_payload(self.db,doc,'leichtmetall',persist_legacy=True)
        with self.live_reader(),patch.object(s,'_extract_leichtmetall_certificate_payload_from_openai',
                side_effect=DocumentTypeReviewRequired('misto',check={'detected_type':'misto'})):
            with reuse.explicit_refresh(doc.id),self.assertRaises(DocumentTypeReviewRequired):
                s._get_leichtmetall_certificate_ai_payload(self.db,certificate_document=doc,openai_api_key='unused')
        self.assertEqual(self.db.query(DocumentAiExtraction).count(),1)
        self.assertIsNone(reuse.cached_payload(self.db,doc,'leichtmetall'))

    def test_cache_failure_cannot_make_empty_read_successful(self):
        doc=self.document()
        with self.live_reader({'core':{}}) as reader:
            payload=self.call(doc)
        self.assertFalse(any(payload['match_values'].values()))
        self.assertEqual(self.db.query(DocumentAiExtraction).count(),0)
        reader.assert_called_once()

    def test_paid_result_retry_repeats_only_save_not_ai(self):
        doc=self.document()
        save=reuse._save
        with self.live_reader() as reader,patch.object(reuse,'_save',side_effect=[RuntimeError('write unavailable'),None]) as write:
            payload=self.call(doc,{})
        reader.assert_called_once()
        self.assertEqual(write.call_count,2)
        self.assertNotIn('_reuse_persistence_pending',payload)

    def test_persistent_save_failure_retains_paid_result_for_same_run(self):
        doc=self.document();memory={}
        with self.live_reader() as reader:
            with patch.object(reuse,'_save',side_effect=RuntimeError('write unavailable')):
                with self.assertRaisesRegex(s.HTTPException,''):
                    self.call(doc,memory)
            self.assertTrue(memory[doc.id]['_reuse_persistence_pending'])
            self.call(doc,memory)
            reader.assert_called_once()
        self.assertEqual(self.db.query(DocumentAiExtraction).count(),1)

    def test_supplier_change_cannot_reinterpret_an_old_json_as_a_new_reader(self):
        doc=self.document();self.legacy(doc,metalba_raw());self.call(doc)
        other=Supplier(ragione_sociale='Other supplier')
        self.db.add(other);self.db.flush();doc.fornitore_id=other.id;self.db.commit()
        self.assertIsNone(reuse.cached_payload(self.db,doc,'metalba'))

    def test_legacy_crop_names_match_existing_reader_and_impol_quote_keeps_page(self):
        doc=self.document()
        for key in ('metalba','impol','leichtmetall','aww','neuman','arconic_hannover','grupa_kety','zalco','aluminium_bozen'):
            captured=[]
            name=f'_normalize_{key}_certificate_ai_payload'
            with patch.object(s,name,side_effect=lambda images,raw:(captured.append(images) or {'match_values':{}})):
                reuse._normalizer_payload(doc,key,{'core':{}})
            expected='page1_core_context' if key=='aluminium_bozen' else 'page1_core_page'
            self.assertEqual(next(iter(captured[0])),expected)
        page2=DocumentPage(document_id=doc.id,numero_pagina=2,testo_estratto='Material free from radioactive contamination',immagine_pagina_storage_key='unused2.png')
        self.db.add(page2);self.db.commit();self.db.refresh(doc)
        raw=metalba_raw()
        raw['notes_raw']['nota_radioactive_free_raw']='Material free from radioactive contamination'
        payload=reuse._normalizer_payload(doc,'impol',raw)
        found=[v for v in payload['notes'].values() if 'radioactive' in v.get('snippet','').lower()]
        self.assertTrue(found)
        self.assertTrue(all(v['page_id']==page2.id for v in found))

    def test_persistent_layer_preserves_all_blocks_for_every_supported_reader(self):
        for key in ('metalba','impol','leichtmetall','aww','neuman','arconic_hannover','grupa_kety','zalco','aluminium_bozen'):
            with self.subTest(reader=key):
                doc=self.document('persist-'+key)
                raw=metalba_raw()
                raw['document_check']={'detected_type':'certificato','matches_assigned':True,
                                       'evidence':[{'page_number':1,'quote':'Inspection certificate'}]}
                expected=s._normalize_metalba_certificate_ai_payload(
                    {'page1':{'page_id':doc.pages[0].id,'page_number':1}},raw)
                called=Mock(return_value=deepcopy(expected))
                read=reuse.reuse_certificate_payload(key)(called)
                first=read(self.db,certificate_document=doc,openai_api_key='unused',certificate_ai_cache={})
                self.db.commit()
                second=read(self.db,certificate_document=doc,openai_api_key='unused',certificate_ai_cache={})
                called.assert_called_once()
                for block in ('match_values','supplier_fields','core_fields','chemistry','properties','notes','mechanical_requirement'):
                    self.assertEqual(first.get(block),second.get(block))

    def test_manual_interpreted_alloy_without_original_raw_is_never_sent_to_ai(self):
        doc=self.document();row=self.manual_source(doc,'2827')
        value=self.db.query(ReadValue).filter_by(acquisition_row_id=row.id,campo='lega_certificato').one()
        value.valore_grezzo='6082H';value.valore_finale='6082H';self.db.commit()
        with self.live_reader() as reader:
            for _ in range(2):
                with self.assertRaises(HTTPException) as refused:
                    self.call(doc,{})
                self.assertEqual(refused.exception.status_code,409)
            reader.assert_not_called()
        self.assertEqual(self.db.query(DocumentAiExtraction).count(),0)
        self.assertEqual(value.valore_finale,'6082H')

    def test_later_manual_row_correction_never_contaminates_document_cache(self):
        doc=self.document();row=self.manual_source(doc,'2827')
        self.legacy(doc, metalba_raw())
        with self.live_reader() as reader:
            self.call(doc)
            value=self.db.query(ReadValue).filter_by(acquisition_row_id=row.id,campo='peso_certificato').one()
            value.valore_finale='3000';self.db.commit()
            again=self.call(doc,{})
            reader.assert_not_called()
        self.assertEqual(again['match_values']['peso_certificato'],'2827')
        self.assertEqual(value.valore_finale,'3000')

    def test_old_partial_arconic_identity_does_not_reread_a_manually_fixed_number(self):
        doc=self.document()
        raw={'core':{'cert_number':'EEP75132','cast_job_number':'C70025341496','alloy_raw':'6082 F','diameter_raw':'98'}}
        self.legacy(doc,raw)
        row=self.manual_source(doc,'3606')
        value=self.db.query(ReadValue).filter_by(acquisition_row_id=row.id,campo='numero_certificato_certificato').one()
        value.valore_finale='EEP75132-44475952';self.db.commit()
        self.assertIsNotNone(reuse.cached_payload(self.db,doc,'arconic_hannover'))
        complete=deepcopy(raw);complete['core']['cast_job_number']='C70025341496/44475952'
        with self.live_reader(),patch.object(s,'_extract_arconic_hannover_certificate_payload_from_openai',return_value=complete) as reader:
            first=s._get_arconic_hannover_certificate_ai_payload(self.db,certificate_document=doc,openai_api_key='unused')
            second=s._get_arconic_hannover_certificate_ai_payload(self.db,certificate_document=doc,openai_api_key='unused',certificate_ai_cache={})
            reader.assert_not_called()
        self.assertEqual(first['match_values']['numero_certificato_certificato'],'EEP75132')
        self.assertEqual(value.valore_finale,'EEP75132-44475952')
        self.assertEqual(second['match_values'],first['match_values'])


if __name__ == '__main__':
    unittest.main()
