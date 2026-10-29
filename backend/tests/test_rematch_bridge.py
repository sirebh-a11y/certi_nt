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

    def test_supplier_contradictions_cannot_be_hidden_by_a_matching_certificate_number(self):
        for supplier, fields in {
            'Metalba': ('lega', 'peso', 'ordine'),
            'Impol': ('lega', 'peso', 'ordine'),
            'Leichtmetall': ('lega',),
            'Neuman': ('lega', 'peso', 'article_code'),
            'AWW': ('lega', 'peso', 'ordine', 'article_code', 'profile_code', 'order_confirmation_root'),
            'Arconic': ('ordine', 'ddt'),
            'Grupa Kety': ('lega',),
        }.items():
            base={'fornitore':supplier,'cdq':'C1','colata':'CAST1','diametro':'33',
                  'lega_base':'6082 F','peso':'2827','ordine':'O1','ddt':'D1'}
            for field in fields:
                with self.subTest(supplier=supplier,field=field):
                    left_read={field:'AAA' if field not in {'peso','lega','order_confirmation_root'} else
                               {'peso':'2827','lega':'6082 F','order_confirmation_root':'123456/1'}[field]}
                    right_read={field:'BBB' if field not in {'peso','lega','order_confirmation_root'} else
                                {'peso':'9999','lega':'7075 T6','order_confirmation_root':'654321/1'}[field]}
                    # Test the actual field aliases, not synthetic bridge keys.
                    aliases={'lega':'lega_certificato','peso':'peso_certificato',
                             'ordine':'ordine_cliente_certificato','ddt':'ddt_certificato',
                             'article_code':'articolo_certificato','profile_code':'profile_code_certificato',
                             'order_confirmation_root':'supplier_order_no_certificato'}
                    right_read={aliases[field]:right_read[field]}
                    result=self.assert_no_match(ddt(base,left_read,supplier_name=supplier),
                                                cert(base,right_read,supplier_name=supplier))
                    self.assertIn(f'{field} diverso',result.blockers)

    def test_new_contradiction_guards_keep_supplier_weight_tolerances_and_missing_fields(self):
        for supplier,left_weight,right_weight in [('Metalba','2827','2830'),('Impol','1603','1610'),
                                                  ('AWW','1540','1540.9'),('Neuman','8420','8421')]:
            with self.subTest(supplier=supplier):
                base={'fornitore':supplier,'cdq':'C1','colata':'CAST1','diametro':'33',
                      'lega_base':'6082 F','ordine':'O1'}
                self.assert_strong(ddt({**base,'peso':left_weight},supplier_name=supplier),
                                   cert({**base,'peso':right_weight},supplier_name=supplier))
                self.assert_strong(ddt(base,supplier_name=supplier),cert(base,supplier_name=supplier))

    def test_aww_order_confirmation_uses_existing_root_parser(self):
        base={'fornitore':'AWW','cdq':'C1','colata':'CAST1','diametro':'33','lega_base':'6082A T1'}
        self.assert_strong(ddt(base,{'order_confirmation_root':'70123456/3'},supplier_name='AWW'),
            cert(base,{'supplier_order_no_certificato':'70123456'},supplier_name='AWW'))

    def test_configured_supplier_key_and_metalba_vs_rif_are_not_lost(self):
        left=build_ddt_bridge(row_values={'cdq':'C1','colata':'CAST1','diametro':'33','peso':'120','ordine':'OLD'},
            read_values={'vs_rif':'REAL'},supplier_id=1,supplier_name='Custom supplier',supplier_key='metalba')
        right=build_certificate_bridge(row_values={'cdq':'C1','colata':'CAST1','diametro':'33','peso':'120'},
            read_values={'ordine_cliente_certificato':'OTHER'},supplier_id=1,
            supplier_name='Custom supplier',supplier_key='metalba')
        self.assertEqual(left.value('ordine'),'REAL')
        self.assertIn('ordine diverso',self.assert_no_match(left,right).blockers)

    def test_metalba_legacy_order_root_is_incomplete_not_a_different_order(self):
        base={'fornitore':'Metalba','cdq':'C1','colata':'CAST1','diametro':'33',
              'lega_base':'6082 F','peso':'2827'}
        left=ddt({**base,'ordine':'169/26'},supplier_name='Metalba')
        result=self.assert_strong(left,cert({**base,'ordine':'169'},supplier_name='Metalba'))
        self.assertNotIn('ordine',result.matched_fields)
        for wrong in ('170','169/25','169/2025','OTHER'):
            with self.subTest(wrong=wrong):
                self.assertIn('ordine diverso',self.assert_no_match(left,
                    cert({**base,'ordine':wrong},supplier_name='Metalba')).blockers)

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

    def test_leichtmetall_duplicate_cdq_matches_right_delivery_row(self):
        ddt_80008254 = ddt(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228.00",
                "colata": "94668",
                "ddt": "80008254",
                "peso": "8554",
                "ordine": "333.1",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        cert_94668_8554 = cert(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228",
                "colata": "94668",
                "peso": "8554",
                "ordine": "333.1",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        ddt_80008535_94668 = ddt(
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
        cert_94668_5014 = cert(
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
        ddt_80008535_94752 = ddt(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94752",
                "lega_base": "6082",
                "diametro": "228.00",
                "colata": "94752",
                "ddt": "80008535",
                "peso": "12211",
                "ordine": "19.2 + 4 + 5",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        cert_94752_12211 = cert(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94752",
                "lega_base": "6082",
                "diametro": "228",
                "colata": "94752",
                "peso": "12211",
                "ordine": "19.2 + 4 + 5",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )

        self.assert_strong(ddt_80008254, cert_94668_8554)
        self.assert_strong(ddt_80008535_94668, cert_94668_5014)
        self.assert_strong(ddt_80008535_94752, cert_94752_12211)

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

    def test_leichtmetall_duplicate_cdq_wrong_weight_and_order_blocks(self):
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
                "peso": "8554",
                "ordine": "333.1",
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        result = self.assert_no_match(left, right)
        self.assertIn("peso diverso", result.blockers)
        self.assertIn("ordine diverso", result.blockers)
        self.assertNotIn("peso", result.matched_fields)

    def test_leichtmetall_cdq_and_diameter_without_row_discriminator_are_not_enough(self):
        left = ddt(
            {
                "fornitore": "Leichtmetall Aluminium Giesserei Hannover GmbH",
                "cdq": "94668",
                "lega_base": "6082",
                "diametro": "228.00",
                "colata": "94668",
                "ddt": "80008535",
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
            },
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )
        result = self.assert_no_match(left, right)
        self.assertIn("cdq", result.matched_fields)
        self.assertIn("colata", result.matched_fields)
        self.assertIn("diametro", result.matched_fields)

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
