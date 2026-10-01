"""Recovery plans, stale-input refusal and PostgreSQL atomicity/locking."""
import copy
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.startup import bootstrap as _registry
from app.core.database import Base
from app.modules.quarta_taglio import ddt_recovery as recovery
from app.modules.quarta_taglio.ddt_snapshot import SnapshotError, _LOCK_ID, _LOCK_NAMESPACE
from app.modules.quarta_taglio.models import (
    QuartaTaglioEsolverLink, QuartaTaglioRow, QuartaTaglioFinalCertificate,
    QuartaTaglioDdtWorkItem, QuartaTaglioDdtSyncRun,
    QuartaTaglioCertificatePdfVersion, QuartaTaglioDdtDecision,
)
from app.modules.quarta_taglio.pdf_schema import PDF_TABLES, missing_pdf_filename_columns

NOW = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
TARGET = dict(environment="alpha", public_host="certi-test.forgialluminio.it", database_id="test-only", storage_root="/test")


def source_rows():
    return [dict(IdDocumento="200", IdRigaDoc="1", RifLottoAlfanum="L", ORP="OL1", CodF3="F3",
        DDT="90-29/09/2026", RagSoc="Test", ODVCli="PO", ODVF3="CONF", QtaUmMag=12, CertificatoPresente=0)]


def seed(db):
    db.add(QuartaTaglioRow(cod_odp="OL1", codice_registro="R", cdq="CDQ"))
    db.add(QuartaTaglioEsolverLink(cod_odp="OL1", rows=[dict(id_documento="100", id_riga_doc="1",
        rif_lotto_alfanum="L", orp="OL1", cod_f3="F3", ddt="77-01/07/2026", rag_soc="Test",
        odv_cli="PO", odv_f3="CONF", qta_um_mag=5, certificato_presente=False)]))


class RecoveryPlanTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        seed(self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def plan(self, rows=None):
        return recovery.build_recovery_plan(self.db, current_rows=rows or source_rows(), target=TARGET, now=NOW)

    def test_preview_is_read_only_and_order_independent(self):
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.strip().split()[0].upper())
        event.listen(self.engine, "before_cursor_execute", capture)
        rows = source_rows() + [{**source_rows()[0], "IdDocumento": "201"}]
        first = self.plan(rows)
        second = self.plan(rows[::-1])
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertEqual(first["audit"]["counts"]["recoverable_historical"], 1)
        self.assertTrue(set(statements) <= {"SELECT", "PRAGMA"})
        self.assertFalse(self.db.dirty or self.db.new)
        recovery.validate_approved_plan(first, second, now=NOW)

    def test_target_age_and_source_changes_are_rejected(self):
        approved = self.plan()
        with self.assertRaisesRegex(SnapshotError, "expired"):
            recovery.validate_approved_plan(approved, approved, now=NOW + timedelta(hours=2))
        wrong = copy.deepcopy(approved)
        wrong["target"]["database_id"] = "different-cluster"
        with self.assertRaisesRegex(SnapshotError, "wrong_target"):
            recovery.validate_approved_plan(wrong, approved, now=NOW)
        changed = self.plan([{**source_rows()[0], "QtaUmMag": 99}])
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            recovery.validate_approved_plan(approved, changed, now=NOW)

    def test_cache_and_certificate_edits_invalidate_report(self):
        approved = self.plan()
        link = self.db.scalar(select(QuartaTaglioEsolverLink))
        link.rows = [{**link.rows[0], "qta_um_mag": 10}]
        self.db.commit()
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            recovery.validate_approved_plan(approved, self.plan(), now=NOW)
        approved = self.plan()
        self.db.add(QuartaTaglioFinalCertificate(cod_odp="OL1", draft_number="D1", status="draft"))
        self.db.commit()
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            recovery.validate_approved_plan(approved, self.plan(), now=NOW)

    def test_missing_pdf_after_preview_invalidates_report(self):
        self.db.add(QuartaTaglioFinalCertificate(cod_odp="OL1", draft_number="D1", status="pdf_final", storage_key_pdf="sample.pdf"))
        self.db.commit()
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "sample.pdf"
            file.write_bytes(b"synthetic fixture")
            with patch.object(recovery.service, "_certificate_storage_path", return_value=file):
                approved = self.plan()
                file.unlink()
                with self.assertRaisesRegex(SnapshotError, "data_changed"):
                    recovery.validate_approved_plan(approved, self.plan(), now=NOW)

    def test_alpha_guard_rejects_local_other_host_and_enabled_job(self):
        settings = SimpleNamespace(database_url="postgresql+psycopg://user:secret@postgres:5432/certi_nt",
            app_env="production", certi_public_base_url="http://certi-test.forgialluminio.it", ddt_snapshot_enabled=False)
        recovery.validate_alpha_settings(settings)
        for key, value in (("app_env", "development"), ("certi_public_base_url", "http://localhost:8080"),
                           ("database_url", "postgresql://u:p@localhost/certi_nt"), ("ddt_snapshot_enabled", True)):
            changed = copy.copy(settings)
            setattr(changed, key, value)
            with self.subTest(key=key), self.assertRaises(SnapshotError):
                recovery.validate_alpha_settings(changed)

    def test_preview_on_old_schema_requests_preparation_without_writes(self):
        with self.engine.begin() as connection:
            for table in PDF_TABLES:
                connection.execute(text(f'ALTER TABLE {table} DROP COLUMN pdf_file_name'))
        statements = []
        event.listen(self.engine, "before_cursor_execute",
                     lambda conn, cursor, sql, params, context, many: statements.append(sql.split()[0].upper()))
        with self.assertRaisesRegex(SnapshotError, "prepare_pdf_filename_schema_before_recovery"):
            self.plan()
        self.assertTrue(set(statements) <= {"SELECT", "PRAGMA"})


class RecoveryCommandTest(unittest.TestCase):
    def test_writes_need_maintenance_and_backup_before_opening_database(self):
        from scripts import recover_ddt_alpha as command
        for argv in (["--prepare-schema"], ["--prepare-schema", "--maintenance-confirmed"],
                     ["--apply", "--report", "report.json"], ["--preview"],
                     ["--prepare-schema", "--maintenance-confirmed", "--backup", "backup.sql", "--report", "r.json"]):
            with self.subTest(argv=argv), patch("sys.argv", ["recover", *argv]), \
                    patch.object(command, "create_engine") as connect, self.assertRaises(SystemExit):
                command.main()
            connect.assert_not_called()

    def test_invalid_backup_refused_before_opening_database(self):
        from scripts import recover_ddt_alpha as command
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "not-a-dump.sql"
            backup.write_text("not a backup", encoding="utf-8")
            with patch("sys.argv", ["recover", "--prepare-schema", "--maintenance-confirmed", "--backup", str(backup)]), \
                    patch.object(command, "validate_alpha_settings"), patch.object(command, "create_engine") as connect:
                self.assertEqual(command.main(), 1)
                connect.assert_not_called()


@unittest.skipUnless(os.environ.get("DDT_TEST_POSTGRES_URL"), "isolated PostgreSQL URL required")
class RecoveryPostgresTest(unittest.TestCase):
    def setUp(self):
        url = make_url(os.environ["DDT_TEST_POSTGRES_URL"])
        if url.host not in {"localhost", "127.0.0.1"} or not (url.database or "").startswith("certi_ddt_test"):
            self.fail("Only isolated local certi_ddt_test databases are allowed")
        self.root = create_engine(url, isolation_level="READ COMMITTED")
        self.schema = "ddt_recovery_" + uuid4().hex
        with self.root.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = self.root.execution_options(schema_translate_map={None: self.schema})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, autoflush=False)
        with self.factory.begin() as db:
            seed(db)

    def tearDown(self):
        with self.root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.root.dispose()

    def plan(self):
        with self.factory() as db:
            return recovery.build_recovery_plan(db, current_rows=source_rows(), target=TARGET, now=NOW)

    def apply(self, approved, fetch=None):
        with self.factory.begin() as db:
            return recovery.apply_approved_recovery(db, approved=approved, target=TARGET,
                fetch_source=fetch or (lambda db: source_rows()), now=NOW)

    def old_alpha_schema(self):
        with self.factory.begin() as db:
            certificate = QuartaTaglioFinalCertificate(cod_odp="OL1", draft_number="OLD-1", status="pdf_final",
                                                       storage_key_pdf="old.pdf", pdf_file_name="old.pdf")
            db.add(certificate)
            db.flush()
            db.add(QuartaTaglioCertificatePdfVersion(certificate_id=certificate.id, version=1,
                    status="active", storage_key_pdf="old.pdf", pdf_file_name="old.pdf"))
        with self.engine.begin() as connection:
            for model in (QuartaTaglioDdtDecision, QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem):
                model.__table__.drop(connection)
            for table in PDF_TABLES:
                connection.execute(text(f'ALTER TABLE "{self.schema}".{table} DROP COLUMN pdf_file_name'))

    def test_old_alpha_prepare_preview_apply_preserves_existing_data(self):
        self.old_alpha_schema()
        with self.assertRaisesRegex(SnapshotError, "prepare_pdf_filename_schema_before_recovery"):
            self.plan()
        with self.factory.begin() as db:
            result = recovery.prepare_recovery_schema(db)
            self.assertEqual(result["added_columns"], [t + ".pdf_file_name" for t in PDF_TABLES])
        with self.factory.begin() as db:
            self.assertEqual(recovery.prepare_recovery_schema(db)["added_columns"], [])
            self.assertFalse(recovery.table_exists(db, QuartaTaglioDdtWorkItem))
            self.assertEqual(db.scalar(select(QuartaTaglioEsolverLink)).rows[0]["qta_um_mag"], 5)
            cert = db.scalar(select(QuartaTaglioFinalCertificate))
            self.assertEqual((cert.draft_number, cert.status, cert.storage_key_pdf, cert.pdf_file_name),
                             ("OLD-1", "pdf_final", "old.pdf", None))
            version = db.scalar(select(QuartaTaglioCertificatePdfVersion))
            self.assertEqual((version.version, version.status, version.storage_key_pdf), (1, "active", "old.pdf"))
        approved = self.plan()
        self.assertEqual(self.apply(approved)["historical_imported"], 1)
        with self.factory.begin() as db:
            cert = db.scalar(select(QuartaTaglioFinalCertificate))
            cert.pdf_file_name = "custom-name.pdf"
        with self.factory.begin() as db:
            self.assertEqual(recovery.prepare_recovery_schema(db)["added_columns"], [])
            self.assertEqual(db.scalar(select(QuartaTaglioFinalCertificate)).pdf_file_name, "custom-name.pdf")
            self.assertEqual(len(list(db.scalars(select(QuartaTaglioDdtWorkItem)))), 2)

    def test_preparation_rolls_back_both_columns_on_failure(self):
        self.old_alpha_schema()
        with self.assertRaisesRegex(RuntimeError, "synthetic"):
            with self.factory.begin() as db:
                recovery.prepare_recovery_schema(db)
                raise RuntimeError("synthetic failure")
        with self.engine.connect() as connection:
            self.assertEqual(missing_pdf_filename_columns(connection), list(PDF_TABLES))

    def test_preparation_refuses_concurrent_writer(self):
        self.old_alpha_schema()
        with self.factory.begin() as writer:
            writer.execute(text(f'UPDATE "{self.schema}".quarta_taglio_esolver_links SET status=\'ok\''))
            with self.assertRaisesRegex(SnapshotError, "recovery_inputs_busy"):
                with self.factory.begin() as db:
                    recovery.prepare_recovery_schema(db)
        with self.engine.connect() as connection:
            self.assertEqual(missing_pdf_filename_columns(connection), list(PDF_TABLES))

    def test_apply_repeat_with_new_report_preserves_cache_and_certificates(self):
        approved = self.plan()
        self.assertEqual(self.apply(approved)["historical_imported"], 1)
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            self.apply(approved)
        repeated = self.apply(self.plan())
        self.assertEqual(repeated["historical_imported"], 0)
        self.assertEqual(repeated["historical_already_present"], 1)
        with self.factory() as db:
            self.assertEqual(len(list(db.scalars(select(QuartaTaglioDdtWorkItem)))), 2)
            self.assertEqual(db.scalar(select(QuartaTaglioEsolverLink)).rows[0]["qta_um_mag"], 5)
            self.assertFalse(list(db.scalars(select(QuartaTaglioFinalCertificate))))

    def test_stale_cache_and_empty_or_failed_source_leave_database_untouched(self):
        approved = self.plan()
        def failed_source(db):
            raise SnapshotError("synthetic_source_unavailable")
        with self.assertRaisesRegex(SnapshotError, "source_unavailable"):
            self.apply(approved, failed_source)
        for fetch in (lambda db: [], lambda db: [{**source_rows()[0], "QtaUmMag": 99}]):
            with self.assertRaises(SnapshotError):
                self.apply(approved, fetch)
        with self.factory.begin() as db:
            link = db.scalar(select(QuartaTaglioEsolverLink))
            link.rows = [{**link.rows[0], "qta_um_mag": 99}]
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            self.apply(approved)
        with self.factory() as db:
            self.assertFalse(list(db.scalars(select(QuartaTaglioDdtWorkItem))))
            self.assertFalse(list(db.scalars(select(QuartaTaglioDdtSyncRun))))

    def test_failure_after_writes_rolls_back_everything(self):
        approved = self.plan()
        original = recovery.import_legacy_cache
        def fail(db, **kwargs):
            original(db, **kwargs)
            raise RuntimeError("synthetic failure")
        with patch.object(recovery, "import_legacy_cache", side_effect=fail), self.assertRaises(RuntimeError):
            self.apply(approved)
        with self.factory() as db:
            self.assertFalse(list(db.scalars(select(QuartaTaglioDdtWorkItem))))
            self.assertFalse(list(db.scalars(select(QuartaTaglioDdtSyncRun))))

    def test_snapshot_lock_refuses_import_before_source_is_read(self):
        approved = self.plan()
        with self.root.connect() as connection, connection.begin():
            connection.execute(text("SELECT pg_advisory_xact_lock(:n,:k)"), {"n": _LOCK_NAMESPACE, "k": _LOCK_ID})
            with self.assertRaisesRegex(SnapshotError, "snapshot_busy"):
                self.apply(approved, lambda db: self.fail("source must not be read while busy"))

    def test_first_install_ddl_is_transactional(self):
        # Reproduce Alpha before first deployment: all queue tables are absent.
        from app.modules.quarta_taglio.models import QuartaTaglioDdtDecision
        with self.engine.begin() as connection:
            for model in (QuartaTaglioDdtDecision, QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem):
                model.__table__.drop(connection)
        approved = self.plan()
        original = recovery.import_legacy_cache
        def fail(db, **kwargs):
            original(db, **kwargs)
            raise RuntimeError("synthetic failure after DDL")
        with patch.object(recovery, "import_legacy_cache", side_effect=fail), self.assertRaises(RuntimeError):
            self.apply(approved)
        with self.factory() as db:
            for model in (QuartaTaglioDdtDecision, QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem):
                self.assertFalse(recovery.table_exists(db, model))
        self.assertEqual(self.apply(approved)["historical_imported"], 1)

    def test_cache_writer_prevents_recovery(self):
        approved = self.plan()
        with self.factory.begin() as writer:
            writer.execute(text(f'UPDATE "{self.schema}".quarta_taglio_esolver_links SET status=\'ok\''))
            with self.assertRaisesRegex(SnapshotError, "recovery_inputs_busy"):
                self.apply(approved, lambda db: self.fail("source must not be read while writer active"))

    def test_manual_decisions_share_snapshot_lock_and_invalidate_recovery_plan(self):
        from fastapi import HTTPException
        from app.modules.quarta_taglio.ddt_decisions import change_decision, source_revision
        from app.modules.quarta_taglio.ddt_schemas import DdtDecisionRequest
        self.apply(self.plan())
        approved = self.plan()
        user = SimpleNamespace(id=None, name="Test Qualità", role="admin", department=SimpleNamespace(name="Qualità"))
        with self.factory() as db:
            item = db.scalar(select(QuartaTaglioDdtWorkItem))
            payload = DdtDecisionRequest(action="exclude", reason="Test", expected_decision_id=0,
                                         source_revision=source_revision(item))
            with self.root.connect() as connection, connection.begin():
                connection.execute(text("SELECT pg_advisory_xact_lock(:n,:k)"), {"n": _LOCK_NAMESPACE, "k": _LOCK_ID})
                with self.assertRaises(HTTPException) as caught:
                    change_decision(db, item.id, payload, user)
                self.assertEqual(caught.exception.status_code, 409)
            change_decision(db, item.id, payload, user)
        with self.assertRaisesRegex(SnapshotError, "data_changed"):
            self.apply(approved)

    def test_postgres_decision_then_snapshot_change_reopens_in_same_transaction(self):
        from app.modules.quarta_taglio.ddt_decisions import change_decision, source_revision, latest_decisions
        from app.modules.quarta_taglio.ddt_schemas import DdtDecisionRequest
        from app.modules.quarta_taglio.ddt_snapshot import _apply_snapshot
        from app.modules.quarta_taglio.ddt_queue import read_ddt_queue
        self.apply(self.plan())
        user = SimpleNamespace(id=None, name="Test Qualità", role="admin", department=SimpleNamespace(name="Qualità"))
        with self.factory() as db:
            item = db.scalar(select(QuartaTaglioDdtWorkItem).where(QuartaTaglioDdtWorkItem.source_present.is_(True)))
            item_id = item.id
            change_decision(db, item_id, DdtDecisionRequest(action="exclude", reason="Test", expected_decision_id=0,
                            source_revision=source_revision(item)), user)
        with self.factory.begin() as db:
            _apply_snapshot(db, source_rows(), now=NOW)
            self.assertEqual(read_ddt_queue(db, scope="excluded").total_items, 1)
        with self.factory.begin() as db:
            _apply_snapshot(db, [{**source_rows()[0], "QtaUmMag": 987}], now=NOW)
        with self.factory() as db:
            self.assertEqual(latest_decisions(db, [item_id])[item_id].action, "review")
            self.assertEqual(read_ddt_queue(db, scope="excluded").total_items, 0)
