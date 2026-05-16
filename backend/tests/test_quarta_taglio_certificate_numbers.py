import unittest
from types import SimpleNamespace

from app.core.departments.models import Department  # noqa: F401
from app.modules.standards.models import NormativeStandard  # noqa: F401
from app.modules.quarta_taglio.service import (
    _certificate_suffix_parts,
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


if __name__ == "__main__":
    unittest.main()
