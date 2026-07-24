import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.quarta_taglio.service import (
    QUALITY_RESERVATION_STATUS_MESSAGE,
    _evaluate_cdq,
    _group_status_message,
    _incoming_rows_ready_for_certification,
)


def _incoming_row(*, evaluation: str, row_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        cdq="CDQ-1",
        colata="COL-1",
        document_certificato_id=11,
        qualita_valutazione=evaluation,
    )


class QuartaTaglioQualityReservationTest(unittest.TestCase):
    def _evaluate(self, row: SimpleNamespace, block_states: dict[str, str]):
        with (
            patch(
                "app.modules.quarta_taglio.service._effective_incoming_rows_for_quarta_material",
                return_value=([row], None),
            ),
            patch(
                "app.modules.quarta_taglio.service._compute_block_states_from_db",
                return_value=block_states,
            ),
        ):
            return _evaluate_cdq(
                db=SimpleNamespace(),
                cod_odp="OL-1",
                cdq="CDQ-1",
                colata="COL-1",
                qta_totale=100,
                rows_by_cdq={"cdq-1": [row]},
            )

    def test_reservation_only_is_warning_not_incomplete_iteration(self):
        result = self._evaluate(
            _incoming_row(evaluation="accettato_con_riserva"),
            {"chimica": "verde", "proprieta": "verde", "note": "verde"},
        )

        self.assertEqual(result[0], "yellow")
        self.assertEqual(result[1], QUALITY_RESERVATION_STATUS_MESSAGE)
        self.assertEqual(result[2], ["Riga app #7: accettato con riserva"])

    def test_reservation_with_missing_confirmation_remains_incomplete(self):
        result = self._evaluate(
            _incoming_row(evaluation="accettato_con_riserva"),
            {"chimica": "giallo", "proprieta": "verde", "note": "verde"},
        )

        self.assertEqual(result[0], "yellow")
        self.assertEqual(result[1], "CDQ trovato, ma iter non completo")
        self.assertIn("Riga app #7: manca conferma chimica", result[2])
        self.assertIn("Riga app #7: accettato con riserva", result[2])

    def test_fully_accepted_row_remains_green(self):
        result = self._evaluate(
            _incoming_row(evaluation="accettato"),
            {"chimica": "verde", "proprieta": "verde", "note": "verde"},
        )

        self.assertEqual(result[:3], ("green", "CDQ coerente e completo", []))

    def test_rejected_row_remains_red(self):
        result = self._evaluate(
            _incoming_row(evaluation="respinto"),
            {"chimica": "verde", "proprieta": "verde", "note": "verde"},
        )

        self.assertEqual(result[0], "red")
        self.assertEqual(result[1], "Respinto da qualità")

    def test_reservation_only_group_is_ready_but_stays_yellow(self):
        rows = [
            SimpleNamespace(status_color="green", status_message="CDQ coerente e completo"),
            SimpleNamespace(status_color="yellow", status_message=QUALITY_RESERVATION_STATUS_MESSAGE),
        ]

        self.assertTrue(_incoming_rows_ready_for_certification(rows))
        self.assertEqual(_group_status_message("yellow", rows), "Uno o più CDQ accettati con riserva")

    def test_actual_incomplete_row_is_not_ready(self):
        rows = [
            SimpleNamespace(status_color="yellow", status_message="CDQ trovato, ma iter non completo"),
        ]

        self.assertFalse(_incoming_rows_ready_for_certification(rows))
        self.assertEqual(_group_status_message("yellow", rows), "CDQ trovato, ma iter non completo")


if __name__ == "__main__":
    unittest.main()
