import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.startup import bootstrap  # registers all model relationships
from app.modules.acquisition.models import AcquisitionRow, CertificateMatch, Document
from app.modules.acquisition.schemas import AcquisitionQualityUpdateRequest, DocumentMatchDetachRequest
from app.modules.acquisition.service import (
    _create_ddt_clone_row_for_manual_link,
    _merge_certificate_only_row_into_ddt_row,
    detach_document_match,
    get_acquisition_row,
    list_gemba_walk_rows,
    list_quality_rows,
    update_quality_row,
)
from app.modules.supplier_kpi.service import _supplier_detail_sheets, _write_xlsx


class QualityPackageCountTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def make_row(self, evaluation=None):
        certificate = Document(tipo_documento="certificato", nome_file_originale="test.pdf", storage_key=f"{uuid4()}.pdf")
        self.db.add(certificate)
        self.db.flush()
        row = AcquisitionRow(
            document_certificato_id=certificate.id,
            fornitore_raw="Fornitore di prova",
            qualita_tipo_controllo="diretta",
            qualita_valutazione=evaluation,
            qualita_note="Nota invariata",
            qualita_data_accettazione=date(2026, 7, 3),
            validata_finale=bool(evaluation),
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(CertificateMatch(acquisition_row_id=row.id, document_certificato_id=certificate.id,
                                     stato="confermato", utente_conferma_id=1))
        self.db.commit()
        return get_acquisition_row(self.db, row.id)

    def test_count_update_clear_and_omitted_field_preserve_other_data_for_all_outcomes(self):
        for evaluation in (None, "accettato", "accettato_con_riserva", "respinto"):
            with self.subTest(evaluation=evaluation):
                row = self.make_row(evaluation)
                before = (row.stato_tecnico, row.stato_workflow, row.validata_finale, row.certificate_match.stato)
                for count in (3, 12, None):
                    response = update_quality_row(self.db, row=row,
                        payload=AcquisitionQualityUpdateRequest(qualita_numero_colli=count), actor_id=1)
                    self.db.expire_all()
                    row = get_acquisition_row(self.db, row.id)
                    self.assertEqual(response.qualita_numero_colli, count)
                    self.assertEqual(row.qualita_numero_colli, count)
                    self.assertEqual(row.qualita_note, "Nota invariata")
                    self.assertEqual(row.qualita_tipo_controllo, "diretta")
                    self.assertEqual(row.qualita_valutazione, evaluation)
                    self.assertEqual(row.qualita_data_accettazione, date(2026, 7, 3))
                    self.assertEqual((row.stato_tecnico, row.stato_workflow, row.validata_finale, row.certificate_match.stato), before)
                update_quality_row(self.db, row=row,
                    payload=AcquisitionQualityUpdateRequest(qualita_numero_colli=7), actor_id=1)
                update_quality_row(self.db, row=row,
                    payload=AcquisitionQualityUpdateRequest(qualita_note="Altra nota"), actor_id=1)
                self.assertEqual(row.qualita_numero_colli, 7)
                self.assertTrue(any("qualita_numero_colli" in (event.nota_breve or "") for event in row.history_events))

    def test_schema_accepts_only_positive_integer_or_null(self):
        for value in (None, 1, 2147483647):
            self.assertEqual(AcquisitionQualityUpdateRequest(qualita_numero_colli=value).qualita_numero_colli, value)
        for value in (0, -1, 1.5, 3.0, True, False, "3", "abc", "", 2147483648):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                AcquisitionQualityUpdateRequest(qualita_numero_colli=value)

    def test_count_is_shared_by_quality_gemba_and_each_supplier_export(self):
        rows = [self.make_row(), self.make_row()]
        rows[0].qualita_numero_colli = 3
        rows[1].fornitore_raw = "Altro fornitore"
        self.db.commit()
        quality = {item.id: item.qualita_numero_colli for item in list_quality_rows(self.db).items}
        gemba = {item.id: item.qualita_numero_colli for item in list_gemba_walk_rows(
            self.db, date_from=date(2000, 1, 1), date_to=date(2100, 1, 1), view="open")}
        self.assertEqual(quality, {rows[0].id: 3, rows[1].id: None})
        self.assertEqual(gemba, quality)
        sheets = _supplier_detail_sheets(rows, period_label="2026", supplier_label="Tutti i fornitori")
        self.assertEqual(len(sheets), 2)
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with ZipFile(BytesIO(_write_xlsx(sheets))) as archive:
            for index, (_, table) in enumerate(sheets, 1):
                col = table[4].index("N° colli")
                self.assertEqual(table[4][col + 1], "Note")
                count = quality[table[5][0]]
                self.assertEqual(table[5][col], count if count is not None else "")
                xml = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
                cell = xml.findall("x:sheetData/x:row", ns)[5].findall("x:c", ns)[col]
                if count is None:
                    self.assertEqual("".join(cell.itertext()), "")
                else:
                    self.assertEqual(cell.get("t"), "n")
                    self.assertEqual(cell.find("x:v", ns).text, "3")

    def test_ai_lock_still_blocks_count_updates(self):
        row = self.make_row()
        row.ai_processing_status = "in_lavorazione"
        self.db.commit()
        with self.assertRaises(HTTPException):
            update_quality_row(self.db, row=row,
                payload=AcquisitionQualityUpdateRequest(qualita_numero_colli=3), actor_id=1)
        self.assertIsNone(row.qualita_numero_colli)

    def test_merge_preserves_count_without_summing_or_changing_siblings(self):
        for source_count, target_count, expected in ((3, None, 3), (None, 5, 5), (3, 5, 5), (3, 3, 3)):
            with self.subTest(source=source_count, target=target_count):
                certificate = Document(tipo_documento="certificato", nome_file_originale="merge.pdf", storage_key=f"{uuid4()}.pdf")
                ddt = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key=f"{uuid4()}.pdf")
                self.db.add_all([certificate, ddt])
                self.db.flush()
                source = AcquisitionRow(document_certificato_id=certificate.id, qualita_numero_colli=source_count)
                target = AcquisitionRow(document_certificato_id=certificate.id, document_ddt_id=ddt.id,
                                        qualita_numero_colli=target_count)
                sibling = AcquisitionRow(document_certificato_id=certificate.id, document_ddt_id=ddt.id)
                self.db.add_all([source, target, sibling])
                self.db.commit()
                source_id = source.id
                self.assertTrue(_merge_certificate_only_row_into_ddt_row(
                    db=self.db, source_row_id=source_id, target_row=get_acquisition_row(self.db, target.id), actor_id=1))
                self.assertEqual(get_acquisition_row(self.db, target.id).qualita_numero_colli, expected)
                self.assertIsNone(self.db.get(AcquisitionRow, source_id))
                self.assertIsNone(self.db.get(AcquisitionRow, sibling.id).qualita_numero_colli)
                if source_count is not None:
                    self.assertTrue(any(f"colli origine {source_count}, mantenuti {expected}" in (event.nota_breve or "")
                                        for event in get_acquisition_row(self.db, target.id).history_events))

    def test_detach_and_clone_do_not_duplicate_count(self):
        row = self.make_row()
        ddt = Document(tipo_documento="ddt", nome_file_originale="ddt.pdf", storage_key="ddt.pdf")
        self.db.add(ddt)
        self.db.flush()
        row.document_ddt_id = ddt.id
        row.qualita_numero_colli = 4
        self.db.commit()
        result = detach_document_match(self.db, row=row, payload=DocumentMatchDetachRequest(), actor_id=1)
        self.assertEqual(result.ddt_row.qualita_numero_colli, 4)
        self.assertIsNone(result.certificate_row.qualita_numero_colli)
        clone = _create_ddt_clone_row_for_manual_link(db=self.db, source_row=row, actor_id=1)
        self.assertIsNone(clone.qualita_numero_colli)


class PackageCountMigrationTest(unittest.TestCase):
    def test_existing_database_upgrade_is_additive_and_repeatable(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE datimaterialeincoming (id INTEGER PRIMARY KEY, cdq TEXT)"))
                connection.execute(text("INSERT INTO datimaterialeincoming (id, cdq) VALUES (1, 'UNCHANGED')"))
            with patch.object(bootstrap, "engine", engine):
                bootstrap.ensure_acquisition_quality_columns()
                bootstrap.ensure_acquisition_quality_columns()
            self.assertIn("qualita_numero_colli", {c["name"] for c in inspect(engine).get_columns("datimaterialeincoming")})
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT cdq, qualita_numero_colli FROM datimaterialeincoming")).one(),
                                 ("UNCHANGED", None))
        finally:
            engine.dispose()
