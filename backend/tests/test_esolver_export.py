import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.esolver_export.service import esolver_pdf_export_fields, list_esolver_pdf_certificates
from app.core.integrations.schemas import EsolverSqlViewSettingsUpdateRequest
from app.modules.quarta_taglio.models import QuartaTaglioCertificatePdfVersion, QuartaTaglioFinalCertificate
from app.modules.quarta_taglio.router import (
    get_quarta_taglio_certificate_pdf_file_route,
    get_quarta_taglio_word_draft_file_route,
)


class EsolverExportTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _certificate(self, **overrides) -> QuartaTaglioFinalCertificate:
        now = datetime.now(timezone.utc)
        values = {
            "cod_odp": "OL-100",
            "status": "pdf_final",
            "certificate_number": "7000_01_01/26",
            "draft_number": "7000_01_01/26",
            "cod_f3": "605000730",
            "ddt": "DDT-10",
            "esolver_id_documento": "DOC-20",
            "esolver_id_riga_doc": "RIGA-30",
            "esolver_rif_lotto_alfanum": "LOTTO-A",
            "quantita": 25.5,
            "cert_date": now,
            "storage_key_docx": "certificate.docx",
            "storage_key_pdf": "certificate.pdf",
            "download_token": "safe-token",
            "closed_at": now,
            "updated_at": now,
        }
        values.update(overrides)
        return QuartaTaglioFinalCertificate(**values)

    def test_export_includes_only_complete_closed_certificate_and_latest_active_pdf(self):
        certificate = self._certificate()
        self.db.add(certificate)
        self.db.flush()
        self.db.add_all(
            [
                QuartaTaglioCertificatePdfVersion(
                    certificate_id=certificate.id,
                    version=1,
                    status="active",
                    storage_key_pdf="certificate-v1.pdf",
                ),
                QuartaTaglioCertificatePdfVersion(
                    certificate_id=certificate.id,
                    version=2,
                    status="active",
                    storage_key_pdf="certificate-v2.pdf",
                ),
            ]
        )
        self.db.commit()

        response = list_esolver_pdf_certificates(self.db, public_base_url="https://certi.example")

        self.assertEqual(response.total_items, 1)
        item = response.items[0]
        self.assertEqual(item.id_documento, "DOC-20")
        self.assertEqual(item.id_riga_doc, "RIGA-30")
        self.assertEqual(item.pdf_version, 2)
        self.assertEqual(item.closed_at, certificate.closed_at)
        self.assertIn("download_token=safe-token", item.pdf_url)
        self.assertEqual(item.nome_file_pdf, "7000_01_01_26.pdf")

    def test_export_excludes_missing_esolver_row_or_inactive_pdf(self):
        missing_row = self._certificate(download_token="token-one", esolver_id_riga_doc=None)
        reopened = self._certificate(download_token="token-two", esolver_id_documento="DOC-21")
        self.db.add_all([missing_row, reopened])
        self.db.flush()
        self.db.add_all(
            [
                QuartaTaglioCertificatePdfVersion(
                    certificate_id=missing_row.id,
                    version=1,
                    status="active",
                    storage_key_pdf="missing-row.pdf",
                ),
                QuartaTaglioCertificatePdfVersion(
                    certificate_id=reopened.id,
                    version=1,
                    status="reopened",
                    storage_key_pdf="reopened.pdf",
                ),
            ]
        )
        self.db.commit()

        response = list_esolver_pdf_certificates(self.db, public_base_url="https://certi.example")

        self.assertEqual(response.total_items, 0)

    def test_exported_pdf_and_register_word_download_with_short_names(self):
        certificate = self._certificate(certificate_number="7017_00_30/26", draft_number="7017_00_30/26")
        self.db.add(certificate)
        self.db.flush()
        self.db.add(QuartaTaglioCertificatePdfVersion(
            certificate_id=certificate.id,
            version=1,
            status="active",
            storage_key_pdf=certificate.storage_key_pdf,
        ))
        self.db.commit()
        exported = list_esolver_pdf_certificates(self.db, public_base_url="https://certi.example").items[0]
        pdf_url = urlsplit(exported.pdf_url)
        certificate_id = int(pdf_url.path.split("/")[-2])
        token = parse_qs(pdf_url.query)["download_token"][0]
        original_keys = (certificate.storage_key_docx, certificate.storage_key_pdf)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            for key in original_keys:
                (root / key).write_bytes(b"existing document content")
            with patch("app.modules.quarta_taglio.service._certificate_storage_path", side_effect=lambda key: root / key):
                pdf_response = get_quarta_taglio_certificate_pdf_file_route(certificate_id, self.db, token)
                word_response = get_quarta_taglio_word_draft_file_route(certificate_id, self.db, token)

            for response, key, extension in (
                (pdf_response, certificate.storage_key_pdf, "pdf"),
                (word_response, certificate.storage_key_docx, "docx"),
            ):
                self.assertEqual(response.headers["content-disposition"], f'attachment; filename="7017_00_30_26.{extension}"')
                self.assertEqual(response.path, root / key)
                self.assertEqual(response.path.read_bytes(), b"existing document content")

        self.assertEqual((certificate.storage_key_docx, certificate.storage_key_pdf), original_keys)
        self.assertEqual(certificate.certificate_number, "7017_00_30/26")
        self.assertEqual(certificate.status, "pdf_final")
        self.assertFalse(self.db.dirty)

    def test_field_contract_includes_identity_and_pdf_lifecycle(self):
        self.assertEqual(esolver_pdf_export_fields()[0], "IdCerti")
        self.assertIn("PdfVersion", esolver_pdf_export_fields())
        self.assertIn("ClosedAt", esolver_pdf_export_fields())
        self.assertEqual(esolver_pdf_export_fields()[-1], "NomeFilePdf")

    def test_publication_cannot_be_enabled_with_missing_it_data(self):
        with self.assertRaises(ValidationError):
            EsolverSqlViewSettingsUpdateRequest(
                enabled=True,
                external_host=None,
                external_port=None,
                reader_username=None,
                allowed_source=None,
                ssl_mode="DA_FORNIRE_IT",
                notes="",
            )

    def test_incomplete_it_data_can_be_saved_while_publication_is_disabled(self):
        payload = EsolverSqlViewSettingsUpdateRequest(
            enabled=False,
            external_host=None,
            external_port=None,
            reader_username=None,
            allowed_source=None,
            ssl_mode="DA_FORNIRE_IT",
            notes="In attesa di IT",
        )
        self.assertFalse(payload.enabled)


if __name__ == "__main__":
    unittest.main()
