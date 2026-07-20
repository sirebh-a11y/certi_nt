import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _detect_note_matches,
    _enrich_notes_with_lst_00_class_b,
    _find_best_note_overlay_match,
    _is_radioactive_free_line,
    _normalize_vision_note_matches,
    _text_has_lst_00_us_control_implication,
    _text_has_limited_us_control_scope,
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

    def test_local_notes_ignore_class_a_limited_to_bar_ends(self):
        matches = _detect_note_matches(
            [
                SimpleNamespace(
                    id=8,
                    testo_estratto=(
                        "BILLETS 100% US TESTED ACCORDING TO AMS STD 2154 CLASS B\n"
                        "100% ULTRASONIC INSPECTION ENDS OF BARS ACCORDIG TO AMS STD 2154 CLASS A"
                    ),
                    ocr_text=None,
                )
            ]
        )

        self.assertNotIn("nota_us_control_class_a", matches)
        self.assertEqual(matches["nota_us_control_class_b"]["final"], "true")

    def test_local_notes_ignore_class_b_limited_to_bar_ends(self):
        matches = _detect_note_matches(
            [
                SimpleNamespace(
                    id=10,
                    testo_estratto=(
                        "BARS 100% US TESTED ACCORDING TO AMS STD 2154 CLASS A\n"
                        "ULTRASONIC INSPECTION OF BAR ENDS ACCORDING TO AMS STD 2154 CLASS B"
                    ),
                    ocr_text=None,
                )
            ]
        )

        self.assertEqual(matches["nota_us_control_class_a"]["final"], "true")
        self.assertNotIn("nota_us_control_class_b", matches)

    def test_limited_scope_detection_is_multilingual_and_does_not_reject_whole_material(self):
        limited_examples = (
            "100% ultrasonic inspection ends of bars class A",
            "controllo US sulle estremita delle barre classe B",
            "US-Prufung an den Stabenden Klasse A",
            "controle US aux extremites des barres classe B",
            "US inspectie aan de uiteinden van de staven class A",
            "badanie US na konce pretow class B",
        )
        for example in limited_examples:
            self.assertTrue(_text_has_limited_us_control_scope(example), example)

        general_examples = (
            "100% US testing on cast bars based on AMS-STD-2154 Class B",
            "US inspection on the billets following AMS-STD 2154 class A",
            "US-Prufung am abgedrehten Barren in Anlehnung an AMS-STD 2154 class A",
        )
        for example in general_examples:
            self.assertFalse(_text_has_limited_us_control_scope(example), example)

    def test_detects_lst_00_as_implicit_us_control_class_b_from_text(self):
        matches = _detect_note_matches(
            [
                SimpleNamespace(
                    id=9,
                    testo_estratto="Exception to N° LST 00 Rev. 01: values specially agreed.",
                    ocr_text=None,
                )
            ]
        )

        self.assertEqual(matches["nota_us_control_class_b"]["final"], "true")

    def test_lst_00_implication_accepts_common_variants_only(self):
        self.assertTrue(_text_has_lst_00_us_control_implication("Materiale secondo Spec. N. LST00"))
        self.assertTrue(_text_has_lst_00_us_control_implication("Exception to N° LST-00 Rev. 01"))
        self.assertTrue(_text_has_lst_00_us_control_implication("Spec. LST.00"))
        self.assertFalse(_text_has_lst_00_us_control_implication("WITH PROOF OF TEMPER T62"))
        self.assertFalse(_text_has_lst_00_us_control_implication("LST 000"))

    def test_ai_mechanical_requirement_lst_00_enriches_notes_with_class_b(self):
        payload = {
            "notes": {},
            "mechanical_requirement": {
                "customer_requirement_quote": {
                    "page_id": 7,
                    "snippet": "Exception to N° LST 00 Rev. 01",
                    "raw": "Exception to N° LST 00 Rev. 01",
                    "standardized": "Exception to N° LST 00 Rev. 01",
                    "final": "Exception to N° LST 00 Rev. 01",
                    "method": "chatgpt",
                }
            },
        }

        _enrich_notes_with_lst_00_class_b(payload)

        self.assertEqual(payload["notes"]["nota_us_control_class_b"]["final"], "true")
        self.assertEqual(payload["notes"]["nota_us_control_class_b"]["method"], "chatgpt")

    def test_ai_mechanical_requirement_does_not_overwrite_existing_class_b_note(self):
        payload = {
            "notes": {
                "nota_us_control_class_b": {
                    "page_id": 1,
                    "snippet": "explicit Class B",
                    "standardized": "true",
                    "final": "true",
                    "method": "chatgpt",
                }
            },
            "mechanical_requirement": {
                "customer_requirement_quote": {
                    "page_id": 7,
                    "snippet": "Exception to N° LST 00 Rev. 01",
                    "raw": "Exception to N° LST 00 Rev. 01",
                    "standardized": "Exception to N° LST 00 Rev. 01",
                    "final": "Exception to N° LST 00 Rev. 01",
                    "method": "chatgpt",
                }
            },
        }

        _enrich_notes_with_lst_00_class_b(payload)

        self.assertEqual(payload["notes"]["nota_us_control_class_b"]["snippet"], "explicit Class B")

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

    def test_vision_note_payload_rejects_only_the_scope_limited_class(self):
        normalized = _normalize_vision_note_matches(
            {
                "nota_us_control_class_a": {
                    "value": "100% ULTRASONIC INSPECTION ENDS OF BARS ACCORDING TO AMS STD 2154 CLASS A",
                    "evidence": "100% ULTRASONIC INSPECTION ENDS OF BARS ACCORDING TO AMS STD 2154 CLASS A",
                    "source_crop": "notes",
                },
                "nota_us_control_class_b": {
                    "value": "BILLETS 100% US TESTED ACCORDING TO AMS STD 2154 CLASS B",
                    "evidence": "BILLETS 100% US TESTED ACCORDING TO AMS STD 2154 CLASS B",
                    "source_crop": "notes",
                },
            },
            {"notes": {"page_id": 5, "page_number": 1}},
        )

        self.assertNotIn("nota_us_control_class_a", normalized)
        self.assertEqual(normalized["nota_us_control_class_b"]["final"], "true")

    def test_vision_note_payload_requires_sentence_evidence_instead_of_true(self):
        normalized = _normalize_vision_note_matches(
            {
                "nota_us_control_class_a": {
                    "value": "true",
                    "evidence": "true",
                    "source_crop": "notes",
                }
            },
            {"notes": {"page_id": 6, "page_number": 1}},
        )

        self.assertNotIn("nota_us_control_class_a", normalized)

    def test_extended_class_a_is_rejected_when_limited_to_bar_ends(self):
        sentence = (
            "100% ultrasonic inspection ends of bars according to SAE AMS-STD-2154-E Class A Type 1, "
            "single indication size >2mm and backwall echo drop > 50% BSH"
        )
        normalized = _normalize_vision_note_matches(
            {
                "nota_us_control_class_a_type1_bsh": {
                    "value": sentence,
                    "evidence": sentence,
                    "source_crop": "notes",
                }
            },
            {"notes": {"page_id": 11, "page_number": 1}},
        )

        self.assertNotIn("nota_us_control_class_a_type1_bsh", normalized)

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
