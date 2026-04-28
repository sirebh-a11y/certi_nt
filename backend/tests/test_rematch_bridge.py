import unittest

from app.modules.acquisition.rematch_bridge import (
    RematchDecision,
    build_certificate_bridge,
    build_ddt_bridge,
    score_bridge_match,
)


def ddt(row, read=None, supplier_id=1, supplier_name="Supplier"):
    return build_ddt_bridge(
        row_values=row,
        read_values=read or {},
        supplier_id=supplier_id,
        supplier_name=supplier_name,
    )


def cert(row, read=None, supplier_id=1, supplier_name="Supplier"):
    return build_certificate_bridge(
        row_values=row,
        read_values=read or {},
        supplier_id=supplier_id,
        supplier_name=supplier_name,
    )


class RematchBridgeTest(unittest.TestCase):
    def assert_strong(self, left, right):
        result = score_bridge_match(left, right)
        self.assertEqual(result.decision, RematchDecision.STRONG, result)
        self.assertFalse(result.blockers, result)
        return result

    def assert_no_match(self, left, right):
        result = score_bridge_match(left, right)
        self.assertEqual(result.decision, RematchDecision.NONE, result)
        return result

    def test_aluminium_bozen_existing_match(self):
        left = ddt(
            {
                "fornitore": "Aluminium Bozen S.r.l.",
                "cdq": "151238",
                "lega_base": "6082 F",
                "diametro": "98",
                "colata": "525301A1",
                "ddt": "176",
                "peso": "5920",
                "ordine": "1-2026-01-07",
            },
            supplier_name="Aluminium Bozen S.r.l.",
        )
        right = cert(
            {
                "fornitore": "Aluminium Bozen S.r.l.",
                "cdq": "151238",
                "lega_base": "6082 F",
                "diametro": "98",
                "colata": "525301A1",
                "peso": "5920",
                "ordine": "1-2026-01-07",
            },
            supplier_name="Aluminium Bozen S.r.l.",
        )
        result = self.assert_strong(left, right)
        self.assertIn("cdq", result.matched_fields)
        self.assertIn("colata", result.matched_fields)

    def test_aww_existing_match_with_row_fallback(self):
        left = ddt(
            {
                "fornitore": "Aluminium-Werke Wutoschingen AG & Co. KG",
                "cdq": "Z24-90172",
                "lega_base": "6082A T1",
                "diametro": "43",
                "colata": "404745",
                "ddt": "14128157",
                "peso": "1540",
                "ordine": "223",
            },
            read={"diametro": "43", "peso": "1540", "ordine": "223"},
            supplier_name="Aluminium-Werke Wutoschingen AG & Co. KG",
        )
        right = cert(
            {
                "fornitore": "Aluminium-Werke Wutoschingen AG & Co. KG",
                "cdq": "Z24-90172",
                "lega_base": "6082A T1",
                "diametro": "43",
                "colata": "404745",
                "ordine": "223",
            },
            read={
                "numero_certificato_certificato": "Z24-90172",
                "lega_certificato": "6082A T1",
                "diametro_certificato": "43",
                "colata_certificato": "404745",
                "ordine_cliente_certificato": "223",
            },
            supplier_name="Aluminium-Werke Wutoschingen AG & Co. KG",
        )
        self.assert_strong(left, right)

    def test_impol_existing_match_normalizes_alloy_and_weight(self):
        left = ddt(
            {
                "fornitore": "Impol d.o.o.",
                "cdq": "1505/A",
                "lega_base": "6082 F",
                "diametro": "32",
                "colata": "398850",
                "ddt": "1505-11",
                "peso": "1.603",
                "ordine": "352",
            },
            supplier_name="Impol d.o.o.",
        )
        right = cert(
            {
                "fornitore": "Impol d.o.o.",
                "cdq": "1505/a",
                "lega_base": "EN AW 6082 F",
                "diametro": "DIA 32 x 5000mm",
                "colata": "398850(44419/25)",
                "peso": "1603 kg",
                "ordine": "352",
            },
            supplier_name="Impol d.o.o.",
        )
        self.assert_strong(left, right)

    def test_leichtmetall_existing_match_normalizes_decimal_diameter(self):
        left = ddt(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228.00",
                "colata": "94668",
                "ddt": "80008535",
                "peso": "5014",
                "ordine": "19.2 + 4 + 5",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        right = cert(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228",
                "colata": "94668",
                "peso": "5014",
                "ordine": "19.2 + 4 + 5",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        self.assert_strong(left, right)

    def test_leichtmetall_already_coupled_certificate_can_be_reused_from_match_values(self):
        left = ddt(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228.00",
                "colata": "94668",
                "ddt": "80008535",
                "peso": "5014",
                "ordine": "19",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        right = cert(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
            },
            read={
                "numero_certificato_certificato": "94668",
                "lega_certificato": "6082",
                "diametro_certificato": "228",
                "colata_certificato": "94668",
                "peso_certificato": "5014",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        result = self.assert_strong(left, right)
        self.assertIn("diametro", result.matched_fields)
        self.assertIn("peso", result.matched_fields)

    def test_metalba_existing_match_with_ddt_readvalue_gaps(self):
        left = ddt(
            {
                "fornitore": "Metalba S.p.A.",
                "cdq": "26-0743",
                "lega_base": "6082F F",
                "diametro": "38",
                "colata": "25338C",
                "ddt": "26-00957",
                "peso": "2233",
                "ordine": "27/26",
            },
            read={"diametro": "38", "peso": "2233", "ordine": "27/26"},
            supplier_name="Metalba S.p.A.",
        )
        right = cert(
            {
                "fornitore": "Metalba S.p.A.",
                "cdq": "26-0743",
                "lega_base": "6082F F",
                "diametro": "38",
                "colata": "25338C",
                "peso": "2233",
                "ordine": "27/26",
            },
            supplier_name="Metalba S.p.A.",
        )
        self.assert_strong(left, right)

    def test_neuman_existing_match_tolerates_small_weight_difference_and_missing_order(self):
        left = ddt(
            {
                "fornitore": "Neuman Aluminium Austria GmbH",
                "cdq": "25537",
                "lega_base": "6082",
                "diametro": "190",
                "colata": "25537",
                "ddt": "75716074",
                "peso": "8420",
                "ordine": "2",
            },
            supplier_name="Neuman Aluminium Austria GmbH",
        )
        right = cert(
            {
                "fornitore": "Neuman Aluminium Austria GmbH",
                "cdq": "25537",
                "lega_base": "6082",
                "diametro": "190",
                "colata": "25537",
                "peso": "8421",
                "ordine": None,
            },
            supplier_name="Neuman Aluminium Austria GmbH",
        )
        self.assert_strong(left, right)

    def test_only_alloy_is_never_enough(self):
        left = ddt(
            {
                "fornitore": "Impol d.o.o.",
                "lega_base": "6005A F",
                "diametro": "35",
                "colata": "400178",
                "peso": "2424",
                "ordine": "389",
            },
            supplier_name="Impol d.o.o.",
        )
        right = cert(
            {
                "fornitore": "Impol d.o.o.",
                "cdq": "17126/A",
                "lega_base": "6005A F",
                "diametro": "40",
                "colata": "383163",
                "peso": "1370",
                "ordine": "143",
            },
            supplier_name="Impol d.o.o.",
        )
        result = self.assert_no_match(left, right)
        self.assertIn("colata diverso", result.blockers)

    def test_supplier_mismatch_blocks_match(self):
        left = ddt(
            {"fornitore": "Impol d.o.o.", "cdq": "1505/A", "diametro": "32", "colata": "398850", "peso": "1603"},
            supplier_id=5,
            supplier_name="Impol d.o.o.",
        )
        right = cert(
            {"fornitore": "Metalba S.p.A.", "cdq": "1505/A", "diametro": "32", "colata": "398850", "peso": "1603"},
            supplier_id=6,
            supplier_name="Metalba S.p.A.",
        )
        result = self.assert_no_match(left, right)
        self.assertIn("fornitore diverso", result.blockers)

    def test_same_certificate_can_score_against_multiple_rows(self):
        certificate = cert(
            {
                "fornitore": "Future Supplier",
                "lega_base": "6082 F",
                "diametro": "50",
                "colata": "ABC123",
                "peso": "1000",
                "ordine": "PO-1",
            },
            supplier_name="Future Supplier",
        )
        first_row = ddt(
            {
                "fornitore": "Future Supplier",
                "lega_base": "6082 F",
                "diametro": "50.00",
                "colata": "ABC123",
                "peso": "1.000",
                "ordine": "PO-1",
            },
            supplier_name="Future Supplier",
        )
        second_row = ddt(
            {
                "fornitore": "Future Supplier",
                "lega_base": "6082 F",
                "diametro": "50",
                "colata": "ABC123",
                "peso": "1000",
                "ordine": "PO-1",
            },
            supplier_name="Future Supplier",
        )
        self.assertEqual(score_bridge_match(first_row, certificate).decision, RematchDecision.STRONG)
        self.assertEqual(score_bridge_match(second_row, certificate).decision, RematchDecision.STRONG)


if __name__ == "__main__":
    unittest.main()
