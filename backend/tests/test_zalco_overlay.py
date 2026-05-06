import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.acquisition.service import (
    _build_zalco_chemistry_overlay_items_from_analysis_block,
    _build_zalco_chemistry_overlay_items_from_compact_table,
)


class ZalcoOverlayTest(unittest.TestCase):
    def test_zalco_overlay_prefers_compact_row_anchored_by_cast_and_weight(self):
        page = SimpleNamespace(id=11, numero_pagina=1, immagine_pagina_storage_key="page.png")
        row = SimpleNamespace(
            values=[
                SimpleNamespace(
                    blocco="ddt",
                    campo="colata",
                    valore_finale="2023-42669",
                    valore_standardizzato=None,
                    valore_grezzo=None,
                ),
                SimpleNamespace(
                    blocco="ddt",
                    campo="peso",
                    valore_finale="17975",
                    valore_standardizzato=None,
                    valore_grezzo=None,
                ),
            ]
        )
        line_boxes = [
            {
                "x0": 160,
                "y0": 2655,
                "x1": 2348,
                "y1": 2769,
                "words": [
                    {"text": "12023", "left": 308, "top": 2663, "width": 108, "height": 32},
                    {"text": "42669", "left": 448, "top": 2670, "width": 123, "height": 57},
                    {"text": "17975", "left": 627, "top": 2677, "width": 131, "height": 50},
                    {"text": "1,3", "normalized": "1,3", "left": 792, "top": 2682, "width": 66, "height": 33},
                    {"text": "0,46", "normalized": "0,46", "left": 989, "top": 2689, "width": 93, "height": 34},
                    {"text": "0,06", "normalized": "0,06", "left": 1189, "top": 2697, "width": 93, "height": 32},
                    {"text": "0,5", "normalized": "0,5", "left": 1389, "top": 2703, "width": 66, "height": 33},
                    {"text": "0,8", "normalized": "0,8", "left": 1587, "top": 2710, "width": 65, "height": 33},
                    {"text": "0,06", "normalized": "0,06", "left": 1785, "top": 2716, "width": 92, "height": 34},
                    {"text": "0,04", "normalized": "0,04", "left": 1983, "top": 2722, "width": 91, "height": 34},
                    {"text": "0,02", "normalized": "0,02", "left": 2183, "top": 2729, "width": 89, "height": 33},
                ],
            }
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 2480, 3507)):
            items = _build_zalco_chemistry_overlay_items_from_compact_table(
                page=page,
                row=row,
                field_values={
                    "Si": "1,3",
                    "Fe": "0,46",
                    "Cu": "0,06",
                    "Mn": "0,5",
                    "Mg": "0,8",
                    "Cr": "0,06",
                    "Zn": "0,04",
                    "Ti": "0,02",
                },
            )

        by_field = {item.field: item for item in items}
        self.assertEqual(set(by_field), {"Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Zn", "Ti"})
        self.assertEqual(by_field["Si"].bbox, "792,2682,858,2715")
        self.assertEqual(by_field["Cr"].bbox, "1785,2716,1877,2750")

    def test_zalco_overlay_uses_label_value_pairs_across_two_analysis_lines(self):
        page = SimpleNamespace(id=1, numero_pagina=2, immagine_pagina_storage_key="page.png")
        line_boxes = [
            {
                "x0": 216,
                "y0": 993,
                "x1": 1416,
                "y1": 1040,
                "words": [
                    {"text": "COULEE", "left": 216, "top": 993, "width": 90, "height": 20},
                    {"text": "ANALYSE", "left": 1278, "top": 1015, "width": 120, "height": 20},
                ],
            },
            {
                "x0": 217,
                "y0": 1095,
                "x1": 2330,
                "y1": 1164,
                "words": [
                    {"text": "42669", "left": 217, "top": 1095, "width": 80, "height": 20},
                    {"text": "SI:", "left": 1280, "top": 1117, "width": 55, "height": 20},
                    {"text": "1,3", "normalized": "1,3", "left": 1381, "top": 1117, "width": 50, "height": 20},
                    {"text": "FE:", "left": 1577, "top": 1122, "width": 55, "height": 20},
                    {"text": "0,46", "normalized": "0,46", "left": 1677, "top": 1122, "width": 70, "height": 20},
                    {"text": "CU:", "left": 1869, "top": 1126, "width": 55, "height": 20},
                    {"text": "0,06", "normalized": "0,06", "left": 1970, "top": 1126, "width": 70, "height": 20},
                    {"text": "MN:", "left": 2162, "top": 1132, "width": 55, "height": 20},
                    {"text": "0,5", "normalized": "0,5", "left": 2265, "top": 1131, "width": 50, "height": 20},
                ],
            },
            {
                "x0": 427,
                "y0": 1143,
                "x1": 2353,
                "y1": 1209,
                "words": [
                    {"text": "001", "left": 427, "top": 1143, "width": 40, "height": 20},
                    {"text": "MG:", "left": 1277, "top": 1161, "width": 55, "height": 20},
                    {"text": "0,8", "normalized": "0,8", "left": 1380, "top": 1161, "width": 50, "height": 20},
                    {"text": "CR:", "left": 1575, "top": 1166, "width": 55, "height": 20},
                    {"text": "0,06", "normalized": "0,06", "left": 1676, "top": 1167, "width": 70, "height": 20},
                    {"text": "ZN:", "left": 1870, "top": 1171, "width": 55, "height": 20},
                    {"text": "0,04", "normalized": "0,04", "left": 1970, "top": 1171, "width": 70, "height": 20},
                    {"text": "TI:", "left": 2163, "top": 1176, "width": 55, "height": 20},
                    {"text": "0,02", "normalized": "0,02", "left": 2264, "top": 1176, "width": 70, "height": 20},
                ],
            },
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 2480, 3507)):
            items = _build_zalco_chemistry_overlay_items_from_analysis_block(
                page=page,
                row=None,
                field_values={
                    "Si": "1,3",
                    "Fe": "0,46",
                    "Cu": "0,06",
                    "Mn": "0,5",
                    "Mg": "0,8",
                    "Cr": "0,06",
                    "Zn": "0,04",
                    "Ti": "0,02",
                },
            )

        by_field = {item.field: item for item in items}
        self.assertEqual(set(by_field), {"Si", "Fe", "Cu", "Mn", "Mg", "Cr", "Zn", "Ti"})
        self.assertEqual(by_field["Mg"].bbox, "1380,1161,1430,1181")
        self.assertEqual(by_field["Ti"].bbox, "2264,1176,2334,1196")


if __name__ == "__main__":
    unittest.main()
