import json
import unittest
from datetime import date, timedelta
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
from app.modules.supplier_calendar.models import SupplierCalendarClosure
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
                self.assertEqual(rows[0]["Tempo controllo giorni"], "0")
                self.assertEqual(rows[0]["Rm"], "-" if index == 0 else "325")
                summary = build_supplier_kpi_summary(self.db, year=2026, month=11, supplier_id=self.leicht.id)
                closed = int(index == 2)
                self.assertEqual((summary.totals.lotti_totali, summary.totals.lotti_scarti,
                                  summary.totals.tonnellate), (closed, closed, closed))
                self.assertEqual(summary.totals.tempo_medio_controllo_giorni, 0)
                self.assertEqual(sheets["Sintesi periodo"][4], ["Lotti totali", str(closed)])
                self.assertEqual(sheets["Mesi"][1][1], str(closed))
                self.assertEqual(sheets["Fornitori"][1][2:], [str(closed), "0", "0", str(closed), "-", "0,00"])

        reopen_final_validation(self.db, lot, actor_id=1)
        reopened = self.export(month=11)
        self.assertEqual([r["Valutazione"] for r in _detail(reopened["Leichtmetall"])],
                         ["Da valutare", "Da valutare – proprietà da completare"])
        self.assertEqual(reopened["Sintesi periodo"][4], ["Lotti totali", "0"])
        self.assertEqual(reopened["Fornitori"][1][-1], "0,00")

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
        summary = build_supplier_kpi_summary(self.db, year=2026)
        self.assertFalse(summary.by_supplier)
        self.assertIsNone(summary.totals.tempo_medio_controllo_giorni)

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

    def test_pending_only_changes_time_metrics_not_quality_totals_or_closed_detail(self):
        closed = self.lot(1)
        closed.validata_finale = True
        closed.qualita_valutazione = "accettato_con_riserva"
        closed.qualita_data_accettazione = date(2026, 11, 13)
        before = self.export()
        self.lot(2)
        after = self.export()
        self.assertEqual(before["Sintesi periodo"][:-2], after["Sintesi periodo"][:-2])
        self.assertEqual(before["Fornitori"][1][:6], after["Fornitori"][1][:6])
        self.assertEqual(before["Mesi"], after["Mesi"])
        self.assertEqual(before["Sintesi periodo"][-1][1], "4,00")
        self.assertEqual(after["Sintesi periodo"][-1][1], "2,00")
        self.assertEqual(after["Fornitori"][1][-1], "2,00")
        self.assertEqual(_detail(before["Leichtmetall"])[0], _detail(after["Leichtmetall"])[0])

    def test_leichtmetall_november_delays_and_no_duplicate_after_acceptance(self):
        for number, delay in enumerate((0, 0, -14, 3, 0, 28, -7, -2), 1):
            lot = self.lot(number)
            lot.qualita_data_richiesta = lot.qualita_data_ricezione - timedelta(days=delay)
            if number <= 6:
                lot.validata_finale = True
                lot.qualita_valutazione = "accettato"

        params = dict(year=2026, month=11, supplier_id=self.leicht.id)
        self.db.commit()
        summary = build_supplier_kpi_summary(self.db, **params)
        self.assertEqual((summary.totals.lotti_totali, summary.totals.lotti_accettati), (6, 6))
        self.assertEqual((summary.totals.ritardo_medio_giorni, summary.totals.tempo_medio_controllo_giorni), (1, 0))
        self.assertEqual(summary.by_supplier[0].metrics, summary.totals)

        xlsx = _sheets(build_supplier_kpi_xlsx(self.db, **params))
        self.assertEqual(xlsx["Sintesi periodo"][-2][1], "1,00")
        self.assertEqual(xlsx["Fornitori"][1][-2:], ["1,00", "0,00"])
        rows = _detail(xlsx["Leichtmetall"])
        self.assertEqual([(r["Ritardo giorni"], r["Tempo controllo giorni"]) for r in rows[-2:]], [("-7", "0"), ("-2", "0")])

        lot.values.append(_value("proprieta", "Rm", "325"))
        validate_final_row(self.db, lot, AcquisitionFinalValidationRequest(qualita_valutazione="accettato"), actor_id=1)
        self.db.commit()
        after = build_supplier_kpi_summary(self.db, **params)
        self.assertEqual((after.totals.lotti_totali, after.totals.lotti_accettati, after.totals.ritardo_medio_giorni), (7, 7, 1))
        self.assertEqual(len(_detail(_sheets(build_supplier_kpi_xlsx(self.db, **params))["Leichtmetall"])), 8)

    def test_missing_dates_are_independent_and_pending_uses_working_calendar(self):
        friday = date(2026, 12, 4)
        wednesday = date(2026, 12, 9)
        control_only = self.lot(1, receipt=friday)
        control_only.qualita_data_accettazione = wednesday
        delay_only = self.lot(2, receipt=friday)
        delay_only.qualita_data_richiesta = date(2026, 12, 8)
        delay_only.qualita_data_accettazione = None
        neither = self.lot(3, receipt=friday)
        neither.qualita_data_accettazione = None
        self.db.add(SupplierCalendarClosure(start_date=date(2026, 12, 7), end_date=date(2026, 12, 7), label="Chiusura"))
        sheets = self.export(month=12)
        rows = _detail(sheets["Leichtmetall"])
        # Only Wednesday is a working day after delivery: weekend, company closure and 8 Dec are excluded.
        self.assertEqual([(r["Ritardo giorni"], r["Tempo controllo giorni"]) for r in rows], [("-", "1"), ("-4", ""), ("-", "")])
        summary = build_supplier_kpi_summary(self.db, year=2026, month=12)
        self.assertEqual(summary.totals.lotti_totali, 0)
        self.assertEqual((summary.totals.ritardo_medio_giorni, summary.totals.tempo_medio_controllo_giorni), (-4, 1))
        self.assertEqual(sheets["Fornitori"][1][2:], ["0", "0", "0", "0", "-4,00", "1,00"])

    def test_identical_month_quarter_year_and_supplier_filters_for_app_and_export(self):
        dates = [date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 6, 30),
                 date(2026, 7, 1), date(2026, 9, 30), date(2026, 10, 1), date(2026, 12, 31),
                 date(2025, 12, 31), date(2027, 1, 1), date(2026, 9, 30)]
        for number, received in enumerate(dates, 1):
            row = self.lot(number, self.metalba if number == 11 else self.leicht, receipt=received)
            row.qualita_data_richiesta = received - timedelta(days=number)
            row.qualita_data_accettazione = received + timedelta(days=2)
        self.db.commit()
        for params, expected, score in (
            ({"quarter": 1}, [1, 2], 1.5), ({"quarter": 2}, [1, 2, 3, 4], 2.5),
            ({"quarter": 3}, list(range(1, 7)), 3.5), ({"quarter": 4}, list(range(1, 9)), 4.5),
            ({}, list(range(1, 9)), 4.5), ({"month": 9, "quarter": 1}, [6], 6.0),
            ({"month": 12}, [8], 8.0),
        ):
            with self.subTest(params=params):
                scope = dict(params, year=2026, supplier_id=self.leicht.id)
                summary = build_supplier_kpi_summary(self.db, **scope)
                xlsx = _sheets(build_supplier_kpi_xlsx(self.db, **scope))
                self.assertNotIn("Metalba", xlsx)
                self.assertEqual([int(r["N."]) for r in _detail(xlsx["Leichtmetall"])], expected)
                self.assertEqual(summary.totals.ritardo_medio_giorni, score)
                self.assertEqual(xlsx["Fornitori"][1][-2], f"{score:.2f}".replace(".", ","))
                self.assertEqual(summary.totals.lotti_totali, 0)
                if params.get("month") in (9, 12):
                    # Acceptance is in the following month. The lot stays in its receipt month;
                    # for 31 December, the calendar must still exclude New Year's Day.
                    control_days = 2 if params["month"] == 9 else 0
                    self.assertEqual(summary.totals.tempo_medio_controllo_giorni, control_days)
                    self.assertEqual(_detail(xlsx["Leichtmetall"])[0]["Tempo controllo giorni"], str(control_days))
        all_suppliers = build_supplier_kpi_summary(self.db, year=2026, month=9)
        self.assertEqual(all_suppliers.totals.ritardo_medio_giorni, 8.5)
