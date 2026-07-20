import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _normalize_arconic_certificate_number,
    _sanitize_aluminium_bozen_vision_certificate_fields,
    _sanitize_impol_vision_certificate_fields,
    _sanitize_vision_ddt_fields,
)
from app.modules.document_reader.matching import detect_certificate_core_matches, detect_ddt_core_matches


class CertificateNumberCaseTest(unittest.TestCase):
    def test_ai_certificate_number_preserves_slash_and_hash_suffixes(self):
        cases = {
            "No. 27781/b": "27781/b",
            "No. 28691/a": "28691/a",
            "No. 28691/B": "28691/B",
            "No. 29289#a": "29289#a",
            "No. 29289#B": "29289#B",
            "No. 17394 # a": "17394#a",
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

        self.assertEqual(matches["numero_certificato_certificato"]["final"], "29289#b")

    def test_generic_certificate_parser_preserves_identifier_case(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto="Certificate No. 17394#a",
            ocr_text=None,
        )

        matches = detect_certificate_core_matches([page])

        self.assertEqual(matches["numero_certificato_certificato"]["final"], "17394#a")

    def test_generic_ddt_parser_preserves_explicit_cdq_case(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto="CdQ: 17394#a",
            ocr_text=None,
        )

        matches = detect_ddt_core_matches([page])

        self.assertEqual(matches["cdq"]["final"], "17394#a")

    def test_other_supplier_local_parsers_preserve_certificate_case(self):
        cases = (
            ("aww", "Zeugnis-Nr. z24-90172", "z24-90172"),
            ("aluminium_bozen", "CERT.NO\n12345a", "12345a"),
        )

        for supplier_key, text, expected in cases:
            with self.subTest(supplier_key=supplier_key):
                page = SimpleNamespace(id=1, testo_estratto=text, ocr_text=None)
                matches = detect_certificate_core_matches([page], supplier_key=supplier_key)
                self.assertEqual(matches["numero_certificato_certificato"]["final"], expected)

    def test_other_supplier_ai_sanitizers_preserve_certificate_case(self):
        bozen = _sanitize_aluminium_bozen_vision_certificate_fields(
            {
                "certificate_number_raw": {
                    "value": "12345a",
                    "evidence": "CERT.NO 12345a",
                    "source_crop": "certificate_core",
                }
            }
        )
        generic_ddt = _sanitize_vision_ddt_fields(
            {
                "numero_certificato_ddt": {
                    "value": "17394#a",
                    "evidence": "Cert. No. 17394#a",
                    "source_crop": "ddt_core",
                }
            }
        )

        self.assertEqual(bozen["numero_certificato_certificato"]["value"], "12345a")
        self.assertEqual(generic_ddt["numero_certificato_ddt"]["value"], "17394#a")
        self.assertEqual(_normalize_arconic_certificate_number("eep73417"), "eep73417")

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
