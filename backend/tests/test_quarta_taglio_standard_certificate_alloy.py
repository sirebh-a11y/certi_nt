import unittest

from app.modules.quarta_taglio.service import _standard_alloy_label, _standard_certificate_material_label
from app.modules.standards.models import NormativeStandard


class QuartaTaglioStandardCertificateAlloyTests(unittest.TestCase):
    def test_variant_stays_in_standard_label_but_not_in_certificate_label(self) -> None:
        cases = (
            ("2024", "Sigma", "EN AW 2024"),
            ("7075", "Eppendorf", "EN AW 7075"),
            ("2618A", "Adixen", "EN AW 2618A"),
            ("6182", "LST07", "EN AW 6182"),
        )

        for base_alloy, variant, expected_certificate_label in cases:
            with self.subTest(base_alloy=base_alloy, variant=variant):
                standard = NormativeStandard(
                    code=f"{base_alloy}-{variant}",
                    lega_base=base_alloy,
                    lega_designazione=f"{base_alloy} {variant}",
                    variante_lega=variant,
                )

                self.assertIn(variant, _standard_alloy_label(standard))
                self.assertEqual(_standard_certificate_material_label(standard), expected_certificate_label)
                self.assertNotIn(variant, _standard_certificate_material_label(standard))

    def test_certificate_label_preserves_real_base_alloy_suffixes(self) -> None:
        for base_alloy in ("2017A", "6110A", "6082H"):
            with self.subTest(base_alloy=base_alloy):
                standard = NormativeStandard(
                    code=base_alloy,
                    lega_base=base_alloy,
                    lega_designazione=base_alloy,
                    variante_lega=None,
                )

                self.assertEqual(_standard_certificate_material_label(standard), f"EN AW {base_alloy}")

    def test_certificate_label_does_not_duplicate_existing_en_aw_prefix(self) -> None:
        standard = NormativeStandard(
            code="2024",
            lega_base="EN AW 2024",
            lega_designazione="EN AW 2024 Sigma",
            variante_lega="Sigma",
        )

        self.assertEqual(_standard_certificate_material_label(standard), "EN AW 2024")


if __name__ == "__main__":
    unittest.main()
