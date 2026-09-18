"""Manual quality values must survive a certificate-first/DDT merge."""
import unittest
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.core.database import Base
from app.startup import bootstrap  # noqa: F401 - register model relationships
from app.modules.acquisition.models import AcquisitionRow, AcquisitionValueHistory, Document, DocumentPage
from app.modules.acquisition.schemas import DocumentLinkCandidateRequest
from app.modules.acquisition import service as s
from app.modules.acquisition.service import get_acquisition_row, _merge_certificate_only_row_into_ddt_row


DATE_FIELDS = ('qualita_data_accettazione', 'qualita_data_ricezione', 'qualita_data_richiesta')


class CertificateMergeManualQualityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def rows(self, source_values=None, target_values=None):
        certificate = Document(tipo_documento='certificato', nome_file_originale='test.pdf', storage_key=f'{uuid4()}.pdf')
        ddt = Document(tipo_documento='ddt', nome_file_originale='ddt.pdf', storage_key=f'{uuid4()}.pdf')
        self.db.add_all([certificate, ddt])
        self.db.flush()
        self.db.add_all([
            DocumentPage(document_id=doc.id, numero_pagina=1,
                         testo_estratto='Test document', ocr_text='Test document', stato_estrazione='completato')
            for doc in (certificate, ddt)
        ])
        source = AcquisitionRow(document_certificato_id=certificate.id, **(source_values or {}))
        target = AcquisitionRow(document_ddt_id=ddt.id, document_certificato_id=certificate.id, **(target_values or {}))
        sibling = AcquisitionRow(document_ddt_id=ddt.id, document_certificato_id=certificate.id)
        self.db.add_all([source, target, sibling])
        self.db.commit()
        return source, target, sibling

    def merge(self, source, target):
        source_id, target_id = source.id, target.id
        self.assertTrue(_merge_certificate_only_row_into_ddt_row(
            db=self.db, source_row_id=source_id, target_row=get_acquisition_row(self.db, target_id), actor_id=1,
        ))
        self.db.expire_all()
        self.assertIsNone(self.db.get(AcquisitionRow, source_id))
        return get_acquisition_row(self.db, target_id)

    def test_unclosed_note_and_dates_survive_without_creating_evaluation(self):
        values = {field: date(2026, 9, 3) for field in DATE_FIELDS}
        values.update(qualita_note='Nota salvata\nprima della chiusura', qualita_numero_colli=4)
        source, target, sibling = self.rows(values)
        result = self.merge(source, target)
        for field, value in values.items():
            self.assertEqual(getattr(result, field), value)
            self.assertIsNone(getattr(self.db.get(AcquisitionRow, sibling.id), field))
        self.assertIsNone(result.qualita_valutazione)
        self.assertFalse(result.validata_finale)

    def test_blank_source_never_erases_destination_for_each_outcome(self):
        for evaluation in (None, 'accettato', 'accettato_con_riserva', 'respinto'):
            with self.subTest(evaluation=evaluation):
                destination = {field: date(2026, 9, 8) for field in DATE_FIELDS}
                destination['qualita_note'] = 'Nota presente sul DDT'
                source, target, _ = self.rows({'qualita_valutazione': evaluation}, destination)
                result = self.merge(source, target)
                for field, value in destination.items():
                    self.assertEqual(getattr(result, field), value)
                self.assertEqual(result.qualita_valutazione, evaluation)

    def test_matching_values_remain_unchanged(self):
        values = {field: date(2026, 9, 8) for field in DATE_FIELDS}
        values['qualita_note'] = 'Nota uguale'
        source, target, _ = self.rows(values, values)
        result = self.merge(source, target)
        for field, value in values.items():
            self.assertEqual(getattr(result, field), value)

    def test_note_whitespace_is_empty_but_real_note_is_preserved_exactly(self):
        for source_note, target_note, expected in (
            ('Nota\ncompleta', '   ', 'Nota\ncompleta'),
            ('   ', 'Nota DDT', 'Nota DDT'),
            ('', 'Nota DDT', 'Nota DDT'),
        ):
            with self.subTest(source=source_note, target=target_note):
                source, target, _ = self.rows({'qualita_note': source_note}, {'qualita_note': target_note})
                self.assertEqual(self.merge(source, target).qualita_note, expected)

    def test_different_long_notes_both_kept_in_field_and_full_history(self):
        left, right = 'Certificato\n' + 'x' * 1200, 'DDT\n' + 'y' * 1200
        source, target, _ = self.rows({'qualita_note': left}, {'qualita_note': right})
        result = self.merge(source, target)
        self.assertEqual(result.qualita_note, f'Da certificato: {left}\nDa riga DDT: {right}')
        history = self.db.query(AcquisitionValueHistory).filter_by(acquisition_row_id=result.id, campo='qualita_note').all()
        origins = {json.loads(h.valore_prima)['origine']: json.loads(h.valore_prima)['valore'] for h in history}
        self.assertEqual(origins, {'certificato': left, 'ddt': right})
        self.assertTrue(all(h.valore_dopo == result.qualita_note for h in history))

    def test_confirmed_evaluation_date_wins_and_both_dates_are_recorded(self):
        for source_eval, target_eval, expected in [
            ('accettato', None, date(2026, 9, 3)),
            ('accettato_con_riserva', None, date(2026, 9, 3)),
            ('respinto', None, date(2026, 9, 3)),
            (None, 'accettato', date(2026, 9, 8)),
            ('accettato', 'accettato_con_riserva', date(2026, 9, 8)),
        ]:
            with self.subTest(source=source_eval, target=target_eval):
                source, target, _ = self.rows(
                    {'qualita_data_accettazione': date(2026, 9, 3), 'qualita_valutazione': source_eval, 'qualita_note': 'Fonte'},
                    {'qualita_data_accettazione': date(2026, 9, 8), 'qualita_valutazione': target_eval, 'qualita_note': 'Destinazione'})
                result = self.merge(source, target)
                self.assertEqual(result.qualita_data_accettazione, expected)
                self.assertEqual(result.qualita_valutazione, target_eval or source_eval)
                history = self.db.query(AcquisitionValueHistory).filter_by(acquisition_row_id=result.id, campo='qualita_data_accettazione').all()
                self.assertEqual({json.loads(h.valore_prima)['valore'] for h in history}, {'2026-09-03', '2026-09-08'})

    def test_unconfirmed_conflict_needs_choice_before_any_merge_write(self):
        source, target, _ = self.rows({'qualita_data_accettazione': date(2026, 9, 3)},
                                     {'qualita_data_accettazione': date(2026, 9, 8)})
        for choice in (None, date(2026, 9, 15)):
            with self.assertRaises(HTTPException) as error:
                _merge_certificate_only_row_into_ddt_row(db=self.db, source_row_id=source.id,
                    target_row=target, actor_id=1, acceptance_date_choice=choice)
            self.assertEqual(error.exception.detail['code'], 'merge_acceptance_date_choice')
            self.assertFalse(self.db.new)
            self.assertFalse(self.db.deleted)
            self.assertFalse(self.db.dirty)
        sid = source.id
        self.assertTrue(_merge_certificate_only_row_into_ddt_row(db=self.db, source_row_id=sid,
            target_row=target, actor_id=1, acceptance_date_choice=date(2026, 9, 8)))
        self.assertIsNone(self.db.get(AcquisitionRow, sid))
        self.assertEqual(get_acquisition_row(self.db, target.id).qualita_data_accettazione, date(2026, 9, 8))

    def test_manual_link_both_directions_conflict_then_explicit_retry(self):
        for from_certificate in (False, True):
            with self.subTest(from_certificate=from_certificate):
                source, target, _ = self.rows({'qualita_data_accettazione': date(2026, 9, 3), 'qualita_note': 'Fonte'},
                                             {'qualita_data_accettazione': date(2026, 9, 8), 'qualita_note': 'DDT'})
                target.document_certificato_id = None
                self.db.commit()
                current, candidate = (source, target) if from_certificate else (target, source)
                link = s._link_ddt_candidate_to_certificate_row if from_certificate else s._link_certificate_candidate_to_ddt_row
                with patch.object(s, '_ensure_user_candidate_can_link'):
                    with self.assertRaises(HTTPException) as error:
                        link(db=self.db, current_row=current, candidate_row=candidate,
                             payload=DocumentLinkCandidateRequest(candidate_row_id=candidate.id), actor_id=1)
                    self.assertEqual(error.exception.detail['code'], 'merge_acceptance_date_choice')
                    self.assertIsNone(target.document_certificato_id)
                    self.assertIsNone(target.certificate_match)
                    self.assertIn(source, self.db)
                    response = link(db=self.db, current_row=current, candidate_row=candidate,
                        payload=DocumentLinkCandidateRequest(candidate_row_id=candidate.id, merge_acceptance_date=date(2026, 9, 3)), actor_id=1)
                    self.assertTrue(response.source_row_deleted)
                    result = get_acquisition_row(self.db, response.target_row_id)
                    self.assertEqual(result.qualita_data_accettazione, date(2026, 9, 3))
                    self.assertEqual(result.qualita_note, 'Da certificato: Fonte\nDa riga DDT: DDT')
                    self.assertEqual(result.certificate_match.stato, 'proposto')

    def test_auto_rematch_conflict_leaves_rows_separate_and_records_guidance(self):
        source, target, _ = self.rows({'qualita_data_accettazione': date(2026, 9, 3)},
                                     {'qualita_data_accettazione': date(2026, 9, 8)})
        target.document_certificato_id = None
        self.db.commit()
        candidate = SimpleNamespace(source_has_ddt=False, source_row_id=source.id)
        plan = SimpleNamespace(row_id=target.id, candidates=(candidate,))
        with patch.object(s, '_plan_cross_run_auto_rematch', return_value=[plan]), patch.object(s, 'upsert_match') as upsert:
            count = s._run_cross_run_auto_rematch(db=self.db, supplier_ids={1}, actor_id=1, run_id=1)
            self.assertEqual(count, 0)
            upsert.assert_not_called()
        self.assertIsNone(target.document_certificato_id)
        self.assertIsNotNone(self.db.get(AcquisitionRow, source.id))
        self.assertTrue(any(h.azione == 'unione_richiede_data_accettazione' for h in get_acquisition_row(self.db, target.id).history_events))

    def test_merge_failure_rolls_back_link_even_when_ocr_was_needed(self):
        source, target, _ = self.rows({'qualita_note': 'Nota da conservare'})
        target.document_certificato_id = None
        page = source.certificate_document.pages[0]
        page.testo_estratto = None
        page.ocr_text = None
        page.immagine_pagina_storage_key = 'synthetic.png'
        self.db.commit()
        sid, tid, pid = source.id, target.id, page.id
        with patch.object(s, '_ensure_user_candidate_can_link'), \
             patch.object(s, 'get_document_page_image_path', return_value='synthetic.png'), \
             patch.object(s, '_ocr_page_image', return_value=('Certificate test', 'ocr_test')), \
             patch.object(s, '_merge_certificate_only_row_into_ddt_row', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                s._link_certificate_candidate_to_ddt_row(db=self.db, current_row=target, candidate_row=source,
                    payload=DocumentLinkCandidateRequest(candidate_row_id=sid), actor_id=1)
        self.db.rollback()
        self.assertIsNone(get_acquisition_row(self.db, tid).document_certificato_id)
        self.assertIsNone(get_acquisition_row(self.db, tid).certificate_match)
        self.assertEqual(get_acquisition_row(self.db, sid).qualita_note, 'Nota da conservare')
        self.assertIsNone(self.db.get(DocumentPage, pid).ocr_text)

    def test_deferred_document_indexing_does_not_commit_merge_transaction(self):
        source, _, _ = self.rows()
        doc = source.certificate_document
        payload = dict(numero_pagina=1, larghezza=100, altezza=100, rotazione=0,
                       testo_estratto='Indexed test', immagine_pagina_storage_key=None,
                       stato_estrazione='testo_pdf')
        with patch.object(s.Path, 'exists', return_value=True), \
             patch.object(s, '_extract_pdf_page_payloads', return_value=[payload]), \
             patch.object(self.db, 'commit', wraps=self.db.commit) as commit:
            indexed = s._index_document_from_path(self.db, doc, commit=False)
            commit.assert_not_called()
            self.assertEqual(indexed.pages[0].testo_estratto, 'Indexed test')


if __name__ == '__main__':
    unittest.main()
