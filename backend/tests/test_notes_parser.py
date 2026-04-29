import unittest

from app.modules.acquisition.service import _is_radioactive_free_line


class NotesParserTest(unittest.TestCase):
    def test_radioactive_free_line_accepts_simple_multilingual_absence_terms(self):
        self.assertTrue(
            _is_radioactive_free_line(
                "Keine erhöhte Radioaktivität im Vergleich zur Umgebung/ Free from radioactivity in comparison to environment".lower()
            )
        )
        self.assertTrue(_is_radioactive_free_line("Material free from radioactive contamination".lower()))
        self.assertTrue(_is_radioactive_free_line("Materiale privo di contaminazione radioattiva".lower()))
        self.assertTrue(_is_radioactive_free_line("Materiel sans contamination radioactive".lower()))

    def test_radioactive_mentions_without_absence_are_not_enough(self):
        self.assertFalse(_is_radioactive_free_line("Radioactive inspection required".lower()))


if __name__ == "__main__":
    unittest.main()
