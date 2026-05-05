import unittest

from app.modules.acquisition.rematch_bridge import (
    RematchDecision,
    build_certificate_bridge,
    build_ddt_bridge,
    score_bridge_match,
)
from app.modules.acquisition.service import (
    _format_arconic_certificate_cdq,
    _sanitize_arconic_hannover_ai_row_groups,
    _sanitize_arconic_hannover_vision_certificate_fields,
)
from app.modules.document_reader.matching import _extract_arconic_hannover_match_fields


class ArconicSupportTest(unittest.TestCase):
    def test_arconic_bridge_matches_real_27697432_case(self):
        left = build_ddt_bridge(
            row_values={
                "fornitore": "Arconic Hannover",
                "lega_base": "6111A",
                "diametro": "68",
                "colata": "C3802220451",
                "ddt": "27697432",
                "peso": "7656",
                "ordine": "318",
            },
            read_values={
                "article_code": "BG5203862",
                "customer_code": "A650680",
                "product_code": "1.1",
                "supplier_order_no": "7232107",
                "lot_batch_no": "43440412",
            },
            supplier_name="Arconic Hannover",
        )
        right = build_certificate_bridge(
            row_values={"fornitore": "Arconic Hannover", "cdq": "EEP66506-43440412"},
            read_values={
                "numero_certificato_certificato": "EEP66506-43440412",
                "lega_certificato": "6111A",
                "diametro_certificato": "68",
                "colata_certificato": "C3802220451",
                "ddt_certificato": "27697432",
                "peso_certificato": "7656",
                "ordine_cliente_certificato": "318",
                "articolo_certificato": "BG5203862",
                "codice_cliente_certificato": "A650680",
                "line_no_certificato": "1.1",
                "sales_order_number_certificato": "7232107",
                "lot_batch_no_certificato": "43440412",
            },
            supplier_name="Arconic Hannover",
        )

        result = score_bridge_match(left, right)

        self.assertEqual(result.decision, RematchDecision.STRONG, result)
        self.assertIn("colata", result.matched_fields)
        self.assertIn("article_code", result.matched_fields)
        self.assertIn("customer_code", result.matched_fields)

    def test_arconic_bridge_matches_same_ddt_multiple_certificate_rows(self):
        base_ddt = {
            "fornitore": "Arconic Hannover",
            "lega_base": "6082 F",
            "diametro": "87",
            "colata": "C70025341313",
            "ddt": "28209127",
            "peso": "3999",
            "ordine": "213",
        }
        first = build_ddt_bridge(
            row_values=base_ddt,
            read_values={"article_code": "BG5207530", "customer_code": "A62087030", "product_code": "2.1"},
            supplier_name="Arconic Hannover",
        )
        second = build_ddt_bridge(
            row_values={**base_ddt, "diametro": "98"},
            read_values={"article_code": "BG5207534", "customer_code": "A62098030", "product_code": "3.1"},
            supplier_name="Arconic Hannover",
        )
        cert_73062 = build_certificate_bridge(
            row_values={"fornitore": "Arconic Hannover", "cdq": "EEP73062-44270958"},
            read_values={
                "colata_certificato": "C70025341313",
                "ddt_certificato": "28209127",
                "ordine_cliente_certificato": "213",
                "diametro_certificato": "87",
                "articolo_certificato": "BG5207530",
                "codice_cliente_certificato": "A62087030",
                "line_no_certificato": "2.1",
            },
            supplier_name="Arconic Hannover",
        )

        self.assertEqual(score_bridge_match(first, cert_73062).decision, RematchDecision.STRONG)
        self.assertEqual(score_bridge_match(second, cert_73062).decision, RematchDecision.NONE)

    def test_arconic_certificate_cdq_uses_cert_number_and_job(self):
        self.assertEqual(_format_arconic_certificate_cdq("EEP73417", "44281864"), "EEP73417-44281864")
        self.assertEqual(_format_arconic_certificate_cdq("EEP73062", "44218360|44270958"), "EEP73062-44218360")
        self.assertEqual(_format_arconic_certificate_cdq("EEP73062", None), "EEP73062")

    def test_arconic_ddt_sanitizer_keeps_row_identity_fields(self):
        candidates = _sanitize_arconic_hannover_ai_row_groups(
            ddt_number_raw="Delivery Note 28209127",
            raw_rows=[
                {
                    "sales_order_raw": "7235306",
                    "customer_po_raw": "213",
                    "line_no_raw": "2.1",
                    "customer_item_number_raw": "A62087030",
                    "customer_item_description_raw": "DIA 87mm 6082-F round bar",
                    "arconic_item_number_raw": "BG5207530",
                    "die_dimension_raw": "RD087,00",
                    "cast_number_raw": "C70025341313",
                    "package_ids_raw": "44218360 44270958",
                    "net_weight_raw": "3.999",
                    "source_crops": ["page1_row_groups_page"],
                }
            ],
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.ddt_number, "28209127")
        self.assertEqual(candidate.customer_order_no, "213")
        self.assertEqual(candidate.product_code, "2.1")
        self.assertEqual(candidate.customer_code, "A62087030")
        self.assertEqual(candidate.article_code, "BG5207530")
        self.assertEqual(candidate.lega, "6082 F")
        self.assertEqual(candidate.diametro, "87")
        self.assertEqual(candidate.colata, "C70025341313")
        self.assertEqual(candidate.lot_batch_no, "44218360|44270958")

    def test_arconic_certificate_core_sanitizer_formats_cdq(self):
        fields = _sanitize_arconic_hannover_vision_certificate_fields(
            {
                "cert_number": "Cert Number EEP73417",
                "customer_po": "213",
                "delivery_note_no": "28209127",
                "customer_item_number": "A62087030",
                "arconic_item_number": "BG5207530",
                "item_description_raw": "RD087,00 6082 / F",
                "cast_job_number": "C70025341313/44281864",
                "net_weight_raw": "3999 KGM",
            },
            "page1_core_page",
        )

        self.assertEqual(fields["numero_certificato_certificato"]["value"], "EEP73417-44281864")
        self.assertEqual(fields["colata_certificato"]["value"], "C70025341313")
        self.assertEqual(fields["diametro_certificato"]["value"], "87")
        self.assertEqual(fields["lega_certificato"]["value"], "6082 F")

    def test_arconic_match_field_extractor_reads_customer_item_and_dimension(self):
        fields = _extract_arconic_hannover_match_fields(
            [
                "Cert Number EEP73062",
                "Sales Order Number 7235306",
                "Customer P/O 213 (EMPB)",
                "Delivery Note No. 28209127",
                "Line No. 2.1",
                "Customer Item No A62087030",
                "Item No. BG5207530",
                "Item Description RD087,00 5400 MM LN +50/-0 MM 6082 / F",
                "CAST/JOB NUMBER : C70025341313/44270958",
            ],
            document_type="certificato",
        )

        self.assertEqual(fields["delivery_note_no"], "28209127")
        self.assertEqual(fields["line_no"], "2.1")
        self.assertEqual(fields["customer_item_number"], "A62087030")
        self.assertEqual(fields["arconic_item_number"], "BG5207530")
        self.assertEqual(fields["cast_number"], "C70025341313")
        self.assertEqual(fields["job_number"], "44270958")
        self.assertEqual(fields["diameter"], "87")
        self.assertEqual(fields["alloy"], "6082 F")


if __name__ == "__main__":
    unittest.main()
