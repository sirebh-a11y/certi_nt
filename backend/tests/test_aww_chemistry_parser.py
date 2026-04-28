import unittest

from app.modules.acquisition.service import _parse_aww_chemistry_from_lines


class AwwChemistryParserTest(unittest.TestCase):
    def assert_aww_6082_values(self, matches):
        self.assertEqual(matches["Si"]["final"], "1.2")
        self.assertEqual(matches["Fe"]["final"], "0.30")
        self.assertEqual(matches["Cu"]["final"], "0.05")
        self.assertEqual(matches["Mn"]["final"], "0.58")
        self.assertEqual(matches["Mg"]["final"], "0.8")
        self.assertEqual(matches["Cr"]["final"], "0.18")
        self.assertEqual(matches["Zn"]["final"], "0.02")
        self.assertEqual(matches["Ti"]["final"], "0.03")
        self.assertEqual(matches["Pb"]["final"], "0.00")

    def test_reversed_pdf_text_row_is_mapped_to_header_order(self):
        lines = [
            "CHEMISCHE ZUSAMMENSETZUNG CHEMICAL COMPOSITION",
            "Charge Nr. Si Fe Cu Mn Mg Cr Zn Ti Pb",
            "305431 0,00 0,03 0,02 0,18 0,8 0,58 0,05 0,30 1,2",
            "Soll min. 0,7 - - 0,40 0,6 - - - -",
            "Set value max. 1,3 0,50 0,10 1,00 1,2 0,25 0,20 0,10 0,05",
            "MECHANISCHE EIGENSCHAFTEN",
        ]

        matches = _parse_aww_chemistry_from_lines(lines, page_id=1)

        self.assert_aww_6082_values(matches)

    def test_stacked_pdf_text_uses_visible_header_order(self):
        lines = [
            "CHEMISCHE ZUSAMMENSETZUNG",
            "CHEMICAL COMPOSITION / COMPOSITION CHIMIQUE",
            "Pb",
            "Ti",
            "Zn",
            "Cr",
            "Mg",
            "Mn",
            "Cu",
            "Fe",
            "Si",
            "Charge Nr.",
            "%",
            "%",
            "%",
            "%",
            "%",
            "%",
            "%",
            "%",
            "%",
            "Charge No.",
            "Coulée No.",
            "0,00",
            "0,03",
            "0,02",
            "0,18",
            "0,8",
            "0,58",
            "0,05",
            "0,30",
            "1,2",
            "305431",
            "min.",
            "Soll",
            "0,6",
            "0,7",
            "0,40",
            "Set value",
            "max",
            "1,00",
            "0,50",
            "0,10",
            "1,2",
            "0,25",
            "0,20",
            "0,10",
            "0,05",
            "1,3",
            "Valeur",
            "MECHANISCHE EIGENSCHAFTEN",
        ]

        matches = _parse_aww_chemistry_from_lines(lines, page_id=1)

        self.assert_aww_6082_values(matches)


if __name__ == "__main__":
    unittest.main()
