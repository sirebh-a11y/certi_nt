import json
import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _ddt_row_field_fallback_value,
    _enrich_aww_ai_row_groups_from_pages,
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


if __name__ == "__main__":
    unittest.main()
