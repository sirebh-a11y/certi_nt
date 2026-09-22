import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.quarta_taglio import service as s


def _row(row_id: int, diameter: str, *, weight: str = "0") -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        diametro=diameter,
        peso=weight,
        cdq="95094",
        colata="95094",
        document_certificato_id=row_id + 100,
        qualita_valutazione="accettato",
    )


class QuartaTaglioArticleDisambiguationTest(unittest.TestCase):
    def _select(
        self,
        rows: list[SimpleNamespace],
        *,
        cod_art: str | None,
        qta_totale: float | None = None,
        override: SimpleNamespace | None = None,
    ):
        with patch.object(s, "_matching_override_for_material", return_value=override):
            return s._effective_incoming_rows_for_quarta_material(
                SimpleNamespace(),
                cod_odp="OL2026001147",
                cdq="95094",
                colata="95094",
                qta_totale=qta_totale,
                exact_rows=rows,
                article_code=cod_art,
            )

    def test_client_case_selects_diameter_285_from_article(self):
        rows = [_row(136, "295"), _row(163, "285")]

        selected, message = self._select(rows, cod_art="A75285BTU")

        self.assertEqual([row.id for row in selected], [163])
        self.assertIsNone(message)

    def test_article_without_candidate_diameter_keeps_manual_check(self):
        rows = [_row(136, "295"), _row(163, "285")]

        selected, message = self._select(rows, cod_art="ABC75BTU")

        self.assertEqual(selected, rows)
        self.assertEqual(message, "CDQ presente su più righe app: verifica manuale")

    def test_overlapping_diameters_are_not_selected_automatically(self):
        rows = [_row(136, "28"), _row(163, "285")]

        selected, message = self._select(rows, cod_art="A75285BTU")

        self.assertEqual(selected, rows)
        self.assertIsNotNone(message)

    def test_suffix_diameters_are_not_selected_automatically(self):
        rows = [_row(136, "85"), _row(163, "285")]

        selected, message = self._select(rows, cod_art="A75285BTU")

        self.assertEqual(selected, rows)
        self.assertIsNotNone(message)

    def test_duplicate_diameter_is_not_selected_automatically(self):
        rows = [_row(136, "285"), _row(163, "285")]

        selected, message = self._select(rows, cod_art="A75285BTU")

        self.assertEqual(selected, rows)
        self.assertIsNotNone(message)

    def test_existing_manual_selection_is_preserved(self):
        rows = [_row(136, "295"), _row(163, "285")]
        override = SimpleNamespace(acquisition_row_id=136)

        selected, message = self._select(rows, cod_art="A75285BTU", override=override)

        self.assertEqual([row.id for row in selected], [136])
        self.assertIsNone(message)

    def test_weight_remains_fallback_when_article_does_not_match(self):
        rows = [_row(136, "295", weight="100"), _row(163, "285", weight="716")]

        selected, message = self._select(rows, cod_art="ABC75BTU", qta_totale=716)

        self.assertEqual([row.id for row in selected], [163])
        self.assertIsNone(message)

    def test_decimal_diameter_is_normalized_for_compact_article(self):
        rows = [_row(136, "29,5"), _row(163, "28,5")]

        selected, message = self._select(rows, cod_art="A75285BTU")

        self.assertEqual([row.id for row in selected], [163])
        self.assertIsNone(message)

    def test_status_evaluation_uses_article_selected_row(self):
        rows = [_row(136, "295"), _row(163, "285")]
        with (
            patch.object(s, "_matching_override_for_material", return_value=None),
            patch.object(
                s,
                "_compute_block_states_from_db",
                return_value={"chimica": "verde", "proprieta": "verde", "note": "verde"},
            ),
        ):
            result = s._evaluate_cdq(
                db=SimpleNamespace(),
                cod_odp="OL2026001147",
                cdq="95094",
                colata="95094",
                qta_totale=716,
                rows_by_cdq={"95094": rows},
                article_code="A75285BTU",
            )

        self.assertEqual(result, ("green", "CDQ coerente e completo", [], [163]))


if __name__ == "__main__":
    unittest.main()
