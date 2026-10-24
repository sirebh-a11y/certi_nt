import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.modules.acquisition.arconic_identity import recover_identity
from app.modules.acquisition import service as s


class ArconicIdentityRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.first = {'core': {'cert_number': 'EEP73061', 'cast_job_number': 'C70025341313'},
                      'chemistry_raw': {'Si': '1.03'}, 'mechanical_raw': {'measured_rows': [{'Rm': '386'}]}}
        self.second = {'core': {'cert_number': 'EEP73061', 'cast_job_number': 'C70025341313/44262209'}}

    def test_missing_job_recovered_without_touching_other_fields_or_original(self):
        original = copy.deepcopy(self.first)
        result = recover_identity(self.first, kind='certificate', reread=lambda: self.second)
        self.assertEqual(self.first, original)
        self.assertEqual(result['chemistry_raw'], original['chemistry_raw'])
        self.assertEqual(result['mechanical_raw'], original['mechanical_raw'])
        self.assertEqual(result['_identity_recovery']['first'], original)
        self.assertEqual(result['core'], self.second['core'])

    def test_complete_certificate_does_not_call_ai_again(self):
        retry = Mock()
        result = recover_identity(self.second, kind='certificate', reread=retry)
        self.assertIs(result, self.second)
        retry.assert_not_called()

    def test_failed_retry_is_non_blocking(self):
        for failure in (TimeoutError(), ValueError('invalid JSON'), RuntimeError('API error')):
            retry = Mock(side_effect=failure)
            self.assertIs(recover_identity(self.first, kind='certificate', reread=retry), self.first)
            retry.assert_called_once()

    def test_conflicting_root_cast_and_job_not_applied(self):
        variants = [dict(cert_number='EEP99999', cast_job_number='C70025341313/44262209'),
                    dict(cert_number='EEP73061', cast_job_number='C99999999999/44262209'),
                    dict(cert_number='EEP73061', cast_job_number='C70025341313/11111111')]
        for core in variants:
            first = copy.deepcopy(self.first)
            if core['cast_job_number'].endswith('/11111111'):
                first['core']['cast_job_number'] = 'C70025341313 job 44262209'  # malformed first reading
            result = recover_identity(first, kind='certificate', reread=lambda: {'core': core})
            self.assertEqual(result['core'], first['core'])

    def test_malformed_reread_preserves_first(self):
        for second in ({}, {'core': []}, {'core': {'cert_number': 'EEP73061', 'cast_job_number': 'Delivery Note 28209127'}}, None):
            result = recover_identity(self.first, kind='certificate', reread=lambda: second)
            self.assertEqual(result['core'], self.first['core'])

    def ddt(self):
        return {'ddt_number_raw': '28209127', 'rows': [
            {'line_no_raw': '2.1', 'arconic_item_number_raw': 'BG5207530', 'cast_number_raw': 'C70025341313', 'package_ids_raw': None, 'net_weight_raw': '3999'},
            {'line_no_raw': '3.1', 'arconic_item_number_raw': 'BG5207534', 'cast_number_raw': 'C70025341313', 'package_ids_raw': '44262209', 'net_weight_raw': '6996'}]}

    def test_ddt_reordered_reread_only_fills_same_identifiable_row(self):
        first = self.ddt(); second = copy.deepcopy(first)
        second['rows'][0]['package_ids_raw'] = '44218360 44270958'
        second['rows'][0]['net_weight_raw'] = '999999'
        second['rows'][1]['package_ids_raw'] = '11111111'
        second['rows'].reverse()
        result = recover_identity(first, kind='ddt', reread=lambda: second)
        self.assertEqual(result['rows'][0]['package_ids_raw'], '44218360 44270958')
        self.assertEqual(result['rows'][0]['net_weight_raw'], '3999')
        self.assertEqual(result['rows'][1], first['rows'][1])

    def test_ddt_ambiguity_and_wrong_document_not_applied(self):
        first = self.ddt()
        for variant in ('duplicate', 'different_article', 'different_ddt', 'package_is_ddt'):
            second = copy.deepcopy(first)
            second['rows'][0]['package_ids_raw'] = '44270958'
            if variant == 'duplicate':second['rows'].append(copy.deepcopy(second['rows'][0]))
            if variant == 'different_article':second['rows'][0]['arconic_item_number_raw'] = 'BG9999999'
            if variant == 'different_ddt':second['ddt_number_raw'] = '99999999'
            if variant == 'package_is_ddt':second['rows'][0]['package_ids_raw'] = '28209127'
            self.assertEqual(recover_identity(first, kind='ddt', reread=lambda: second)['rows'], first['rows'])

    def test_one_ddt_retry_for_many_rows_and_no_retry_if_complete(self):
        first = self.ddt();first['rows'][1]['package_ids_raw'] = None
        retry = Mock(side_effect=TimeoutError())
        self.assertIs(recover_identity(first, kind='ddt', reread=retry), first)
        retry.assert_called_once()
        first['rows'][0]['package_ids_raw'] = '44270958'
        first['rows'][1]['package_ids_raw'] = '44262209'
        retry.reset_mock()
        recover_identity(first, kind='ddt', reread=retry)
        retry.assert_not_called()

    def test_service_certificate_cache_and_failed_retry_does_not_abort_following_documents(self):
        cache = {}; calls = []
        def extract(images, **kw):
            calls.append(kw.get('identity_only', False))
            if kw.get('identity_only'):raise TimeoutError()
            return copy.deepcopy(self.first)
        with patch.object(s, '_document_has_image_pages', return_value=True), \
             patch.object(s, '_ensure_document_page_images', side_effect=lambda db, doc: doc), \
             patch.object(s, '_build_certificate_safe_crops', return_value={}), \
             patch.object(s, '_select_aluminium_bozen_certificate_document_images', return_value={'p1': {'page_id': 1, 'page_number': 1}}), \
             patch.object(s, '_extract_arconic_hannover_certificate_payload_from_openai', side_effect=extract):
            for i in range(1, 11):
                doc = SimpleNamespace(id=i, pages=[object()])
                first = s._get_arconic_hannover_certificate_ai_payload(None, certificate_document=doc, openai_api_key='unused', certificate_ai_cache=cache)
                second = s._get_arconic_hannover_certificate_ai_payload(None, certificate_document=doc, openai_api_key='unused', certificate_ai_cache=cache)
                self.assertIs(first, second)
                self.assertEqual(first['match_values']['numero_certificato_certificato'], 'EEP73061')
        self.assertEqual(calls.count(False), 10)
        self.assertEqual(calls.count(True), 10)

    def test_service_ddt_failed_retry_still_returns_material_rows(self):
        raw = self.ddt()
        with patch.object(s, '_ensure_document_page_images', side_effect=lambda db, doc: doc), \
             patch.object(s, '_build_arconic_hannover_ddt_group_crops', return_value={'p': {}}), \
             patch.object(s, 'reader_detect_ddt_core_matches', return_value={}), \
             patch.object(s, '_extract_arconic_hannover_ddt_row_groups_from_openai', side_effect=[('28209127',raw['rows'],json.dumps(raw)), TimeoutError()]):
            doc = SimpleNamespace(pages=[SimpleNamespace(immagine_pagina_storage_key='unused')])
            rows = s._extract_arconic_hannover_ddt_row_groups_with_vision(None, ddt_document=doc, openai_api_key='unused')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].article_code, 'BG5207530')

    def test_service_successful_certificate_recovery_is_normalized_before_caching(self):
        doc = SimpleNamespace(id=42, pages=[object()]); cache = {}
        with patch.object(s, '_document_has_image_pages', return_value=True), \
             patch.object(s, '_ensure_document_page_images', side_effect=lambda db, doc: doc), \
             patch.object(s, '_build_certificate_safe_crops', return_value={}), \
             patch.object(s, '_select_aluminium_bozen_certificate_document_images', return_value={'p1': {'page_id': 1, 'page_number': 1}}), \
             patch.object(s, '_extract_arconic_hannover_certificate_payload_from_openai', side_effect=[self.first,self.second]) as extract:
            result = s._get_arconic_hannover_certificate_ai_payload(None,certificate_document=doc,openai_api_key='unused',certificate_ai_cache=cache)
            again = s._get_arconic_hannover_certificate_ai_payload(None,certificate_document=doc,openai_api_key='unused',certificate_ai_cache=cache)
        self.assertIs(result, again)
        self.assertEqual(extract.call_count, 2)
        self.assertEqual(result['match_values']['numero_certificato_certificato'], 'EEP73061-44262209')
        evidence = json.loads(result['debug_raw_output'])
        self.assertEqual(evidence['_identity_recovery']['first'], self.first)

    def test_service_successful_ddt_recovery_preserves_exact_original_response(self):
        raw = self.ddt();second = copy.deepcopy(raw)
        second['rows'][0]['package_ids_raw'] = '44270958'
        original_raw = json.dumps(raw,indent=3)
        with patch.object(s, '_ensure_document_page_images', side_effect=lambda db, doc: doc), \
             patch.object(s, '_build_arconic_hannover_ddt_group_crops', return_value={'p': {}}), \
             patch.object(s, 'reader_detect_ddt_core_matches', return_value={}), \
             patch.object(s, '_extract_arconic_hannover_ddt_row_groups_from_openai', side_effect=[('28209127',raw['rows'],original_raw),('28209127',second['rows'],json.dumps(second))]):
            doc = SimpleNamespace(pages=[SimpleNamespace(immagine_pagina_storage_key='unused')])
            rows = s._extract_arconic_hannover_ddt_row_groups_with_vision(None,ddt_document=doc,openai_api_key='unused')
        self.assertEqual(rows[0].lot_batch_no,'44270958')
        self.assertEqual(rows[1].lot_batch_no,'44262209')
        self.assertEqual(json.loads(rows[0].ai_document_payload_raw)['_identity_recovery']['first_response_raw'],original_raw)

    def test_identity_only_api_has_bounded_time_and_output(self):
        for extract in (s._extract_arconic_hannover_certificate_payload_from_openai, s._extract_arconic_hannover_ddt_row_groups_from_openai):
            client = Mock();client.with_options.return_value=client
            with patch.object(s, '_make_openai_client', return_value=client), \
                 patch.object(s, '_create_openai_response', return_value=SimpleNamespace(output_text='{"core":{},"rows":[]}')) as create:
                extract({},openai_api_key='unused',identity_only=True)
            client.with_options.assert_called_once_with(timeout=45.0,max_retries=0)
            self.assertEqual(create.call_args.kwargs['max_output_tokens'], 2048)


if __name__ == '__main__':unittest.main()
