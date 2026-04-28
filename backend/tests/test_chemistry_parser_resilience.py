import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import (
    _detect_chemistry_matches,
    _parse_aww_chemistry_from_lines,
    _parse_chemistry_from_lines,
    _parse_metalba_chemistry_from_lines,
    _parse_neuman_chemistry_from_lines,
)


class ChemistryParserResilienceTest(unittest.TestCase):
    def test_generic_parser_keeps_unknown_middle_column_aligned(self):
        lines = [
            "Si Fe Cu Mn Mg Ga V Ti Pb Sn",
            "LOT123 0,10 0,20 0,30 0,40 0,50 0,99 0,60 0,70 0,80 0,90",
        ]

        matches = _parse_chemistry_from_lines(lines, page_id=1)

        self.assertEqual(matches["Si"]["final"], "0.10")
        self.assertEqual(matches["Mg"]["final"], "0.50")
        self.assertEqual(matches["V"]["final"], "0.60")
        self.assertEqual(matches["Sn"]["final"], "0.90")
        self.assertNotIn("Ga", matches)

    def test_aww_parser_keeps_unknown_middle_column_aligned(self):
        lines = [
            "CHEMISCHE ZUSAMMENSETZUNG",
            "Charge Nr. Si Fe Cu Mn Mg Ga Cr Zn Ti Pb",
            "305431 1,20 0,30 0,05 0,58 0,80 0,99 0,18 0,02 0,03 0,00",
            "Soll min. 0,70 - - 0,40 0,60 0,00 - - - -",
            "Set value max. 1,30 0,50 0,10 1,00 1,20 1,00 0,25 0,20 0,10 0,05",
            "MECHANISCHE EIGENSCHAFTEN",
        ]

        matches = _parse_aww_chemistry_from_lines(lines, page_id=1)

        self.assertEqual(matches["Si"]["final"], "1.20")
        self.assertEqual(matches["Mg"]["final"], "0.80")
        self.assertEqual(matches["Cr"]["final"], "0.18")
        self.assertEqual(matches["Pb"]["final"], "0.00")
        self.assertNotIn("Ga", matches)

    def test_neuman_parser_keeps_unknown_middle_column_aligned(self):
        lines = [
            "CHEMICAL COMPOSITION",
            "Charge No. Si Fe Cu Mn Mg Ga Cr Zn Ti",
            "26088 0,90 0,30 0,08 0,62 0,83 0,99 0,18 0,04 0,03",
            "min 0,70 0,00 0,00 0,40 0,60 0,00 0,00 0,00 0,00",
            "max 1,30 0,50 0,10 1,00 1,20 1,00 0,25 0,20 0,10",
            "Hardness and mechanical properties",
        ]

        matches = _parse_neuman_chemistry_from_lines(lines, page_id=1)

        self.assertEqual(matches["Si"]["final"], "0.90")
        self.assertEqual(matches["Mg"]["final"], "0.83")
        self.assertEqual(matches["Cr"]["final"], "0.18")
        self.assertEqual(matches["Ti"]["final"], "0.03")
        self.assertNotIn("Ga", matches)

    def test_metalba_parser_keeps_unknown_middle_column_aligned(self):
        lines = [
            "ANALISI CHIMICA",
            "Lotto Colata Si Fe Cu Mn Mg Ga Zn Ti Cr",
            "AA 26052B 0,10 0,20 0,30 0,40 0,50 0,99 0,60 0,70 0,80",
        ]

        matches = _parse_metalba_chemistry_from_lines(lines, page_id=1)

        self.assertEqual(matches["Si"]["final"], "0.10")
        self.assertEqual(matches["Mg"]["final"], "0.50")
        self.assertEqual(matches["Zn"]["final"], "0.60")
        self.assertEqual(matches["Cr"]["final"], "0.80")
        self.assertNotIn("Ga", matches)

    def test_impol_fallback_uses_resilient_generic_parser(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto=(
                "Chemical composition\n"
                "Si Fe Cu Mn Mg Ga Cr Zn Ti Pb\n"
                "7149 0,11 0,22 0,33 0,44 0,55 0,99 0,66 0,77 0,88 0,09\n"
            ),
            ocr_text=None,
        )

        matches = _detect_chemistry_matches([page], supplier_name="Impol d.o.o.")

        self.assertEqual(matches["Si"]["final"], "0.11")
        self.assertEqual(matches["Mg"]["final"], "0.55")
        self.assertEqual(matches["Cr"]["final"], "0.66")
        self.assertEqual(matches["Pb"]["final"], "0.09")
        self.assertNotIn("Ga", matches)

    def test_leichtmetall_fallback_uses_resilient_generic_parser(self):
        page = SimpleNamespace(
            id=1,
            testo_estratto=(
                "Chemical analysis\n"
                "Si Fe Cu Mn Mg Ga Cr Zn Ti Pb\n"
                "94668 0,12 0,23 0,34 0,45 0,56 0,99 0,67 0,78 0,89 0,10\n"
            ),
            ocr_text=None,
        )

        matches = _detect_chemistry_matches(
            [page],
            supplier_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        )

        self.assertEqual(matches["Si"]["final"], "0.12")
        self.assertEqual(matches["Mg"]["final"], "0.56")
        self.assertEqual(matches["Cr"]["final"], "0.67")
        self.assertEqual(matches["Pb"]["final"], "0.10")
        self.assertNotIn("Ga", matches)


if __name__ == "__main__":
    unittest.main()
