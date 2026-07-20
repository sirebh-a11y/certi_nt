import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _gemba_is_evaluated_list_row,
    _gemba_is_open_list_row,
    _quality_pending_closure_reason,
)


class AcquisitionPendingClosureTest(unittest.TestCase):
    def test_pending_reason_distinguishes_ddt_and_match(self):
        self.assertEqual(
            _quality_pending_closure_reason(
                qualita_valutazione="accettato",
                document_ddt_id=None,
                ddt_state="rosso",
                match_state="rosso",
            ),
            "attesa_ddt",
        )
        self.assertEqual(
            _quality_pending_closure_reason(
                qualita_valutazione="accettato",
                document_ddt_id=11,
                ddt_state="giallo",
                match_state="giallo",
            ),
            "ddt_da_confermare",
        )
        self.assertEqual(
            _quality_pending_closure_reason(
                qualita_valutazione="accettato",
                document_ddt_id=11,
                ddt_state="verde",
                match_state="giallo",
            ),
            "match_da_confermare",
        )
        self.assertIsNone(
            _quality_pending_closure_reason(
                qualita_valutazione="accettato",
                document_ddt_id=11,
                ddt_state="verde",
                match_state="verde",
            )
        )

    def test_evaluated_pending_row_is_in_both_business_views(self):
        row = SimpleNamespace(validata_finale=False, qualita_valutazione="accettato")

        self.assertTrue(_gemba_is_evaluated_list_row(row))
        self.assertTrue(_gemba_is_open_list_row(row))

    def test_closed_row_is_not_open(self):
        row = SimpleNamespace(validata_finale=True, qualita_valutazione="accettato")

        self.assertTrue(_gemba_is_evaluated_list_row(row))
        self.assertFalse(_gemba_is_open_list_row(row))


if __name__ == "__main__":
    unittest.main()
