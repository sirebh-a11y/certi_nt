import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.acquisition.service import (
    _build_chemistry_overlay_items,
    _build_properties_overlay_items_from_column_words,
    _find_best_chemistry_overlay_match,
)


class ArconicOverlayTest(unittest.TestCase):
    def test_chemistry_overlay_uses_header_geometry_when_values_are_sparse(self):
        page = SimpleNamespace(id=1, numero_pagina=1, immagine_pagina_storage_key="page.png")
        header_tokens = ["Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Ni", "Zn", "Ti", "Cd", "Hg", "Pb", "V", "Bi", "Sn", "Zr"]
        header_words = [
            {"text": token, "left": 100 + index * 32, "top": 100, "width": 18, "height": 12}
            for index, token in enumerate(header_tokens)
        ]
        # Simula Arconic: OCR locale vede solo pochi valori della riga, non abbastanza
        # per superare la soglia dei 3 match, ma l'header della tabella e' chiaro.
        value_words = [
            {"text": "0,0030", "normalized": "0,0030", "left": 452, "top": 150, "width": 28, "height": 12},
            {"text": "0,00", "normalized": "0,00", "left": 580, "top": 150, "width": 22, "height": 12},
        ]
        line_boxes = [
            {"words": header_words, "x0": 100, "y0": 100, "x1": 610, "y1": 112},
            {"words": value_words, "x0": 452, "y0": 150, "x1": 602, "y1": 162},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 700, 300)):
            match = _find_best_chemistry_overlay_match(
                page=page,
                field_values={"Si": "1,03", "Pb": "0,0030", "Zr": "0,00"},
                supplier_key="arconic_hannover",
            )
            self.assertIsNotNone(match)
            assert match is not None
            line_box, matched_fields, image_width, image_height, _score = match
            items = _build_chemistry_overlay_items(
                page=page,
                line_box=line_box,
                field_values={"Si": "1,03", "Pb": "0,0030", "Zr": "0,00"},
                matched_fields=matched_fields,
                image_width=image_width,
                image_height=image_height,
                supplier_key="arconic_hannover",
            )

        by_field = {item.field: item for item in items}
        self.assertIn("Si", by_field)
        self.assertIn("Pb", by_field)
        self.assertIn("Zr", by_field)

    def test_properties_overlay_uses_column_words_when_ocr_drops_leading_digit(self):
        page = SimpleNamespace(id=1, numero_pagina=1, immagine_pagina_storage_key="page.png")
        header_words = [
            {"text": "Rm", "left": 100, "top": 100, "width": 18, "height": 12},
            {"text": "Rp0,2", "left": 220, "top": 100, "width": 36, "height": 12},
            {"text": "A5", "left": 340, "top": 100, "width": 18, "height": 12},
            {"text": "HBW", "left": 460, "top": 170, "width": 26, "height": 12},
        ]
        result_words = [
            {"text": "387,0", "normalized": "387,0", "left": 100, "top": 145, "width": 34, "height": 12},
            {"text": "351,0", "normalized": "351,0", "left": 220, "top": 145, "width": 34, "height": 12},
            {"text": "13,5", "normalized": "13,5", "left": 340, "top": 145, "width": 28, "height": 12},
            {"text": "09.", "normalized": "09", "left": 462, "top": 215, "width": 20, "height": 12},
        ]
        line_boxes = [
            {"words": header_words[:3], "x0": 100, "y0": 100, "x1": 358, "y1": 112},
            {"words": result_words[:3], "x0": 100, "y0": 145, "x1": 368, "y1": 157},
            {"words": header_words[3:], "x0": 460, "y0": 170, "x1": 486, "y1": 182},
            {"words": result_words[3:], "x0": 462, "y0": 215, "x1": 482, "y1": 227},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 700, 300)):
            items = _build_properties_overlay_items_from_column_words(
                page=page,
                field_values={"Rm": "387,0", "Rp0.2": "351,0", "A%": "13,5", "HB": "109,0"},
            )

        by_field = {item.field: item for item in items}
        self.assertIn("HB", by_field)
        left, _top, right, _bottom = [int(value) for value in by_field["HB"].bbox.split(",")]
        self.assertLess(left, 462)
        self.assertGreaterEqual(right, 482)

    def test_properties_overlay_recognizes_grupa_a_column_written_as_single_a(self):
        page = SimpleNamespace(id=1, numero_pagina=1, immagine_pagina_storage_key="page.png")
        header_words = [
            {"text": "Rm", "left": 260, "top": 100, "width": 20, "height": 12},
            {"text": "R0,2", "left": 390, "top": 100, "width": 34, "height": 12},
            {"text": "A", "left": 520, "top": 100, "width": 14, "height": 12},
            {"text": "Hardness", "left": 650, "top": 100, "width": 60, "height": 12},
            {"text": "IACS", "left": 925, "top": 185, "width": 38, "height": 12},
        ]
        percent_words = [
            {"text": "[MPa]", "left": 255, "top": 122, "width": 40, "height": 12},
            {"text": "[MPa]", "left": 385, "top": 122, "width": 40, "height": 12},
            {"text": "[%]", "left": 515, "top": 122, "width": 26, "height": 12},
            {"text": "[HB]", "left": 660, "top": 122, "width": 30, "height": 12},
        ]
        t005_words = [
            {"text": "T005", "left": 120, "top": 170, "width": 38, "height": 12},
            {"text": "599", "normalized": "599", "left": 260, "top": 170, "width": 26, "height": 12},
            {"text": "565", "normalized": "565", "left": 390, "top": 170, "width": 26, "height": 12},
            {"text": "11.4", "normalized": "11.4", "left": 520, "top": 170, "width": 30, "height": 12},
            {"text": "170", "normalized": "170", "left": 650, "top": 170, "width": 26, "height": 12},
            {"text": "35.6", "normalized": "35.6", "left": 925, "top": 210, "width": 30, "height": 12},
        ]
        t006_words = [
            {"text": "T006", "left": 120, "top": 195, "width": 38, "height": 12},
            {"text": "598", "normalized": "598", "left": 260, "top": 195, "width": 26, "height": 12},
            {"text": "561", "normalized": "561", "left": 390, "top": 195, "width": 26, "height": 12},
            {"text": "13.5", "normalized": "13.5", "left": 520, "top": 195, "width": 30, "height": 12},
            {"text": "169", "normalized": "169", "left": 650, "top": 195, "width": 26, "height": 12},
        ]
        line_boxes = [
            {"words": header_words[:4], "x0": 260, "y0": 100, "x1": 710, "y1": 112},
            {"words": percent_words, "x0": 255, "y0": 122, "x1": 690, "y1": 134},
            {"words": t005_words, "x0": 120, "y0": 170, "x1": 955, "y1": 222},
            {"words": t006_words, "x0": 120, "y0": 195, "x1": 676, "y1": 207},
            {"words": header_words[4:], "x0": 925, "y0": 185, "x1": 963, "y1": 197},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 1200, 600)):
            items = _build_properties_overlay_items_from_column_words(
                page=page,
                field_values={"Rm": "598", "Rp0.2": "561", "A%": "11,4", "HB": "169", "IACS%": "35,6"},
            )

        by_field = {item.field: item for item in items}
        self.assertIn("A%", by_field)
        self.assertEqual(by_field["A%"].bbox, "520,170,550,182")


if __name__ == "__main__":
    unittest.main()
