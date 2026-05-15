import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import _sanitize_impol_vision_certificate_fields
from app.modules.document_reader.matching import detect_certificate_core_matches


class ImpolCertificateNumberTest(unittest.TestCase):
    def test_ai_certificate_number_preserves_slash_and_hash_suffixes(self):
        cases = {
            "No. 27781/b": "27781/B",
            "No. 28691/a": "28691/A",
            "No. 28691/b": "28691/B",
            "No. 29289#a": "29289#A",
            "No. 29289#b": "29289#B",
        }

        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                fields = _sanitize_impol_vision_certificate_fields(
                    {"numero_certificato": raw_value},
                    "certificate_core_context",
                )
                self.assertEqual(fields["numero_certificato_certificato"]["value"], expected)

    def test_local_certificate_parser_preserves_impol_hash_suffix(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto="Inspection certificate\nNo. 29289#b\nCustomer Order No. 334",
            ocr_text=None,
        )

        matches = detect_certificate_core_matches([page], supplier_key="impol")

        self.assertEqual(matches["numero_certificato_certificato"]["final"], "29289#B")

    def test_local_certificate_parser_does_not_take_customer_order_as_impol_number(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto="Customer Order No. 334\nPacking list No. 29289",
            ocr_text=None,
        )

        matches = detect_certificate_core_matches([page], supplier_key="impol")

        self.assertNotIn("numero_certificato_certificato", matches)


if __name__ == "__main__":
    unittest.main()
