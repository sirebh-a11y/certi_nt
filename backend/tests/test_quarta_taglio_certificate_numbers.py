import unittest
from types import SimpleNamespace

from app.core.departments.models import Department  # noqa: F401
from app.modules.standards.models import NormativeStandard  # noqa: F401
from app.modules.quarta_taglio.service import (
    _certificate_main_number,
    _certificate_suffix_for_ol_or_next,
    _certificate_suffix_parts,
    _cod_f3_certificate_suffix,
    _find_existing_certificate_for_unit,
    _format_certificate_suffix,
    _next_certificate_suffix,
)


class QuartaTaglioCertificateNumberTest(unittest.TestCase):
    def test_certificate_suffix_is_formatted_with_two_digits(self):
        self.assertEqual(_format_certificate_suffix(1), "01")
        self.assertEqual(_format_certificate_suffix(9), "09")
        self.assertEqual(_format_certificate_suffix(10), "10")

    def test_next_suffix_accepts_old_and_new_existing_formats(self):
        certificates = [
            SimpleNamespace(certificate_number="7001_1/26"),
            SimpleNamespace(certificate_number="7001_09/26"),
            SimpleNamespace(certificate_number="7001_10/26"),
            SimpleNamespace(certificate_number="7002_99/26"),
        ]

        self.assertEqual(_next_certificate_suffix(certificates, base_number=7001, year_suffix="26"), 11)

    def test_suffix_parser_keeps_compatibility_with_old_numbers(self):
        self.assertEqual(_certificate_suffix_parts("7001_1/26"), (7001, 1, "26"))
        self.assertEqual(_certificate_suffix_parts("7001_01/26"), (7001, 1, "26"))
        self.assertEqual(_certificate_suffix_parts("7001_00_083/26"), (7001, 0, "26"))

    def test_main_number_does_not_change_with_cod_f3_suffix(self):
        self.assertEqual(_certificate_main_number("7001_00_083/26"), 7001)
        self.assertEqual(_certificate_main_number("7001_01_060/26"), 7001)

    def test_next_suffix_progresses_without_changing_main_number(self):
        certificates = [
            SimpleNamespace(certificate_number="7001_00_083/26"),
            SimpleNamespace(certificate_number="7001_01_060/26"),
            SimpleNamespace(certificate_number="7002_00_083/26"),
        ]

        self.assertEqual(_next_certificate_suffix(certificates, base_number=7001, year_suffix="26"), 2)

    def test_same_ol_reuses_first_suffix(self):
        certificates = [
            SimpleNamespace(certificate_number="7001_00_083/26", cod_odp="OL2026000428"),
            SimpleNamespace(certificate_number="7001_01_060/26", cod_odp="OL2026000429"),
        ]

        self.assertEqual(
            _certificate_suffix_for_ol_or_next(
                certificates,
                base_number=7001,
                year_suffix="26",
                cod_odp="OL2026000428",
            ),
            0,
        )

    def test_different_ol_with_same_cdq_gets_next_first_suffix(self):
        certificates = [
            SimpleNamespace(certificate_number="7001_00_083/26", cod_odp="OL2026000428"),
            SimpleNamespace(certificate_number="7001_01_060/26", cod_odp="OL2026000429"),
        ]

        self.assertEqual(
            _certificate_suffix_for_ol_or_next(
                certificates,
                base_number=7001,
                year_suffix="26",
                cod_odp="OL2026000430",
            ),
            2,
        )

    def test_cod_f3_suffix_uses_last_two_digits(self):
        self.assertEqual(_cod_f3_certificate_suffix("047012883"), "83")
        self.assertEqual(_cod_f3_certificate_suffix("605000900"), "00")
        self.assertEqual(_cod_f3_certificate_suffix("7"), "07")
        self.assertEqual(_cod_f3_certificate_suffix(None), "00")

    def test_existing_certificate_without_ddt_is_reused_when_esolver_adds_ddt(self):
        certificates = [
            SimpleNamespace(id=1, status="draft", cod_f3="292000100", ddt=None),
            SimpleNamespace(id=2, status="draft", cod_f3="605000700", ddt="1133"),
        ]
        unit = SimpleNamespace(cod_f3="292000100", ddt="1204-29/04/2026")

        self.assertIs(_find_existing_certificate_for_unit(certificates, unit=unit, used_certificate_ids=set()), certificates[0])

    def test_existing_certificate_matching_keeps_distinct_cod_f3_lines_separate(self):
        certificates = [
            SimpleNamespace(id=1, status="draft", cod_f3="292000100", ddt=None),
            SimpleNamespace(id=2, status="draft", cod_f3="605000700", ddt=None),
        ]
        unit = SimpleNamespace(cod_f3="605000700", ddt="2526-10/12/2025")

        self.assertIs(_find_existing_certificate_for_unit(certificates, unit=unit, used_certificate_ids={1}), certificates[1])


if __name__ == "__main__":
    unittest.main()
