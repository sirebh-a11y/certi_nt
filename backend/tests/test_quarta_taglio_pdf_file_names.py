import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.modules.quarta_taglio.schemas import QuartaTaglioPdfGenerateRequest
from app.startup.bootstrap import ensure_quarta_taglio_pdf_filename_columns


class PdfFileNameTest(unittest.TestCase):
    def test_names_are_validated_without_losing_customer_text(self):
        for value, expected in (
            ("Cliente 123", "Cliente 123.pdf"),
            (" Qualità ordine 123.PDF ", "Qualità ordine 123.pdf"),
            ("7017_00_30_26.pdf", "7017_00_30_26.pdf"),
        ):
            with self.subTest(value=value):
                self.assertEqual(QuartaTaglioPdfGenerateRequest(pdf_file_name=value).pdf_file_name, expected)
        self.assertIsNone(QuartaTaglioPdfGenerateRequest().pdf_file_name)

    def test_empty_unsafe_and_overlong_names_are_rejected(self):
        for value in ("", " ", ".pdf", "../other.pdf", "folder/file.pdf", "C:\\other.pdf", "foo\n.pdf",
                      "foo?.pdf", "foo\x7f.pdf", "NUL.pdf", "con.txt.pdf", "foo..pdf", "x" * 252):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                QuartaTaglioPdfGenerateRequest(pdf_file_name=value)

    def test_existing_databases_gain_nullable_names_idempotently(self):
        engine = create_engine("sqlite:///:memory:")
        tables = ("quarta_taglio_final_certificates", "quarta_taglio_certificate_pdf_versions")
        try:
            with engine.begin() as connection:
                for table in tables:
                    connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, storage_key_pdf TEXT)"))
                    connection.execute(text(f"INSERT INTO {table} VALUES (1, 'unchanged.pdf')"))
            with patch("app.startup.bootstrap.engine", engine):
                ensure_quarta_taglio_pdf_filename_columns()
                ensure_quarta_taglio_pdf_filename_columns()
            with engine.connect() as connection:
                for table in tables:
                    self.assertIn("pdf_file_name", {c["name"] for c in inspect(engine).get_columns(table)})
                    self.assertEqual(tuple(connection.execute(text(f"SELECT storage_key_pdf, pdf_file_name FROM {table}")).one()),
                                     ("unchanged.pdf", None))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
