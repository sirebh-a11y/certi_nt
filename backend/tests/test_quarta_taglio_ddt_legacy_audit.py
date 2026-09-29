"""Read-only historical dry-run tests on an isolated SQLite database."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.modules.quarta_taglio.ddt_legacy_audit import analyze_legacy_cache
from app.modules.quarta_taglio.ddt_legacy_import import import_legacy_cache
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _normalize
from app.modules.quarta_taglio.models import (
    QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem, QuartaTaglioEsolverLink,
    QuartaTaglioFinalCertificate, QuartaTaglioRow,
)


def source_row(**changes):
    row = dict(IdDocumento="100", IdRigaDoc="1", RifLottoAlfanum="lot-a", ORP="OL1",
               CodF3="F3", DDT="77-01/09/2026", RagSoc="Cliente", ODVCli="PO",
               ODVF3="CONF", QtaUmMag=Decimal("12"), CertificatoPresente=False)
    row.update(changes)
    return row


def cached_row(**changes):
    source = source_row(**changes)
    return dict(id_documento=source["IdDocumento"], id_riga_doc=source["IdRigaDoc"],
                rif_lotto_alfanum=source["RifLottoAlfanum"], orp=source["ORP"],
                cod_f3=source["CodF3"], ddt=source["DDT"], rag_soc=source["RagSoc"],
                odv_cli=source["ODVCli"], odv_f3=source["ODVF3"],
                qta_um_mag=float(source["QtaUmMag"]), certificato_presente=source["CertificatoPresente"])


class LegacyDdtAuditTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add(QuartaTaglioRow(codice_registro="R1", cod_odp="OL1", cdq="CDQ1"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_cache(self, rows, ol="OL1"):
        self.db.add(QuartaTaglioEsolverLink(cod_odp=ol, rows=rows))
        self.db.commit()

    def test_without_complete_source_no_historical_import_is_claimed(self):
        self.add_cache([cached_row()])
        report = analyze_legacy_cache(self.db)
        self.assertEqual(report["status"], "source_baseline_required")
        self.assertEqual(report["counts"]["source_unknown_units"], 1)
        self.assertNotIn("recoverable_historical", report["counts"])
        self.assertFalse(self.db.dirty)

    def test_empty_live_source_is_not_accepted_as_complete_when_cache_exists(self):
        self.add_cache([cached_row()])
        report = analyze_legacy_cache(self.db, current_rows=[])
        self.assertEqual(report["status"], "source_baseline_required")
        self.assertEqual(report["issues"]["empty_current_source_with_cache"], 1)

    def test_unique_old_unit_can_be_recovered_but_current_unit_is_skipped(self):
        self.add_cache([cached_row(), cached_row(IdDocumento="101")])
        report = analyze_legacy_cache(self.db, current_rows=[source_row(IdDocumento="101")])
        self.assertEqual(report["status"], "classified")
        self.assertEqual(report["counts"]["already_in_current_source"], 1)
        self.assertEqual(report["counts"]["historical_units"], 1)
        self.assertEqual(report["counts"]["recoverable_historical"], 1)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioEsolverLink)))), 1)
        self.assertFalse(self.db.dirty)

    def test_duplicate_cache_identity_never_becomes_recoverable(self):
        self.add_cache([cached_row(), cached_row()])
        report = analyze_legacy_cache(self.db, current_rows=[source_row(IdDocumento="200")])
        self.assertEqual(report["counts"]["duplicate_identity_units"], 1)
        self.assertEqual(report["counts"]["review_units"], 1)
        self.assertNotIn("recoverable_historical", report["counts"])

    def test_changed_ol_with_same_document_row_and_lot_requires_review(self):
        self.add_cache([cached_row()])
        report = analyze_legacy_cache(self.db, current_rows=[source_row(ORP="OL2")])
        self.assertEqual(report["issues"]["source_identity_changed"], 1)
        self.assertEqual(report["counts"]["review_units"], 1)
        self.assertNotIn("recoverable_historical", report["counts"])

    def test_existing_exact_pdf_is_counted_as_completed_only_when_verified(self):
        self.add_cache([cached_row()])
        values = _normalize(source_row())
        cert = QuartaTaglioFinalCertificate(
            cod_odp="OL1", draft_number="D1", status="pdf_final",
            unit_key=values["certification_unit_key"], cod_f3="F3", ddt="77-01/09/2026",
            esolver_id_documento="100", esolver_id_riga_doc="1", esolver_rif_lotto_alfanum="lot-a",
            ordine_cliente="PO", quantita=12,
        )
        self.db.add(cert)
        self.db.commit()
        with patch("app.modules.quarta_taglio.ddt_legacy_audit._pdf_valid", return_value=True):
            report = analyze_legacy_cache(self.db, current_rows=[source_row(IdDocumento="200")])
        self.assertEqual(report["counts"]["completed_historical"], 1)
        self.assertNotIn("recoverable_historical", report["counts"])

    def test_import_recovers_only_unique_history_and_is_idempotent(self):
        self.add_cache([
            cached_row(IdDocumento="100", QtaUmMag=12),
            cached_row(IdDocumento="100", QtaUmMag=1),
            cached_row(IdDocumento="101", QtaUmMag=7),
        ])
        current = [source_row(IdDocumento="200", QtaUmMag=5)]
        result = import_legacy_cache(self.db, current_rows=current)
        self.db.commit()
        self.assertEqual(result["audit"]["counts"]["duplicate_identity_units"], 1)
        self.assertEqual(result["historical_imported"], 1)
        items = list(self.db.scalars(select(QuartaTaglioDdtWorkItem)))
        self.assertEqual({item.id_documento for item in items}, {"101", "200"})
        historical = next(item for item in items if item.id_documento == "101")
        self.assertFalse(historical.source_present)
        self.assertEqual(historical.quantita, 7)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtSyncRun)))), 1)

        repeated = import_legacy_cache(self.db, current_rows=current)
        self.db.commit()
        self.assertEqual(repeated["historical_imported"], 0)
        self.assertEqual(repeated["historical_already_present"], 1)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtWorkItem)))), 2)

    def test_import_refuses_duplicate_current_source_without_writing(self):
        self.add_cache([cached_row()])
        current = [source_row(IdDocumento="200"), source_row(IdDocumento="200", QtaUmMag=1)]
        with self.assertRaisesRegex(SnapshotError, "legacy_source_baseline_required"):
            import_legacy_cache(self.db, current_rows=current)
        self.assertFalse(list(self.db.scalars(select(QuartaTaglioDdtWorkItem))))
        self.assertFalse(list(self.db.scalars(select(QuartaTaglioDdtSyncRun))))

    def test_import_never_overwrites_an_existing_conflicting_quantity(self):
        self.add_cache([cached_row()])
        values = _normalize(source_row())
        seen_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.db.add(QuartaTaglioDdtWorkItem(
            source_key=values["source_key"], id_documento="100", id_riga_doc="1",
            rif_lotto_alfanum="lot-a", cod_odp="OL1", cod_f3="F3",
            ddt_raw="77-01/09/2026", quantita=99, first_seen_at=seen_at,
            last_seen_at=seen_at, source_present=False,
        ))
        self.db.commit()
        result = import_legacy_cache(self.db, current_rows=[source_row(IdDocumento="200")])
        self.db.commit()
        self.assertEqual(result["historical_imported"], 0)
        self.assertEqual(result["historical_existing_conflicts"], 1)
        saved = self.db.scalar(select(QuartaTaglioDdtWorkItem).where(
            QuartaTaglioDdtWorkItem.id_documento == "100"))
        self.assertEqual(saved.quantita, 99)

    def test_ambiguous_historical_group_is_excluded_in_both_orders(self):
        for order in (("OL1", "OL2"), ("OL2", "OL1")):
            with self.subTest(order=order):
                self.db.query(QuartaTaglioDdtWorkItem).delete()
                self.db.query(QuartaTaglioEsolverLink).delete()
                if not self.db.query(QuartaTaglioRow).filter_by(cod_odp="OL2").first():
                    self.db.add(QuartaTaglioRow(codice_registro="R2", cod_odp="OL2", cdq="CDQ2"))
                self.db.commit()
                for ol in order:
                    self.add_cache([cached_row(ORP=ol)], ol=ol)
                result = import_legacy_cache(self.db, current_rows=[source_row(IdDocumento="200")])
                self.db.commit()
                self.assertEqual(result["audit"]["counts"].get("recoverable_historical", 0), 0)
                self.assertEqual(result["audit"]["issues"]["historical_identity_group_ambiguous"], 2)
                self.assertEqual(result["historical_imported"], 0)
                self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtWorkItem)))), 1)

    def test_distinct_lots_history_and_simultaneous_current_ols_are_kept(self):
        self.add_cache([cached_row(RifLottoAlfanum="a"), cached_row(RifLottoAlfanum="b")])
        result = import_legacy_cache(self.db, current_rows=[source_row(IdDocumento="200"),
            source_row(IdDocumento="200", ORP="OL2")])
        self.db.commit()
        self.assertEqual(result["historical_imported"], 2)
        self.assertEqual(len(list(self.db.scalars(select(QuartaTaglioDdtWorkItem)))), 4)


if __name__ == "__main__":
    unittest.main()
