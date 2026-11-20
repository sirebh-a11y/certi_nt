import json
import unittest
from datetime import date
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.users.models import User  # noqa: F401
from app.modules.acquisition.models import (
    AcquisitionHistoryEvent, AcquisitionRow, CertificateMatch, Document, DocumentEvidence, ReadValue,
)
from app.modules.acquisition.schemas import AcquisitionFinalValidationRequest
from app.modules.acquisition.service import LEICHTMETALL_GROUP_EVIDENCE, reopen_final_validation, validate_final_row
from app.modules.notes.models import AcquisitionRowNoteTemplate  # noqa: F401
from app.modules.supplier_kpi.service import build_supplier_kpi_summary, build_supplier_kpi_xlsx
from app.modules.suppliers.models import Supplier


def _sheets(content):
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(content)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        result = {}
        for index, sheet in enumerate(workbook.findall("s:sheets/s:sheet", ns), 1):
            root = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
            result[sheet.attrib["name"]] = [
                ["".join(cell.itertext()) for cell in row.findall("s:c", ns)]
                for row in root.findall("s:sheetData/s:row", ns)
            ]
        return result


def _detail(sheet):
    return [dict(zip(sheet[4], row, strict=True)) for row in sheet[5:]]


def _value(block, key, value, status="confermato"):
    return ReadValue(blocco=block, campo=key, valore_grezzo=value, stato=status,
                     fonte_documentale="ddt" if block == "ddt" else "certificato", metodo_lettura="manuale")


class SupplierKpiPendingExportTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = Session(engine)
        self.addCleanup(engine.dispose)
        self.addCleanup(self.db.close)
        self.leicht = Supplier(ragione_sociale="Leichtmetall", reader_template_key="leichtmetall")
        self.metalba = Supplier(ragione_sociale="Metalba", reader_template_key="metalba")
        self.db.add_all([self.leicht, self.metalba])
        self.db.flush()

    def lot(self, number, supplier=None, receipt=date(2026, 11, 9)):
        supplier = supplier or self.leicht

        def document(kind):
            return Document(tipo_documento=kind, supplier=supplier, nome_file_originale=f"{kind}.pdf",
                            storage_key=f"{number}-{kind}.pdf")

        cert = document("certificato")
        row = AcquisitionRow(id=number, supplier=supplier, certificate_document=cert, ddt_document=document("ddt"),
                             qualita_data_ricezione=receipt, qualita_data_accettazione=date(2026, 11, 9),
                             qualita_tipo_controllo="diretta", peso="1000", cdq=str(number))
        row.certificate_match = CertificateMatch(certificate_document=cert, stato="confermato")
        row.values = [_value("ddt", key, value) for key, value in
                      (("ddt", "80011553"), ("lega", "7075"), ("colata", "95135"),
                       ("diametro", "295"), ("peso", "1000"), ("ordine", "342"))]
        row.values.extend([_value("chimica", "Si", "0,22"), _value("note", "nota", "OK")])
        self.db.add(row)
        return row

    def export(self, **params):
        self.db.commit()
        return _sheets(build_supplier_kpi_xlsx(self.db, year=2026, **params))

    def test_pending_only_then_confirm_properties_then_finalize(self):
        lot = self.lot(309)
        self.lot(337)
        for index, expected in enumerate(("Da valutare – proprietà da completare", "Da valutare", "Respinto")):
            with self.subTest(expected=expected):
                if index == 1:
                    lot.values.append(_value("proprieta", "Rm", "325"))
                elif index == 2:
                    validate_final_row(self.db, lot, AcquisitionFinalValidationRequest(
                        qualita_valutazione="respinto", qualita_note="Fuori specifica"), actor_id=1)
                sheets = self.export(month=11, supplier_id=self.leicht.id)
                self.assertEqual(sheets["Sintesi periodo"][1], ["Fornitore", "Leichtmetall"])
                rows = _detail(sheets["Leichtmetall"])
                self.assertEqual([r["N."] for r in rows], ["309", "337"])
                self.assertEqual(rows[0]["Valutazione"], expected)
                self.assertEqual(rows[0]["Data accettazione"], "09/11/2026")
                self.assertEqual(rows[0]["Tempo controllo giorni"], "0" if index == 2 else "")
                self.assertEqual(rows[0]["Rm"], "-" if index == 0 else "325")
                summary = build_supplier_kpi_summary(self.db, year=2026, month=11, supplier_id=self.leicht.id)
                closed = int(index == 2)
                self.assertEqual((summary.totals.lotti_totali, summary.totals.lotti_scarti,
                                  summary.totals.tonnellate), (closed, closed, closed))
                self.assertEqual(summary.totals.tempo_medio_controllo_giorni, 0 if closed else None)
                self.assertEqual(sheets["Sintesi periodo"][4], ["Lotti totali", str(closed)])
                self.assertEqual(sheets["Mesi"][1][1], str(closed))
                self.assertEqual(len(sheets["Fornitori"]), 1 + closed)

        reopen_final_validation(self.db, lot, actor_id=1)
        reopened = self.export(month=11)
        self.assertEqual([r["Valutazione"] for r in _detail(reopened["Leichtmetall"])],
                         ["Da valutare", "Da valutare – proprietà da completare"])
        self.assertEqual(reopened["Sintesi periodo"][4], ["Lotti totali", "0"])

    def test_export_excludes_other_open_blocks_and_unverified_compound_match(self):
        for number, block in ((374, "note"), (375, "chimica"), (376, "ddt")):
            row = self.lot(number, self.metalba)
            next(v for v in row.values if v.blocco == block).stato = "proposto"
        self.lot(377).certificate_match.stato = "proposto"
        self.lot(378).ai_processing_status = "in_lavorazione"
        self.lot(379).ddt_document = None
        self.lot(380).qualita_valutazione = "accettato"
        grouped = self.lot(381)
        self.db.flush()
        grouped.evidences.append(DocumentEvidence(document_id=grouped.document_certificato_id, blocco="match",
            tipo_evidenza=LEICHTMETALL_GROUP_EVIDENCE, metodo_estrazione="test",
            testo_grezzo=json.dumps({"ddt_id": grouped.document_ddt_id, "certificate_id": grouped.document_certificato_id})))
        self.assertEqual(list(self.export()), ["Sintesi periodo", "Fornitori", "Mesi"])

    def test_supplier_period_quick_confirmation_and_partial_properties(self):
        first = self.lot(301)
        first.values.extend([_value("proprieta", "Rm", "310", "proposto"), _value("proprieta", "HB", "90")])
        second = self.lot(302, self.metalba)
        second.values = [v for v in second.values if v.blocco != "note"]
        second.history_events = [AcquisitionHistoryEvent(blocco="note", azione="conferma_rapida_certificazione")]
        self.lot(303, receipt=None)
        self.lot(304, receipt=date(2025, 11, 9))
        self.lot(305, receipt=date(2026, 9, 30))
        sheets = self.export(month=11)
        [row] = _detail(sheets["Leichtmetall"])
        self.assertEqual((row["N."], row["Valutazione"], row["Si"], row["HB"], row["Rm"]),
                         ("301", "Da valutare – proprietà da completare", "0,22", "90", "-"))
        self.assertEqual([r["N."] for r in _detail(sheets["Metalba"])], ["302"])
        quarter = self.export(quarter=3, supplier_id=self.leicht.id)
        self.assertNotIn("Metalba", quarter)
        self.assertEqual([r["N."] for r in _detail(quarter["Leichtmetall"])], ["305"])

    def test_adding_open_lot_changes_no_summary_sheet_or_closed_detail(self):
        closed = self.lot(1)
        closed.validata_finale = True
        closed.qualita_valutazione = "accettato_con_riserva"
        closed.qualita_data_accettazione = date(2026, 11, 13)
        before = self.export()
        self.lot(2)
        after = self.export()
        for tab in ("Sintesi periodo", "Fornitori", "Mesi"):
            self.assertEqual(before[tab], after[tab])
        self.assertEqual(_detail(before["Leichtmetall"])[0], _detail(after["Leichtmetall"])[0])
