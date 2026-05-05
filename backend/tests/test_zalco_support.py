import unittest

from PIL import Image, ImageChops, ImageDraw

from app.modules.acquisition.rematch_bridge import (
    RematchDecision,
    build_certificate_bridge,
    build_ddt_bridge,
    score_bridge_match,
)
from app.modules.acquisition.service import (
    _build_zalco_masked_page,
    _normalize_zalco_certificate_ai_payload,
    _sanitize_zalco_ai_row_groups,
    _supplier_certificate_first_keeps_row_order,
    _supplier_supports_certificate_first,
)
from app.modules.document_reader.registry import resolve_supplier_template


class ZalcoSupportTest(unittest.TestCase):
    def test_zalco_supplier_aliases_resolve(self):
        for name in ("Zalco", "Zeeland Aluminium Company", "Zeeland Aluminium Company BV"):
            template = resolve_supplier_template(name)
            self.assertIsNotNone(template, name)
            self.assertEqual(template.supplier_key, "zalco")

    def test_zalco_certificate_first_is_enabled_for_second_run_rematch(self):
        self.assertTrue(_supplier_supports_certificate_first("zalco"))
        self.assertTrue(_supplier_certificate_first_keeps_row_order("zalco"))

    def test_zalco_ddt_sanitizer_reads_packing_list_with_analysis(self):
        candidates = _sanitize_zalco_ai_row_groups(
            ddt_number_raw="000020285",
            raw_rows=[
                {
                    "tally_sheet_raw": "No. AVIS / TALLY SHEET 000020285",
                    "order_raw": "ORDER FORGIALLUMINIO 20230145",
                    "symbol_raw": "CUSTOMER ALLOY CODE 6082 HO 608213",
                    "code_art_raw": "CODE ART: 0381Z",
                    "diameter_raw": "FORMAT: 203",
                    "weight_raw": "POIDS NET: 17975",
                    "cast_raw": "2023 42669",
                    "alloy_raw": "6082 HO",
                    "source_crops": ["page1_row_groups_page"],
                }
            ],
            ai_document_payload_raw="{}",
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.ddt_number, "20285")
        self.assertEqual(candidate.cdq, "20285")
        self.assertEqual(candidate.customer_order_no, "20230145")
        self.assertEqual(candidate.customer_code, "608213")
        self.assertEqual(candidate.article_code, "0381Z")
        self.assertEqual(candidate.product_code, "0381Z")
        self.assertEqual(candidate.diametro, "203")
        self.assertEqual(candidate.peso_netto, "17975")
        self.assertEqual(candidate.colata, "2023-42669")
        self.assertEqual(candidate.lega, "6082 HO")

    def test_zalco_ddt_sanitizer_allows_weak_tally_sheet_without_cast(self):
        candidates = _sanitize_zalco_ai_row_groups(
            ddt_number_raw=None,
            raw_rows=[
                {
                    "tally_sheet_raw": "No. AVIS / TALLY SHEET Nr. 20067",
                    "order_raw": "20230032",
                    "symbol_raw": "SYMBOLE 60821",
                    "code_art_raw": "CODE 0283Z",
                    "diameter_raw": "DIAMETER OR SIZES 254",
                    "weight_raw": "NET 80",
                    "cast_raw": None,
                }
            ],
            ai_document_payload_raw=None,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].ddt_number, "20067")
        self.assertEqual(candidates[0].colata, None)
        self.assertEqual(candidates[0].diametro, "254")
        self.assertEqual(candidates[0].peso_netto, "80")

    def test_zalco_certificate_payload_maps_origin_certificate_fields(self):
        payload = _normalize_zalco_certificate_ai_payload(
            {"page1_core_page": {"page_id": 10, "page_number": 1}},
            {
                "core": {
                    "tally_sheet_raw": "No. AVIS / TALLY SHEET Nr. 20285",
                    "order_raw": "No. ORDRE / ORDER Nr. 20230145",
                    "symbol_raw": "SYMBOLE 608213",
                    "code_art_raw": "CODE 0381Z",
                    "diameter_raw": "LONGEUR 5500 DIAMETER OR SIZES 203",
                    "weight_raw": "NET 17975",
                    "cast_raw": "2023 42669",
                    "alloy_raw": "6082 HO",
                },
                "chemistry_raw": {"Si": "1,3", "Fe": "0,46", "Cu": "0,06", "Mn": "0,5", "Mg": "0,8", "Cr": "0,06", "Zn": "0,04", "Ti": "0,02"},
                "notes_raw": {"nota_us_control_classe_raw": None},
            },
        )

        core = payload["core_fields"]
        self.assertEqual(core["numero_certificato_certificato"]["value"], "20285")
        self.assertEqual(core["ddt_certificato"]["value"], "20285")
        self.assertEqual(core["ordine_cliente_certificato"]["value"], "20230145")
        self.assertEqual(core["colata_certificato"]["value"], "2023-42669")
        self.assertEqual(core["lega_certificato"]["value"], "6082 HO")
        self.assertEqual(core["diametro_certificato"]["value"], "203")
        self.assertEqual(core["peso_certificato"]["value"], "17975")
        self.assertEqual(core["articolo_certificato"]["value"], "0381Z")
        self.assertEqual(core["codice_cliente_certificato"]["value"], "608213")
        self.assertEqual(payload["supplier_fields"]["tally_sheet_no"], "20285")
        self.assertIn("Si", payload["chemistry"])

    def test_zalco_bridge_matches_origin_tally_and_cast(self):
        ddt = build_ddt_bridge(
            row_values={
                "fornitore": "Zeeland Aluminium Company",
                "lega_base": "6082 HO",
                "diametro": "203",
                "cdq": "20285",
                "colata": "2023-42669",
                "ddt": "20285",
                "peso": "17975",
                "ordine": "20230145",
            },
            supplier_name="Zeeland Aluminium Company",
        )
        cert = build_certificate_bridge(
            row_values={"fornitore": "Zeeland Aluminium Company", "cdq": "20285"},
            read_values={
                "numero_certificato_certificato": "20285",
                "colata_certificato": "2023-42669",
                "ddt_certificato": "20285",
                "peso_certificato": "17975",
                "ordine_cliente_certificato": "20230145",
                "lega_certificato": "6082 HO",
                "diametro_certificato": "203",
            },
            supplier_name="Zeeland Aluminium Company",
        )

        result = score_bridge_match(ddt, cert)

        self.assertEqual(result.decision, RematchDecision.STRONG, result)
        self.assertIn("cdq", result.matched_fields)
        self.assertIn("colata", result.matched_fields)

    def test_zalco_masking_keeps_analysis_table(self):
        image = Image.new("RGB", (1000, 1400), "white")
        draw = ImageDraw.Draw(image)
        draw.text((760, 80), "ZALCO Zeeland Aluminium Company", fill="black")
        draw.text((120, 780), "COULEE 2023 42669 NET 17975 SI 1,3 FE 0,46", fill="black")
        before = image.copy()

        masked = _build_zalco_masked_page(image)

        diff = ImageChops.difference(before, masked).convert("L")
        self.assertIsNotNone(diff.crop((700, 45, 970, 180)).getbbox())
        self.assertIsNone(diff.crop((100, 740, 800, 830)).getbbox())


if __name__ == "__main__":
    unittest.main()
