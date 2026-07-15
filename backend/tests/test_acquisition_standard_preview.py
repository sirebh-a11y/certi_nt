import unittest

from app.modules.acquisition.service import _standard_preview_normalize_alloy


class AcquisitionStandardPreviewTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
