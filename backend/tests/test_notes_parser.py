import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _detect_note_matches,
    _find_best_note_overlay_match,
    _is_radioactive_free_line,
    _normalize_vision_note_matches,
)


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

    def test_detects_us_control_class_a_and_b_independently(self):
        matches = _detect_note_matches(
            [
                SimpleNamespace(
                    id=7,
                    testo_estratto=(
                        "US-Prufung an abgedrehten Barren in Anlehnung an ASTM B 594 / "
                        "AMS-STD 2154 class A\n"
                        "US inspection following ASTM B 594 / AMS-STD 2154 class B"
                    ),
                    ocr_text=None,
                )
            ]
        )

        self.assertEqual(matches["nota_us_control_class_a"]["final"], "true")
        self.assertEqual(matches["nota_us_control_class_b"]["final"], "true")

    def test_vision_note_payload_keeps_both_us_classes(self):
        normalized = _normalize_vision_note_matches(
            {
                "nota_us_control_class_a": {
                    "value": "true",
                    "evidence": "US inspection according to ASTM 594 class A",
                    "source_crop": "notes",
                },
                "nota_us_control_class_b": {
                    "value": "true",
                    "evidence": "US inspection according to ASTM 594 class B",
                    "source_crop": "notes",
                },
            },
            {"notes": {"page_id": 3, "page_number": 1}},
        )

        self.assertEqual(normalized["nota_us_control_class_a"]["final"], "true")
        self.assertEqual(normalized["nota_us_control_class_b"]["final"], "true")

    def test_legacy_vision_note_payload_is_split_when_both_classes_are_present(self):
        normalized = _normalize_vision_note_matches(
            {
                "nota_us_control_classe": {
                    "value": "ASTM B 594 class A and class B",
                    "evidence": "US inspection according to ASTM B 594 class A and class B",
                    "source_crop": "notes",
                },
            },
            {"notes": {"page_id": 4, "page_number": 1}},
        )

        self.assertEqual(normalized["nota_us_control_class_a"]["final"], "true")
        self.assertEqual(normalized["nota_us_control_class_b"]["final"], "true")

    def test_notes_overlay_uses_class_specific_field_to_pick_the_right_line(self):
        line_boxes = [
            {
                "x0": 10,
                "y0": 10,
                "x1": 300,
                "y1": 30,
                "words": [{"text": token} for token in "US inspection according to ASTM B 594 class B".split()],
            },
            {
                "x0": 10,
                "y0": 50,
                "x1": 300,
                "y1": 70,
                "words": [{"text": token} for token in "US inspection according to ASTM B 594 class A".split()],
            },
        ]

        class_a_match = _find_best_note_overlay_match(
            field="nota_us_control_class_a",
            snippet="US inspection according to ASTM B 594 class A",
            line_boxes=line_boxes,
            expected_value="true",
        )
        class_b_match = _find_best_note_overlay_match(
            field="nota_us_control_class_b",
            snippet="US inspection according to ASTM B 594 class B",
            line_boxes=line_boxes,
            expected_value="true",
        )

        self.assertEqual(class_a_match[0], "10,50,300,70")
        self.assertEqual(class_b_match[0], "10,10,300,30")


if __name__ == "__main__":
    unittest.main()
