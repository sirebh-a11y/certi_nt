import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import test_quarta_taglio_esolver as fixtures
from app.modules.quarta_taglio import service as s
from app.modules.quarta_taglio.schemas import QuartaTaglioEsolverDdtRowResponse


class WordFiltersTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.QuartaTaglioEsolverTest()
        self.row = self.f._quarta_row()
        self.raw = self.candidate('605000700')
        self.child = self.candidate('605000730')
        self.raw_word = self.f._certificate(cod_f3='605000700')
        self.raw_word.id = 1

    def candidate(self, code, description='Descrizione Quarta'):
        return s._CertiOlRow(orp='OL1', cod_cli='C', rag_soc='Test',
                            cod_f3_odp='605000700', cod_f3=code, des_f3=description)

    def filter_groups(self, certificates, candidates, *, additional=False, blocked=False):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [('OL1',)]
        with ExitStack() as stack:
            for name, value in {
                '_load_final_certificates_by_odp': {'OL1': certificates},
                '_load_matching_app_rows': [],
                '_word_creation_blockers': ['Blocked'] if blocked else [],
                '_fetch_certiol_rows_batch': {'OL1': candidates},
            }.items():
                stack.enter_context(patch.object(s, name, return_value=value))
            return s._filter_word_pending_groups(
                db, groups=[(s._serialize_ol_group([self.row]), [self.row])],
                esolver_links={}, additional_words=additional,
            )

    def test_first_and_additional_are_disjoint(self):
        for certificates, expected in [([], (True, False)), ([self.raw_word], (False, True))]:
            with self.subTest(started=bool(certificates)):
                for additional in (False, True):
                    result = self.filter_groups(certificates, [self.raw, self.child], additional=additional)
                    self.assertEqual(bool(result), expected[int(additional)])
                    if result:
                        self.assertTrue(result[0][0].word_pending_reasons)

    def test_all_words_present_neither_filter(self):
        certificates = [self.raw_word, self.f._certificate(cod_f3='605000730')]
        for additional in (False, True):
            self.assertFalse(self.filter_groups(certificates, [self.raw, self.child], additional=additional))

    def test_standard_or_other_blockers_still_exclude_both(self):
        for additional in (False, True):
            self.assertFalse(self.filter_groups([self.raw_word] if additional else [],
                                               [self.raw, self.child], additional=additional, blocked=True))

    def test_probable_and_preparable_candidates_are_both_explicitly_proposals(self):
        for child in [self.child, self.candidate('605000760', 'Xyz')]:
            result = self.filter_groups([self.raw_word], [self.raw, child], additional=True)
            reasons = result[0][0].word_pending_reasons
            self.assertEqual(len(reasons), 1)
            self.assertEqual(reasons[0].kind, 'proposed')
            self.assertIn('verificare se serve il certificato', reasons[0].message)
            self.assertIn(child.cod_f3, reasons[0].message)

    def test_review_candidate_not_mistaken_for_work_to_do(self):
        self.assertFalse(self.filter_groups([self.raw_word],
                                           [self.raw, self.candidate('999999999', 'Xyz')], additional=True))

    def test_same_article_two_deliveries_reports_only_missing_delivery(self):
        link = self.f._esolver_link([
            {'cod_f3': '605000730', 'orp': 'OL1', 'ddt': f'DDT{n}',
             'id_documento': str(n), 'id_riga_doc': '1', 'rif_lotto_alfanum': f'L{n}'}
            for n in (1, 2)
        ])
        units = s._build_certifiable_units(cod_odp='OL1', quarta_rows=[self.row],
                    esolver_rows=[QuartaTaglioEsolverDdtRowResponse(**r) for r in link.rows])
        first = self.f._certificate(cod_f3=units[0].cod_f3, ddt=units[0].ddt, unit_key=units[0].unit_key)
        first.id = 2
        reasons = s._word_pending_reasons(group_rows=[self.row], esolver_link=link,
                                          certificates=[self.raw_word, first], certiol_rows=[self.raw, self.child])
        self.assertEqual(len(reasons), 1)
        self.assertEqual(reasons[0].kind, 'ddt')
        self.assertIn(units[1].ddt, reasons[0].message)
        self.assertNotIn(units[0].ddt, reasons[0].message)

    def test_number_without_file_not_considered_prepared_but_closed_pdf_is(self):
        empty = self.f._certificate(storage_key_docx=None)
        self.assertFalse(s._has_prepared_word([empty]))
        empty.status = 'pdf_final'
        empty.storage_key_pdf = 'closed.pdf'
        self.assertTrue(s._has_prepared_word([empty]))

    def test_conflicting_filters_fail_before_any_sync_or_db_access(self):
        db = MagicMock()
        with patch.object(s, '_sync_quarta_rows') as sync:
            with self.assertRaises(HTTPException) as error:
                s.sync_and_list_quarta_taglio(db, only_word_pending=True, only_additional_words=True)
            self.assertEqual(error.exception.status_code, 422)
            sync.assert_not_called()
            self.assertFalse(db.mock_calls)

    def test_list_counts_search_pagination_and_reasons_use_selected_filter(self):
        rows = [self.f._quarta_row(cod_odp=f'OL{n}') for n in range(1, 5)]
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        db.query.return_value.filter.return_value.all.return_value = [(r.cod_odp,) for r in rows]
        ci = {r.cod_odp: [self.raw, self.child] for r in rows}
        with ExitStack() as stack:
            for name, value in {
                '_latest_quarta_sync_run': object(),
                '_load_esolver_links_for_rows': {},
                '_refresh_esolver_links_for_rows': {},
                '_load_final_certificates_by_odp': {'OL4': [self.raw_word]},
                '_load_matching_app_rows': [],
                '_word_creation_blockers': [],
                '_fetch_certiol_rows_batch': ci,
                '_build_certification_progress_by_odp': {},
                '_serialize_run': dict(id=1, status='ok', message=None, total_ol=4,
                                      total_cdq_rows=4, started_at=datetime.now(timezone.utc), finished_at=None),
            }.items():
                stack.enter_context(patch.object(s, name, return_value=value))
            sync = stack.enter_context(patch.object(s, '_sync_quarta_rows'))
            first = s.sync_and_list_quarta_taglio(db, sync_data=False, only_word_pending=True,
                                                 limit=1, offset=1, sort_field='cod_odp')
            self.assertEqual(first.total_items, 3)
            self.assertEqual([r.cod_odp for r in first.items], ['OL2'])
            self.assertEqual(first.items[0].word_pending_reasons[0].kind, 'raw')
            self.assertTrue(first.only_word_pending)
            self.assertFalse(first.only_additional_words)
            additional = s.sync_and_list_quarta_taglio(db, sync_data=False, only_additional_words=True)
            self.assertEqual(additional.total_items, 1)
            self.assertEqual(additional.items[0].cod_odp, 'OL4')
            self.assertEqual(additional.items[0].word_pending_reasons[0].kind, 'proposed')
            self.assertTrue(additional.only_additional_words)
            searched = s.sync_and_list_quarta_taglio(db, sync_data=False, only_word_pending=True,
                                                    query_one='OL3')
            self.assertEqual(searched.total_items, 1)
            self.assertEqual(searched.items[0].cod_odp, 'OL3')
            all_rows = s.sync_and_list_quarta_taglio(db, sync_data=False)
            self.assertEqual(all_rows.total_items, 4)
            self.assertTrue(all(not r.word_pending_reasons for r in all_rows.items))
            sync.assert_not_called()

    def test_incomplete_material_excluded_and_reservation_still_allowed(self):
        self.row.status_color = 'yellow'
        self.row.status_message = 'CDQ trovato, ma iter non completo'
        self.assertFalse(self.filter_groups([], [self.raw]))
        self.row.status_message = s.QUALITY_RESERVATION_STATUS_MESSAGE
        self.assertTrue(self.filter_groups([], [self.raw]))


if __name__ == '__main__':
    unittest.main()
