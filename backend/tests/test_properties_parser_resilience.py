import unittest

from app.modules.acquisition.service import _parse_generic_properties_table_capture


class PropertiesParserResilienceTest(unittest.TestCase):
    def test_generic_properties_table_keeps_lowest_measured_values(self):
        lines = [
            "Mechanical Property - Test Limits",
            "Test Rm L Rp0,2 L A5 L HB",
            "Min 380 340 10 100",
            "T001 T76 581 539 12.3 164",
            "T002 T76 596 525 11.4 170",
        ]

        choice = _parse_generic_properties_table_capture(lines, page_id=1)

        self.assertEqual(choice.matches["Rm"]["final"], "581")
        self.assertEqual(choice.matches["Rp0.2"]["final"], "525")
        self.assertEqual(choice.matches["A%"]["final"], "11,4")
        self.assertEqual(choice.matches["HB"]["final"], "164")

    def test_generic_properties_table_ignores_chemical_numeric_rows(self):
        lines = [
            "Chemical composition",
            "Si Fe Cu Mn Mg",
            "0.88 0.16 0.46 0.48 0.79",
            "Mechanical properties",
            "sample Rm Rp0.2 A% HB",
            "1 390 350 13.5 107",
        ]

        choice = _parse_generic_properties_table_capture(lines, page_id=1)

        self.assertEqual(choice.matches["Rm"]["final"], "390")
        self.assertEqual(choice.matches["Rp0.2"]["final"], "350")
        self.assertEqual(choice.matches["A%"]["final"], "13,5")
        self.assertEqual(choice.matches["HB"]["final"], "107")


if __name__ == "__main__":
    unittest.main()
