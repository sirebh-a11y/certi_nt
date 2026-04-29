import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.modules.acquisition.service import (
    _ddt_row_field_fallback_value,
    _enrich_aww_ai_row_groups_from_pages,
    _mask_aww_supplier_occurrence_blocks,
    _normalize_aww_alloy_from_text,
)
from app.modules.document_reader.matching import _normalize_aww_alloy
from app.modules.document_reader.schemas import ReaderRowSplitCandidateResponse


class AwwDdtAlloyGuardrailsTest(unittest.TestCase):
    def test_aww_alloy_normalizers_reject_temper_without_base_alloy(self):
        wrong_article_context = "A6L043070 (T1 535)"

        self.assertIsNone(_normalize_aww_alloy_from_text(wrong_article_context))
        self.assertIsNone(_normalize_aww_alloy(wrong_article_context))
        self.assertEqual(_normalize_aww_alloy_from_text("EN AW-6082A/535/T1"), "6082A T1")
        self.assertEqual(_normalize_aww_alloy("EN AW-6082A/535/T1"), "6082A T1")

    def test_aww_ai_candidate_falls_back_to_document_alloy_code(self):
        payload = {
            "alloy_temper_raw": "A6L043070 (T1 535)",
            "source_crops": ["page2_row_groups_page"],
        }
        candidate = ReaderRowSplitCandidateResponse(
            candidate_index=1,
            supplier_key="aww",
            article_code="A6L043070",
            lega=None,
            ai_row_payload_raw=json.dumps(payload),
        )
        pages = [
            SimpleNamespace(
                numero_pagina=2,
                ocr_text="Your part number: A6L043070\nalloy code AWW: EN AW-6082A/535/T1\n",
                testo_estratto=None,
            )
        ]

        enriched = _enrich_aww_ai_row_groups_from_pages([candidate], pages)

        self.assertEqual(enriched[0].lega, "6082A T1")
        self.assertEqual(json.loads(enriched[0].ai_row_payload_raw)["alloy_temper_raw"], "EN AW-6082A/535/T1")

    def test_aww_temper_only_does_not_protect_row_lega(self):
        row = SimpleNamespace(
            supplier=None,
            fornitore_raw="Aluminium-Werke Wutöschingen AG & Co. KG",
            ddt_document=None,
            certificate_document=None,
            lega_base="T1",
        )

        self.assertIsNone(_ddt_row_field_fallback_value(row, "lega"))

    def test_aww_masking_keeps_technical_alloy_code_line(self):
        image = Image.new("RGB", (420, 160), "white")
        words = [
            {"text": "alloy", "left": 20, "top": 30, "right": 60, "bottom": 45, "line_key": (1, 1, 1)},
            {"text": "code", "left": 66, "top": 30, "right": 104, "bottom": 45, "line_key": (1, 1, 1)},
            {"text": "AWW:", "left": 110, "top": 30, "right": 152, "bottom": 45, "line_key": (1, 1, 1)},
            {"text": "EN", "left": 158, "top": 30, "right": 180, "bottom": 45, "line_key": (1, 1, 1)},
            {"text": "AW-6082A/535/T1", "left": 186, "top": 30, "right": 330, "bottom": 45, "line_key": (1, 1, 1)},
            {"text": "Aluminium-Werke", "left": 20, "top": 90, "right": 150, "bottom": 105, "line_key": (1, 1, 2)},
            {"text": "AWW.DE", "left": 156, "top": 90, "right": 220, "bottom": 105, "line_key": (1, 1, 2)},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_word_blocks", return_value=words):
            _mask_aww_supplier_occurrence_blocks(image, [{"text": "dummy", "left": 0, "top": 0, "right": 1, "bottom": 1}])

        self.assertEqual(image.getpixel((210, 36)), (255, 255, 255))
        self.assertEqual(image.getpixel((80, 96)), (0, 0, 0))

    def test_aww_masking_keeps_technical_fields_on_same_ocr_line(self):
        image = Image.new("RGB", (520, 120), "white")
        words = [
            {"text": "Forgialluminio", "left": 20, "top": 35, "right": 135, "bottom": 52, "line_key": (1, 1, 1)},
            {"text": "3", "left": 140, "top": 35, "right": 150, "bottom": 52, "line_key": (1, 1, 1)},
            {"text": "S.R.L.", "left": 156, "top": 35, "right": 200, "bottom": 52, "line_key": (1, 1, 1)},
            {"text": "Werkstoff", "left": 260, "top": 35, "right": 335, "bottom": 52, "line_key": (1, 1, 1)},
            {"text": "EN", "left": 350, "top": 35, "right": 372, "bottom": 52, "line_key": (1, 1, 1)},
            {"text": "AW-6082A", "left": 380, "top": 35, "right": 465, "bottom": 52, "line_key": (1, 1, 1)},
        ]

        with patch("app.modules.acquisition.service._extract_ocr_word_blocks", return_value=words):
            from app.modules.acquisition.service import _mask_aww_customer_occurrence_blocks

            _mask_aww_customer_occurrence_blocks(image, [{"text": "dummy", "left": 0, "top": 0, "right": 1, "bottom": 1}])

        self.assertEqual(image.getpixel((70, 42)), (0, 0, 0))
        self.assertEqual(image.getpixel((405, 42)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
