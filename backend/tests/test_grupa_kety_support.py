import unittest

from PIL import Image, ImageChops, ImageDraw

from app.modules.acquisition.rematch_bridge import (
    RematchDecision,
    build_certificate_bridge,
    build_ddt_bridge,
    score_bridge_match,
)
from app.modules.acquisition.service import (
    _build_grupa_kety_masked_page,
    _normalize_grupa_kety_certificate_ai_payload,
    _prefer_grupa_kety_ddt_number,
    _sanitize_grupa_kety_ai_row_groups,
    _supplier_certificate_first_keeps_row_order,
    _supplier_supports_certificate_first,
)
from app.modules.document_reader.registry import resolve_supplier_template


class GrupaKetySupportTest(unittest.TestCase):
    def test_grupa_kety_supplier_aliases_resolve(self):
        for name in ("Grupa Kety S.A.", "Grupa Kety", "Kety"):
            template = resolve_supplier_template(name)
            self.assertIsNotNone(template, name)
            self.assertEqual(template.supplier_key, "grupa_kety")

    def test_grupa_kety_certificate_first_is_enabled_for_second_run_rematch(self):
        self.assertTrue(_supplier_supports_certificate_first("grupa_kety"))
        self.assertTrue(_supplier_certificate_first_keeps_row_order("grupa_kety"))

    def test_grupa_kety_ai_ddt_wins_after_minimal_masking_keeps_labels_visible(self):
        self.assertEqual(_prefer_grupa_kety_ddt_number("12594", "19883"), "19883")
        self.assertEqual(_prefer_grupa_kety_ddt_number(None, "201177772"), "201177772")
        self.assertEqual(_prefer_grupa_kety_ddt_number("12594", None), "12594")

    def test_grupa_kety_ddt_sanitizer_aggregates_12594_rows_by_certificate_and_heat(self):
        candidates = _sanitize_grupa_kety_ai_row_groups(
            ddt_number_raw="Delivery Note 12594",
            raw_rows=[
                {
                    "certificate_number_raw": "10033541/25",
                    "lot_batch_raw": "10033541_22815",
                    "heat_raw": "25E-7871",
                    "alloy_raw": "Alloy:7150",
                    "temper_raw": "F",
                    "diameter_raw": "Extruded Round Bar 44.00",
                    "customer_order_raw": "PO Number 154",
                    "net_weight_raw": "999 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
                {
                    "certificate_number_raw": "10033541/25",
                    "lot_batch_raw": "10033541_22816",
                    "heat_raw": "25E-7871",
                    "alloy_raw": "7150",
                    "temper_raw": "F",
                    "diameter_raw": "44.00",
                    "customer_order_raw": "154",
                    "net_weight_raw": "808 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
                {
                    "certificate_number_raw": "10033539/25",
                    "lot_batch_raw": "10033539_22762",
                    "heat_raw": "25E-7870",
                    "alloy_raw": "7150",
                    "temper_raw": "F",
                    "diameter_raw": "44.00",
                    "customer_order_raw": "154",
                    "net_weight_raw": "594 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
                {
                    "certificate_number_raw": "10033539/25",
                    "lot_batch_raw": "10033539_22763",
                    "heat_raw": "25E-7870",
                    "alloy_raw": "7150",
                    "temper_raw": "F",
                    "diameter_raw": "44.00",
                    "customer_order_raw": "154",
                    "net_weight_raw": "737 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
                {
                    "certificate_number_raw": "10033543/25",
                    "lot_batch_raw": "10033543_22800",
                    "heat_raw": "25E-7872",
                    "alloy_raw": "7150",
                    "temper_raw": "F",
                    "diameter_raw": "44.00",
                    "customer_order_raw": "154",
                    "net_weight_raw": "951 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
                {
                    "certificate_number_raw": "10033543/25",
                    "lot_batch_raw": "10033543_22801",
                    "heat_raw": "25E-7872",
                    "alloy_raw": "7150",
                    "temper_raw": "F",
                    "diameter_raw": "44.00",
                    "customer_order_raw": "154",
                    "net_weight_raw": "951 kg",
                    "source_crops": ["page1_row_groups_page"],
                },
            ],
            ai_document_payload_raw="{}",
        )

        by_cdq = {candidate.cdq: candidate for candidate in candidates}
        self.assertEqual(set(by_cdq), {"10033541/25", "10033539/25", "10033543/25"})
        self.assertEqual(by_cdq["10033541/25"].peso_netto, "1807")
        self.assertEqual(by_cdq["10033539/25"].peso_netto, "1331")
        self.assertEqual(by_cdq["10033543/25"].peso_netto, "1902")
        self.assertEqual(by_cdq["10033539/25"].colata, "25E-7870")
        self.assertEqual(by_cdq["10033539/25"].diametro, "44")
        self.assertEqual(by_cdq["10033539/25"].lega, "7150 F")
        self.assertEqual(by_cdq["10033539/25"].ddt_number, "12594")
        self.assertEqual(by_cdq["10033539/25"].customer_order_no, "154")

    def test_grupa_kety_ddt_sanitizer_derives_certificate_year_from_heat(self):
        candidates = _sanitize_grupa_kety_ai_row_groups(
            ddt_number_raw="12594",
            raw_rows=[
                {
                    "certificate_number_raw": None,
                    "lot_batch_raw": "10033539_22762",
                    "heat_raw": "25E-7870",
                    "net_weight_raw": "594",
                }
            ],
            ai_document_payload_raw=None,
        )

        self.assertEqual(candidates[0].cdq, "10033539/25")

    def test_grupa_kety_certificate_payload_maps_user_match_fields(self):
        payload = _normalize_grupa_kety_certificate_ai_payload(
            {"page1_core_page": {"page_id": 10, "page_number": 1}},
            {
                "core": {
                    "certificate_number": "10033539/25",
                    "packing_slip_raw": "12594 / 10033539",
                    "order_no_raw": "154",
                    "customer_part_raw": "PPO 44MM 7150/F L:5000 US",
                    "alloy_raw": "EN AW-7150",
                    "temper_raw": "F",
                    "heat_raw": "25E-7870",
                    "kg_raw": "1 331,00",
                    "diameter_raw": "44.00 mm",
                },
                "chemistry_raw": {"Si": "0.06", "Cu": "2.16", "Zr": "0.12"},
                "mechanical_raw": {"measured_rows": [{"Rm": "599", "Rp0.2": "565", "A%": "11.4", "HB": "170"}]},
                "notes_raw": {"nota_rohs_raw": "Conformity with directive 2011/65/UE (Rohs II)"},
            },
        )

        core = payload["core_fields"]
        self.assertEqual(core["numero_certificato_certificato"]["value"], "10033539/25")
        self.assertEqual(core["ddt_certificato"]["value"], "12594")
        self.assertEqual(core["ordine_cliente_certificato"]["value"], "154")
        self.assertEqual(core["colata_certificato"]["value"], "25E-7870")
        self.assertEqual(core["lega_certificato"]["value"], "7150 F")
        self.assertEqual(core["diametro_certificato"]["value"], "44")
        self.assertEqual(core["peso_certificato"]["value"], "1331")
        self.assertEqual(payload["supplier_fields"]["lot_number"], "10033539")
        self.assertEqual(payload["supplier_fields"]["heat"], "25E-7870")
        self.assertIn("Cu", payload["chemistry"])
        self.assertIn("Rm", payload["properties"])

    def test_grupa_kety_bridge_matches_on_excel_user_fields(self):
        ddt = build_ddt_bridge(
            row_values={
                "fornitore": "Grupa Kety",
                "lega_base": "7150 F",
                "diametro": "44",
                "cdq": "10033539/25",
                "colata": "25E-7870",
                "ddt": "12594",
                "peso": "1331",
                "ordine": "154",
            },
            supplier_name="Grupa Kety",
        )
        cert = build_certificate_bridge(
            row_values={
                "fornitore": "Grupa Kety",
                "cdq": "10033539/25",
            },
            read_values={
                "numero_certificato_certificato": "10033539/25",
                "colata_certificato": "25E-7870",
                "ddt_certificato": "12594",
                "peso_certificato": "1331",
                "ordine_cliente_certificato": "154",
                "lega_certificato": "7150 F",
                "diametro_certificato": "44",
            },
            supplier_name="Grupa Kety",
        )

        result = score_bridge_match(ddt, cert)

        self.assertEqual(result.decision, RematchDecision.STRONG, result)
        self.assertIn("cdq", result.matched_fields)
        self.assertIn("colata", result.matched_fields)

    def test_grupa_kety_masking_keeps_material_tables(self):
        image = Image.new("RGB", (1000, 1400), "white")
        draw = ImageDraw.Draw(image)
        draw.text((90, 120), "FORGIALLUMINIO Via Enrico Fermi 2", fill="black")
        draw.text((90, 220), "Delivery Note: 12594", fill="black")
        draw.text((90, 260), "Shipment ID: 19883", fill="black")
        draw.text((90, 600), "Alloy grade EN AW-7150 Heat H6245 kg", fill="black")
        before = image.copy()

        masked = _build_grupa_kety_masked_page(image)

        diff = ImageChops.difference(before, masked).convert("L")
        self.assertIsNotNone(diff.crop((70, 95, 460, 160)).getbbox())
        self.assertIsNone(diff.crop((70, 195, 360, 290)).getbbox())
        self.assertIsNone(diff.crop((70, 570, 520, 640)).getbbox())


if __name__ == "__main__":
    unittest.main()
