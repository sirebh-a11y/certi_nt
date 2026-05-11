import unittest
from types import SimpleNamespace

from app.modules.quarta_taglio.service import _evaluate_notes


def _note(field: str, value: str | None = "true") -> SimpleNamespace:
    return SimpleNamespace(
        blocco="note",
        campo=field,
        valore_finale=value,
        valore_standardizzato=value,
        valore_grezzo=value,
    )


class QuartaTaglioNotesTest(unittest.TestCase):
    def test_keeps_us_control_class_a_and_b_independent(self):
        row = SimpleNamespace(
            id=1,
            cdq="CDQ-1",
            values=[
                _note("nota_us_control_class_a"),
                _note("nota_us_control_class_b"),
            ],
        )

        notes = {item.code: item for item in _evaluate_notes([row])}

        self.assertEqual(notes["nota_us_control_class_a"].status, "ok")
        self.assertEqual(notes["nota_us_control_class_b"].status, "ok")
        self.assertNotIn("nota_us_control_classe", notes)


if __name__ == "__main__":
    unittest.main()
