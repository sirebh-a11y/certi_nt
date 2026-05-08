import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.acquisition.schemas import DocumentCoreOverlayPreviewItemResponse
from app.modules.acquisition.service import (
    _build_document_core_overlay_items_from_value_ocr_window,
    _merge_document_core_overlay_items_prefer_existing,
)


def _words(tokens, *, left=80, top=100):
    cursor = left
    words = []
    for token in tokens:
        width = max(len(token) * 7, 18)
        words.append({"text": token, "left": cursor, "top": top, "width": width, "height": 12})
        cursor += width + 16
    return words


def _line(tokens, *, top):
    words = _words(tokens, top=top)
    return {
        "x0": min(word["left"] for word in words),
        "y0": top,
        "x1": max(word["left"] + word["width"] for word in words),
        "y1": top + 12,
        "words": words,
    }


class DocumentCoreOverlayTest(unittest.TestCase):
    def test_certificate_value_window_finds_arconic_identity_block(self):
        page = SimpleNamespace(id=1, numero_pagina=1, immagine_pagina_storage_key="page.png")
        row = SimpleNamespace(
            lega_base="6082 F",
            diametro="87",
            cdq="EEP73062-44270958",
            colata="C70025341313",
            ddt="28209127",
            peso="3999",
            ordine="213",
        )
        document = SimpleNamespace(pages=[page])
        line_boxes = [
            {
                "x0": 100,
                "y0": 120,
                "x1": 820,
                "y1": 145,
                "words": [
                    {"text": "Cert", "left": 100, "top": 120, "width": 30, "height": 12},
                    {"text": "EEP73062-44270958", "left": 140, "top": 120, "width": 125, "height": 12},
                    {"text": "Delivery", "left": 330, "top": 120, "width": 48, "height": 12},
                    {"text": "28209127", "left": 385, "top": 120, "width": 62, "height": 12},
                    {"text": "Order", "left": 520, "top": 120, "width": 36, "height": 12},
                    {"text": "213", "left": 562, "top": 120, "width": 25, "height": 12},
                    {"text": "3999", "left": 680, "top": 120, "width": 34, "height": 12},
                ],
            },
            {
                "x0": 100,
                "y0": 150,
                "x1": 820,
                "y1": 175,
                "words": [
                    {"text": "ROUND", "left": 100, "top": 150, "width": 45, "height": 12},
                    {"text": "BAR", "left": 150, "top": 150, "width": 26, "height": 12},
                    {"text": "RD087,00", "left": 185, "top": 150, "width": 58, "height": 12},
                    {"text": "6082", "left": 255, "top": 150, "width": 34, "height": 12},
                    {"text": "F", "left": 296, "top": 150, "width": 9, "height": 12},
                    {"text": "C70025341313", "left": 340, "top": 150, "width": 95, "height": 12},
                ],
            },
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 900, 400)):
            items = _build_document_core_overlay_items_from_value_ocr_window(
                row=row,
                document=document,
                source_key="certificato",
                value_map={},
            )

        by_field = {item.field: item for item in items}
        self.assertIn("material_block", by_field)
        self.assertIn("cdq", by_field)
        self.assertIn("ddt", by_field)
        self.assertIn("ordine", by_field)
        self.assertEqual(by_field["ddt"].bbox, "385,120,447,132")

    def test_ddt_value_window_prefers_row_with_matching_cast_and_weight(self):
        page = SimpleNamespace(id=2, numero_pagina=1, immagine_pagina_storage_key="page.png")
        row = SimpleNamespace(
            lega_base="6082 F",
            diametro="87",
            cdq="EEP73062-44270958",
            colata="C70025341313",
            ddt="28209127",
            peso="3999",
            ordine="213",
        )
        document = SimpleNamespace(pages=[page])
        line_boxes = [
            {
                "x0": 80,
                "y0": 100,
                "x1": 760,
                "y1": 120,
                "words": [
                    {"text": "Delivery", "left": 80, "top": 100, "width": 48, "height": 12},
                    {"text": "28209127", "left": 135, "top": 100, "width": 62, "height": 12},
                    {"text": "Order", "left": 260, "top": 100, "width": 36, "height": 12},
                    {"text": "213", "left": 302, "top": 100, "width": 25, "height": 12},
                ],
            },
            {
                "x0": 80,
                "y0": 220,
                "x1": 820,
                "y1": 242,
                "words": [
                    {"text": "ROUND", "left": 80, "top": 220, "width": 45, "height": 12},
                    {"text": "BAR", "left": 130, "top": 220, "width": 26, "height": 12},
                    {"text": "RD087,00", "left": 170, "top": 220, "width": 58, "height": 12},
                    {"text": "6082", "left": 240, "top": 220, "width": 34, "height": 12},
                    {"text": "F", "left": 282, "top": 220, "width": 9, "height": 12},
                    {"text": "C70000000000", "left": 330, "top": 220, "width": 95, "height": 12},
                    {"text": "2000", "left": 470, "top": 220, "width": 34, "height": 12},
                ],
            },
            {
                "x0": 80,
                "y0": 270,
                "x1": 820,
                "y1": 292,
                "words": [
                    {"text": "ROUND", "left": 80, "top": 270, "width": 45, "height": 12},
                    {"text": "BAR", "left": 130, "top": 270, "width": 26, "height": 12},
                    {"text": "RD087,00", "left": 170, "top": 270, "width": 58, "height": 12},
                    {"text": "6082", "left": 240, "top": 270, "width": 34, "height": 12},
                    {"text": "F", "left": 282, "top": 270, "width": 9, "height": 12},
                    {"text": "C70025341313", "left": 330, "top": 270, "width": 95, "height": 12},
                    {"text": "3999", "left": 470, "top": 270, "width": 34, "height": 12},
                    {"text": "EEP73062-44270958", "left": 540, "top": 270, "width": 125, "height": 12},
                ],
            },
        ]

        with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 900, 400)):
            items = _build_document_core_overlay_items_from_value_ocr_window(
                row=row,
                document=document,
                source_key="ddt",
                value_map={},
            )

        by_field = {item.field: item for item in items}
        self.assertIn("material_block", by_field)
        self.assertIn("cdq", by_field)
        self.assertEqual(by_field["material_block"].bbox, "170,270,504,282")
        self.assertEqual(by_field["cdq"].bbox, "540,270,665,282")

    def test_value_window_handles_all_supplier_core_rows(self):
        cases = [
            {
                "supplier": "aluminium_bozen",
                "row": {
                    "lega_base": "2014 F",
                    "diametro": "98",
                    "cdq": "145550",
                    "colata": "43698",
                    "ddt": "1267",
                    "peso": "4159",
                    "ordine": "210-20",
                },
                "wrong": ["2014", "F", "DIAM", "98", "145550", "99999", "2000", "210-20"],
                "right": ["2014", "F", "DIAM", "98", "145550", "43698", "4159", "1267", "210-20"],
            },
            {
                "supplier": "aww",
                "row": {
                    "lega_base": "6082A T1",
                    "diametro": "35",
                    "cdq": "Z25-02034",
                    "colata": "401479",
                    "ddt": "14142236",
                    "peso": "3498",
                    "ordine": "351",
                },
                "wrong": ["6082A", "T1", "Ø35", "Z25-02034", "999999", "2000", "351"],
                "right": ["6082A", "T1", "Ø35", "Z25-02034", "401479", "3498", "14142236", "351"],
            },
            {
                "supplier": "impol",
                "row": {
                    "lega_base": "6082 F",
                    "diametro": "32",
                    "cdq": "1505/A",
                    "colata": "398850",
                    "ddt": "1505-11",
                    "peso": "1603",
                    "ordine": "352",
                },
                "wrong": ["6082", "F", "DIA", "32", "1505/A", "398850", "9999", "352"],
                "right": ["6082", "F", "DIA", "32", "1505/A", "398850", "1603", "1505-11", "352"],
            },
            {
                "supplier": "leichtmetall",
                "row": {
                    "lega_base": "6082",
                    "diametro": "228",
                    "cdq": "94668",
                    "colata": "94668",
                    "ddt": "80008535",
                    "peso": "5014",
                    "ordine": "19",
                },
                "wrong": ["6082", "DIAMETER", "228", "94668", "3000", "80008519", "19"],
                "right": ["6082", "DIAMETER", "228", "94668", "5014", "80008535", "19"],
            },
            {
                "supplier": "metalba",
                "row": {
                    "lega_base": "6082F F",
                    "diametro": "48",
                    "cdq": "26-0746",
                    "colata": "26052B",
                    "ddt": "26-00960",
                    "peso": "1334",
                    "ordine": "45/26",
                },
                "wrong": ["6082F", "F", "DIAM", "48", "26-0746", "99999B", "2000", "45/26"],
                "right": ["6082F", "F", "DIAM", "48", "26-0746", "26052B", "1334", "26-00960", "45/26"],
            },
            {
                "supplier": "neuman",
                "row": {
                    "lega_base": "6082",
                    "diametro": "100",
                    "cdq": "25531",
                    "colata": "25531",
                    "ddt": "71015878",
                    "peso": "3498",
                    "ordine": "351",
                },
                "wrong": ["6082", "DIAMETER", "100", "25531", "2000", "71015878", "351"],
                "right": ["6082", "DIAMETER", "100", "25531", "3498", "71015878", "351"],
            },
            {
                "supplier": "grupa_kety",
                "row": {
                    "lega_base": "7150 F",
                    "diametro": "44",
                    "cdq": "10033539/25",
                    "colata": "25E-7870",
                    "ddt": "12594",
                    "peso": "1331",
                    "ordine": "154",
                },
                "wrong": ["7150", "F", "ROUND", "44", "10033539/25", "25E-7870", "1902", "154"],
                "right": ["7150", "F", "ROUND", "44", "10033539/25", "25E-7870", "1331", "12594", "154"],
            },
            {
                "supplier": "zalco",
                "row": {
                    "lega_base": "6082 HO",
                    "diametro": "203",
                    "cdq": "20285",
                    "colata": "2023-42669",
                    "ddt": "20285",
                    "peso": "17975",
                    "ordine": "20230145",
                },
                "wrong": ["6082", "HO", "FORMAT", "203", "20285", "2023-42669", "2400", "20230145"],
                "right": ["6082", "HO", "FORMAT", "203", "20285", "2023-42669", "17975", "20230145"],
            },
        ]

        for case in cases:
            with self.subTest(case["supplier"]):
                page = SimpleNamespace(id=100, numero_pagina=1, immagine_pagina_storage_key="page.png")
                row = SimpleNamespace(**case["row"])
                document = SimpleNamespace(pages=[page])
                line_boxes = [
                    _line(["HEADER", case["supplier"]], top=80),
                    _line(case["wrong"], top=140),
                    _line(case["right"], top=210),
                ]

                with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 1200, 500)):
                    items = _build_document_core_overlay_items_from_value_ocr_window(
                        row=row,
                        document=document,
                        source_key="ddt",
                        value_map={},
                    )

                by_field = {item.field: item for item in items}
                self.assertIn("material_block", by_field)
                self.assertIn("cdq", by_field)
                self.assertEqual(by_field["material_block"].bbox.split(",")[1], "210")

    def test_certificate_value_window_handles_all_supplier_identity_rows(self):
        cases = [
            ("aluminium_bozen", "100036", "23039A3", "2415", "6082 F", "52"),
            ("aww", "Z21-42315", "305431", "3498", "6082", "100"),
            ("impol", "3078/A", "398850", "3720", "6082 F", "24"),
            ("leichtmetall", "94752", "94752", "12211", "6082", "228"),
            ("metalba", "26-0746", "26052B", "1334", "6082F F", "48"),
            ("neuman", "25531", "25531", "3498", "6082", "100"),
            ("arconic_hannover", "EEP73062-44270958", "C70025341313", "3999", "6082 F", "87"),
            ("grupa_kety", "10033539/25", "25E-7870", "1331", "7150 F", "44"),
            ("zalco", "20285", "2023-42669", "17975", "6082 HO", "203"),
        ]

        for supplier, cdq, colata, peso, lega, diametro in cases:
            with self.subTest(supplier):
                page = SimpleNamespace(id=200, numero_pagina=1, immagine_pagina_storage_key="page.png")
                row = SimpleNamespace(
                    lega_base=lega,
                    diametro=diametro,
                    cdq=cdq,
                    colata=colata,
                    ddt="20285",
                    peso=peso,
                    ordine="154",
                )
                document = SimpleNamespace(pages=[page])
                right = ["CERT", cdq, "CAST", colata, "WEIGHT", peso, "ALLOY", *lega.split(), "DIAM", diametro]
                line_boxes = [
                    _line(["OLD", cdq, "CAST", "WRONG", "WEIGHT", "9999"], top=110),
                    _line(right, top=190),
                ]

                with patch("app.modules.acquisition.service._extract_ocr_line_boxes", return_value=(line_boxes, 1200, 500)):
                    items = _build_document_core_overlay_items_from_value_ocr_window(
                        row=row,
                        document=document,
                        source_key="certificato",
                        value_map={},
                    )

                by_field = {item.field: item for item in items}
                self.assertIn("material_block", by_field)
                self.assertIn("cdq", by_field)
                self.assertEqual(by_field["material_block"].bbox.split(",")[1], "190")

    def test_value_window_replaces_generic_material_block_that_points_to_address(self):
        existing = [
            DocumentCoreOverlayPreviewItemResponse(
                page_id=1,
                page_number=1,
                field="material_block",
                bbox="20,40,400,90",
                image_width=1200,
                image_height=500,
            )
        ]
        candidates = [
            DocumentCoreOverlayPreviewItemResponse(
                page_id=1,
                page_number=1,
                field="material_block",
                bbox="80,210,500,222",
                image_width=1200,
                image_height=500,
            ),
            DocumentCoreOverlayPreviewItemResponse(
                page_id=1,
                page_number=1,
                field="cdq",
                bbox="540,210,620,222",
                image_width=1200,
                image_height=500,
            ),
        ]

        merged = _merge_document_core_overlay_items_prefer_existing(
            existing,
            candidates,
            replace_material_block=True,
        )

        by_field = {item.field: item for item in merged}
        self.assertEqual(by_field["material_block"].bbox, "80,210,500,222")
        self.assertEqual(by_field["cdq"].bbox, "540,210,620,222")


if __name__ == "__main__":
    unittest.main()
