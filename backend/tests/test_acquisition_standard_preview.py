import unittest
from types import SimpleNamespace

from app.modules.acquisition.incoming_chemistry import (
    find_incoming_chemistry_profile,
    incoming_chemistry_profiles,
    incoming_chemistry_value_is_inside,
)
from app.modules.acquisition.schemas import AcquisitionStandardPreviewRequest
from app.modules.acquisition.service import (
    _standard_preview_normalize_alloy,
    preview_acquisition_row_standard_conformity,
)


class AcquisitionStandardPreviewTest(unittest.TestCase):
    @staticmethod
    def _row(*, alloy: str, variant: str | None = None):
        return SimpleNamespace(
            lega_base=alloy,
            lega_designazione=None,
            variante_lega=variant,
            values=[],
            evidences=[],
            ddt_document=None,
            certificate_document=None,
        )

    def test_normalize_alloy_preserves_6082_variants_without_confusing_base(self):
        cases = {
            "6082": "6082",
            "6082 F": "6082",
            "6082F F": "6082",
            "EN AW 6082 T6": "6082",
            "EN AW 6082 T62": "6082",
            "6082L": "6082L",
            "6082 L": "6082L",
            "6082 LF": "6082L",
            "6082L F": "6082L",
            "6082 LUNGHEZZA 5900": "6082",
            "6082 L=5900": "6082",
            "6082 F BARRA TONDA DIAM 48 mm VOSTRO CODICE A62048010 IN LUNGHEZZA DI 5.900 mm": "6082",
            "6082H": "6082H",
            "6082 H": "6082H",
            "6082 HF": "6082H",
            "6082H F": "6082H",
            "6110A F": "6110A",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_standard_preview_normalize_alloy(raw), expected)

    def test_incoming_profiles_cover_the_customer_table(self):
        profiles = incoming_chemistry_profiles()

        self.assertEqual(len(profiles), 20)
        self.assertEqual(len({profile.code for profile in profiles}), 20)
        self.assertTrue(all(profile.limits for profile in profiles))

    def test_incoming_profile_selection_preserves_special_variants(self):
        cases = (
            (("2024 F", None, "Sigma"), "2024_LST05"),
            (("2618A", None, "Adixen"), "2618A_ADIXEN"),
            (("6082H F", None, None), "6082H_LST03A"),
            (("6082", "LST03-A", None), "6082H_LST03A"),
            (("6082 LF", None, None), "6082L"),
            (("6182", None, "LST07"), "6182_LST07"),
            (("7075 T6", None, None), "7075"),
        )

        for (alloy, designation, variant), expected in cases:
            with self.subTest(alloy=alloy, designation=designation, variant=variant):
                profile = find_incoming_chemistry_profile(
                    lega_base=alloy,
                    lega_designazione=designation,
                    variante_lega=variant,
                )
                self.assertIsNotNone(profile)
                self.assertEqual(profile.code, expected)

    def test_incoming_chemistry_checks_only_values_that_are_present(self):
        preview = preview_acquisition_row_standard_conformity(
            None,
            row=self._row(alloy="6082 F"),
            payload=AcquisitionStandardPreviewRequest(
                block="chimica",
                fields={"Si": "0,95", "Mg": "0,80"},
            ),
        )

        self.assertEqual(preview.status, "conforme")
        self.assertEqual(preview.standard_label, "EN AW 6082")
        self.assertEqual(preview.issues, [])

    def test_incoming_chemistry_reports_an_actual_out_of_range_value(self):
        preview = preview_acquisition_row_standard_conformity(
            None,
            row=self._row(alloy="6082"),
            payload=AcquisitionStandardPreviewRequest(
                block="chimica",
                fields={"Si": "1,40", "Mg": "0,80"},
            ),
        )

        self.assertEqual(preview.status, "non_conforme")
        self.assertEqual([issue.field for issue in preview.issues], ["Si"])
        self.assertIn("fuori limite", preview.issues[0].message)

    def test_incoming_chemistry_uses_the_variant_limits(self):
        preview = preview_acquisition_row_standard_conformity(
            None,
            row=self._row(alloy="6082L"),
            payload=AcquisitionStandardPreviewRequest(
                block="chimica",
                fields={"Cu": "0,08"},
            ),
        )

        self.assertEqual(preview.standard_label, "6082L")
        self.assertEqual(preview.status, "non_conforme")
        self.assertEqual(preview.issues[0].limit, "<= 0.05")

    def test_adixen_explicit_less_than_limit_is_not_treated_as_inclusive(self):
        profile = find_incoming_chemistry_profile(
            lega_base="2618A",
            lega_designazione=None,
            variante_lega="Adixen",
        )
        self.assertIsNotNone(profile)
        bi_limit = next(limit for limit in profile.limits if limit.element == "Bi")

        self.assertTrue(incoming_chemistry_value_is_inside(0.004, bi_limit))
        self.assertFalse(incoming_chemistry_value_is_inside(0.005, bi_limit))


if __name__ == "__main__":
    unittest.main()
