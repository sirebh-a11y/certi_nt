import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core.departments.models import Department  # noqa: F401 - ensures SQLAlchemy relationship resolution
from app.core.users.models import User
from app.modules.quarta_taglio.certificate_docx import build_forgialluminio_draft_docx, update_docx_content_controls
from app.modules.quarta_taglio.schemas import QuartaTaglioDetailResponse
from app.modules.standards.models import NormativeStandard  # noqa: F401 - ensures SQLAlchemy relationship resolution


class QuartaTaglioDocxContentControlTests(unittest.TestCase):
    def test_header_dynamic_fields_are_word_content_controls(self) -> None:
        detail = QuartaTaglioDetailResponse(
            cod_odp="OLTEST",
            ready=True,
            status_color="green",
            status_message="ok",
            can_create_word=True,
            header={
                "data_certificato": "",
                "cliente": "CLIENTE TEST",
                "ordine_cliente": "ORD123",
                "conferma_ordine": "CDO456",
                "codice_f3_raw": "100",
                "descrizione_raw": "RAW DESC",
                "ddt_raw": "",
                "quantita_raw": "10",
                "codice_f3_finished": "200",
                "descrizione_finished": "",
                "ddt_finished": "",
                "quantita_finished": "",
            },
            materials=[],
            missing_items=[],
            standard_candidates=[],
            selected_standard=None,
            selected_standard_confirmed=True,
            chemistry=[],
            properties=[],
            notes=[],
            conformity_status="conforme",
            conformity_issues=[],
            esolver_rows=[],
            certifiable_units=[],
        )
        user = User(name="System Admin", email="system@example.test", role="admin")
        output_path = Path(tempfile.gettempdir()) / "certi_nt_content_controls_test.docx"

        build_forgialluminio_draft_docx(
            detail=detail,
            output_path=output_path,
            draft_number="7000_00_00/26",
            certified_by=user,
            quality_manager=user,
        )

        with zipfile.ZipFile(output_path) as archive:
            header_xml = "".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("word/header")
            )

        expected_tags = {
            "CERT_NUMBER",
            "CERT_DATE",
            "PURCHASER",
            "ORDER_CLIENT",
            "CONFIRM_ORDER",
            "COD_F3_RAW",
            "RAW_DESCRIPTION",
            "DDT_RAW",
            "QUANTITY_RAW",
            "COD_F3_FINISHED",
            "FINISHED_DESCRIPTION",
            "DDT_FINISHED",
            "QUANTITY_FINISHED",
        }
        for tag in expected_tags:
            self.assertIn(f'w:val="{tag}"', header_xml)
        self.assertEqual(header_xml.count("<w:sdt>"), len(expected_tags))

    def test_update_content_controls_changes_only_tagged_values(self) -> None:
        detail = QuartaTaglioDetailResponse(
            cod_odp="OLTEST",
            ready=True,
            status_color="green",
            status_message="ok",
            can_create_word=True,
            header={
                "data_certificato": "",
                "cliente": "CLIENTE TEST",
                "ordine_cliente": "ORD123",
                "conferma_ordine": "CDO456",
                "codice_f3_raw": "100",
                "descrizione_raw": "RAW DESC",
                "ddt_raw": "",
                "quantita_raw": "10",
                "codice_f3_finished": "",
                "descrizione_finished": "",
                "ddt_finished": "",
                "quantita_finished": "",
            },
            materials=[],
            missing_items=[],
            standard_candidates=[],
            selected_standard=None,
            selected_standard_confirmed=True,
            chemistry=[],
            properties=[],
            notes=[],
            conformity_status="conforme",
            conformity_issues=[],
            esolver_rows=[],
            certifiable_units=[],
        )
        user = User(name="System Admin", email="system@example.test", role="admin")
        source_path = Path(tempfile.gettempdir()) / "certi_nt_content_controls_source.docx"
        output_path = Path(tempfile.gettempdir()) / "certi_nt_content_controls_updated.docx"
        build_forgialluminio_draft_docx(
            detail=detail,
            output_path=source_path,
            draft_number="7000_00_00/26",
            certified_by=user,
            quality_manager=user,
        )

        updated, missing = update_docx_content_controls(
            source_path,
            output_path,
            {
                "CERT_DATE": "19/05/2026",
                "DDT_RAW": "1133-19/05/2026",
                "COD_F3_FINISHED": "605001860",
            },
        )

        self.assertIn("CERT_DATE", updated)
        self.assertIn("DDT_RAW", updated)
        self.assertIn("COD_F3_FINISHED", updated)
        self.assertEqual(missing, [])
        with zipfile.ZipFile(output_path) as archive:
            header_xml = "".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("word/header")
            )
        self.assertIn("19/05/2026", header_xml)
        self.assertIn("1133-19/05/2026", header_xml)
        self.assertIn("605001860", header_xml)


if __name__ == "__main__":
    unittest.main()
