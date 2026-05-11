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

    def test_system_notes_use_configured_note_text(self):
        row = SimpleNamespace(id=1, cdq="CDQ-1", values=[_note("nota_rohs")])

        notes = {item.code: item for item in _evaluate_notes([row], system_note_texts={"nota_rohs": "Frase decisa in pagina Note"})}

        self.assertEqual(notes["nota_rohs"].status, "ok")
        self.assertEqual(notes["nota_rohs"].value, "Frase decisa in pagina Note")

    def test_system_notes_use_fallback_phrase_instead_of_ok(self):
        row = SimpleNamespace(id=1, cdq="CDQ-1", values=[_note("nota_us_control_class_b")])

        notes = {item.code: item for item in _evaluate_notes([row])}

        self.assertEqual(notes["nota_us_control_class_b"].status, "ok")
        self.assertIn("class B", notes["nota_us_control_class_b"].value)
        self.assertNotEqual(notes["nota_us_control_class_b"].value, "OK")
        self.assertNotIn("nota_us_control_class_a", notes)

    def test_custom_user_notes_are_reported_when_uniform(self):
        template = SimpleNamespace(id=10, text="Nota custom da pagina Note", is_system=False, is_active=True, sort_order=100)
        rows = [
            SimpleNamespace(id=1, cdq="CDQ-1", values=[], custom_note_links=[SimpleNamespace(note_template=template)]),
            SimpleNamespace(id=2, cdq="CDQ-2", values=[], custom_note_links=[SimpleNamespace(note_template=template)]),
        ]

        notes = {item.code: item for item in _evaluate_notes(rows)}

        self.assertEqual(notes["custom_note_10"].status, "ok")
        self.assertEqual(notes["custom_note_10"].value, "Nota custom da pagina Note")

    def test_custom_user_notes_are_not_reported_automatically_when_not_uniform(self):
        template = SimpleNamespace(id=10, text="Nota custom da pagina Note", is_system=False, is_active=True, sort_order=100)
        rows = [
            SimpleNamespace(id=1, cdq="CDQ-1", values=[], custom_note_links=[SimpleNamespace(note_template=template)]),
            SimpleNamespace(id=2, cdq="CDQ-2", values=[], custom_note_links=[]),
        ]

        notes = {item.code: item for item in _evaluate_notes(rows)}

        self.assertEqual(notes["custom_note_10"].status, "different")
        self.assertIn("manca su CDQ-2", notes["custom_note_10"].message)


if __name__ == "__main__":
    unittest.main()
