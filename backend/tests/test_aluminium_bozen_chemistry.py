import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.acquisition.service import (
    _build_chemistry_overlay_items,
    _build_chemistry_overlay_items_from_header_order,
    _parse_aluminium_bozen_chemistry_from_lines,
)


class AluminiumBozenChemistryTest(unittest.TestCase):
    def test_parser_counts_ga_column_without_shift(self):
        lines = [
            "COMPOSIZIONE CHIMICA / CHEMICAL COMPOSITION",
            "Nr COLATA %Si %Fe %Cu %Mn %Mg %Cr %Ni %Zn %Ga %V %Ti %Pb %Zr %Bi %Sn",
            "23039A3 0,630 0,340 4,350 0,680 0,590 0,060 0,010 0,200 0,000 0,000 0,030 0,030 0,100 0,005 0,006",
            "NORMA Min. 0,500 0,000 3,900 0,400 0,200 0,000 0,000 0,000 0,000 0,000 0,000 0,000 0,000 0,000 0,000",
        ]

        matches = _parse_aluminium_bozen_chemistry_from_lines(lines, page_id=1)

        self.assertEqual(matches["Si"]["final"], "0.630")
        self.assertEqual(matches["Zn"]["final"], "0.200")
        self.assertEqual(matches["V"]["final"], "0.000")
        self.assertEqual(matches["Ti"]["final"], "0.030")
        self.assertEqual(matches["Pb"]["final"], "0.030")
        self.assertEqual(matches["Zr"]["final"], "0.100")
        self.assertEqual(matches["Bi"]["final"], "0.005")
        self.assertEqual(matches["Sn"]["final"], "0.006")

    def test_overlay_header_order_fills_rightmost_sn_box(self):
        page = SimpleNamespace(id=1, numero_pagina=1)
        header_words = [
            {"text": token, "left": left, "top": 20, "width": 20, "height": 10}
            for left, token in enumerate(
                ["%Si", "%Fe", "%Cu", "%Mn", "%Mg", "%Cr", "%Ni", "%Zn", "%Ga", "%V", "%Ti", "%Pb", "%Zr", "%Bi", "%Sn"],
                start=10,
            )
        ]
        value_words = [
            {"text": token, "normalized": token, "left": left, "top": 60, "width": 18, "height": 10}
            for left, token in enumerate(
                ["23039A3", "0,630", "0,340", "4,350", "0,680", "0,590", "0,060", "0,010", "0,200", "0,000", "0,000", "0,030", "0,030", "0,100", "0,005", "0,006"],
                start=5,
            )
        ]
        line_boxes = [
            {"words": header_words, "x0": 10, "y0": 20, "x1": 25, "y1": 30},
            {"words": value_words, "x0": 5, "y0": 60, "x1": 21, "y1": 70},
        ]
        value_line = line_boxes[1]

        items = _build_chemistry_overlay_items_from_header_order(
            page=page,
            line_box=value_line,
            line_boxes=line_boxes,
            field_values={"Sn": "0,005"},
            existing_fields=set(),
            image_width=100,
            image_height=100,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].field, "Sn")
        self.assertEqual(items[0].bbox, "20,60,38,70")

    def test_overlay_prefers_header_column_when_duplicate_values_exist(self):
        page = SimpleNamespace(id=1, numero_pagina=1)
        header_tokens = ["%Si", "%Fe", "%Cu", "%Mn", "%Mg", "%Cr", "%Ni", "%Zn", "%Ga", "%V", "%Ti", "%Pb", "%Zr", "%Bi", "%Sn"]
        value_tokens = ["23039A3", "0,630", "0,340", "4,350", "0,680", "0,590", "0,060", "0,010", "0,200", "0,000", "0,000", "0,030", "0,030", "0,100", "0,005", "0,006"]
        header_words = [
            {"text": token, "left": 100 + index * 10, "top": 20, "width": 8, "height": 10}
            for index, token in enumerate(header_tokens)
        ]
        value_words = [
            {"text": token, "normalized": token, "left": 50 if index == 0 else 90 + index * 10, "top": 60, "width": 8, "height": 10}
            for index, token in enumerate(value_tokens)
        ]
        line_boxes = [
            {"words": header_words, "x0": 100, "y0": 20, "x1": 248, "y1": 30},
            {"words": value_words, "x0": 50, "y0": 60, "x1": 248, "y1": 70},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 300, 100)):
            items = _build_chemistry_overlay_items(
                page=page,
                line_box=line_boxes[1],
                field_values={"V": "0,000", "Ti": "0,030", "Sn": "0,006"},
                matched_fields=["V", "Ti", "Sn"],
                image_width=300,
                image_height=100,
            )

        by_field = {item.field: item for item in items}
        self.assertEqual(by_field["V"].bbox, "190,60,198,70")
        self.assertEqual(by_field["Ti"].bbox, "200,60,208,70")
        self.assertEqual(by_field["Sn"].bbox, "240,60,248,70")


if __name__ == "__main__":
    unittest.main()
