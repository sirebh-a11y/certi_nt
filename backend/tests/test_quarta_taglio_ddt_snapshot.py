"""Offline snapshot contract tests: no company database/network connections."""
import unittest
import asyncio
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.departments.models import Department  # noqa: F401
from app.core.integrations.models import ExternalConnection
from app.modules.quarta_taglio import ddt_snapshot as snapshot
from app.modules.quarta_taglio.models import (
    QuartaTaglioDdtSyncRun, QuartaTaglioDdtWorkItem, QuartaTaglioEsolverLink,
    QuartaTaglioFinalCertificate,
)


def row(**changes):
    values = dict(IdDocumento=100, IdRigaDoc=1, RifLottoAlfanum="lot-a", ORP="OL1",
                  CodF3="001230", DDT="77-01/01/2026", RagSoc="Cliente",
                  ODVCli="PO", ODVF3="ORD", QtaUmMag=Decimal("123.4567"), CertificatoPresente=0)
    values.update(changes)
    return values


class DdtSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)

    def tearDown(self):
        self.engine.dispose()

    def sync(self, rows=None, error=None):
        with patch.object(snapshot, "_fetch_complete_snapshot", return_value=rows, side_effect=error):
            return snapshot.sync_ddt_snapshot(session_factory=self.factory)

    def items(self):
        with self.factory() as db:
            return list(db.scalars(select(QuartaTaglioDdtWorkItem).order_by(QuartaTaglioDdtWorkItem.id)))

    def test_key_retains_case_zeroes_and_prevents_separator_collisions(self):
        key = snapshot.source_key
        self.assertEqual(key(100, 1, " OL1 ", "lot-a"), key("100", "1", "OL1", "lot-a"))
        self.assertEqual(key(100, 1, None, None), key(100, 1, " ", ""))
        self.assertNotEqual(key(100, 1, "OL1", "lot-a"), key(100, 1, "OL1", "LOT-A"))
        self.assertNotEqual(key("01", 1, "OL1", None), key("1", 1, "OL1", None))
        self.assertNotEqual(key("a|b", "c", None, None), key("a", "b|c", None, None))

    def test_repeated_snapshot_updates_one_item_preserving_first_seen(self):
        self.assertEqual(self.sync([row()]).inserted, 1)
        first = self.items()[0]
        changed = row(CodF3="001240", QtaUmMag=Decimal("9.1234"), DDT="78-02/01/2026", ODVCli="PO2")
        result = self.sync([changed])
        item = self.items()[0]
        self.assertEqual((result.inserted, result.updated, len(self.items())), (0, 1, 1))
        self.assertEqual(item.id, first.id)
        self.assertEqual(item.first_seen_at, first.first_seen_at)
        self.assertEqual(item.quantita, Decimal("9.1234"))
        self.assertEqual(item.cod_f3, "001240")
        self.assertNotEqual(item.certification_unit_key, first.certification_unit_key)
        self.assertEqual(item.certification_unit_key, "OL1|001240|78-02/01/2026|100|1|lot-a|PO2|ORD")

    def test_corrected_date_clears_only_date_warning_not_identity_conflict(self):
        self.sync([row(DDT="date unreadable")])
        self.assertEqual(self.items()[0].source_review_reason, "ddt_date_unrecognized")
        self.sync([row()])
        self.assertIsNone(self.items()[0].source_review_reason)
        with self.factory() as db:
            db.scalar(select(QuartaTaglioDdtWorkItem)).source_review_reason = "source_identity_changed"
            db.commit()
        self.sync([row()])
        self.assertEqual(self.items()[0].source_review_reason, "source_identity_changed")

    def test_every_share_and_missing_ol_is_retained(self):
        rows = [row(), row(ORP="OL2"), row(IdDocumento=101), row(IdRigaDoc=2),
                row(RifLottoAlfanum="lot-b"), row(ORP=None), row(ORP=None, RifLottoAlfanum="lot-c")]
        result = self.sync(rows)
        self.assertEqual(result.inserted, 7)
        self.assertEqual(len(self.items()), 7)
        self.assertEqual(sum(i.cod_odp is None for i in self.items()), 2)
        self.assertTrue(all(i.certification_unit_key is None for i in self.items() if i.cod_odp is None))

    def test_unambiguous_missing_ol_promotion_preserves_row(self):
        self.sync([row(ORP=None)])
        first = self.items()[0]
        result = self.sync([row()])
        current = self.items()[0]
        self.assertEqual((result.reconciled, result.inserted, result.disappeared), (1, 0, 0))
        self.assertEqual(len(self.items()), 1)
        self.assertEqual(current.id, first.id)
        self.assertEqual(current.first_seen_at, first.first_seen_at)
        self.assertEqual(current.cod_odp, "OL1")

    def test_snapshot_has_no_page_size_limit(self):
        result = self.sync([row(IdDocumento=100 + i) for i in range(530)])
        self.assertEqual(result.source_rows, 530)
        self.assertEqual(len(self.items()), 530)

    def test_missing_connection_does_not_replace_last_success(self):
        self.sync([row()])
        result = snapshot.sync_ddt_snapshot(session_factory=self.factory)
        self.assertEqual(result.error_code, "connection_disabled")
        self.assertTrue(self.items()[0].source_present)
        with self.factory() as db:
            latest, successful = snapshot.last_snapshot_runs(db)
            self.assertEqual(latest.status, "error")
            self.assertEqual(successful.id, 1)

    def test_split_missing_ol_is_not_arbitrarily_promoted(self):
        self.sync([row(ORP=None)])
        result = self.sync([row(ORP="OL1"), row(ORP="OL2")])
        self.assertEqual((result.reconciled, result.inserted), (0, 2))
        items = self.items()
        self.assertEqual(len(items), 3)
        self.assertTrue(all(i.source_review_reason == "source_identity_changed" for i in items))
        self.assertFalse(items[0].source_present)

    def test_missing_and_linked_shares_in_same_snapshot_are_not_merged(self):
        self.sync([row(ORP=None)])
        result = self.sync([row(ORP=None), row()])
        self.assertEqual(result.reconciled, 0)
        self.assertEqual(len(self.items()), 2)
        self.assertTrue(all(i.source_present for i in self.items()))

    def test_changed_lot_is_retained_for_review(self):
        self.sync([row()])
        self.sync([row(RifLottoAlfanum="different-lot")])
        items = self.items()
        self.assertEqual(len(items), 2)
        self.assertFalse(items[0].source_present)
        self.assertTrue(all(i.source_review_reason for i in items))

    def test_old_item_disappears_from_source_but_is_not_deleted(self):
        self.sync([row()])
        with self.factory.begin() as db:
            db.get(QuartaTaglioDdtWorkItem, 1).first_seen_at = datetime.now(timezone.utc) - timedelta(days=120)
        self.sync([row(IdDocumento=101)])
        old = self.items()[0]
        self.assertFalse(old.source_present)
        self.assertIsNotNone(old.source_disappeared_at)
        self.assertEqual(old.ddt_raw, "77-01/01/2026")
        self.sync([row(IdDocumento=101)])
        self.assertEqual(self.items()[0].source_disappeared_at, old.source_disappeared_at)
        self.sync([row(), row(IdDocumento=101)])
        self.assertTrue(self.items()[0].source_present)
        self.assertIsNone(self.items()[0].source_disappeared_at)
        self.assertEqual(self.items()[0].first_seen_at, old.first_seen_at)

    def test_empty_snapshot_after_data_preserves_flags_and_last_success(self):
        self.sync([row()])
        previous = self.items()[0]
        result = self.sync([])
        self.assertEqual((result.status, result.error_code), ("error", "empty_source_requires_review"))
        self.assertEqual(len(self.items()), 1)
        self.assertTrue(self.items()[0].source_present)
        self.assertEqual(self.items()[0].last_seen_at, previous.last_seen_at)
        with self.factory() as db:
            latest, success = snapshot.last_snapshot_runs(db)
            self.assertEqual((latest.status, success.id), ("error", 1))
        self.assertEqual(self.sync([row()]).status, "success")

    def test_initial_empty_source_without_history_can_succeed(self):
        self.assertEqual(self.sync([]).status, "success")
        self.assertEqual(self.items(), [])

    def test_source_failure_retains_snapshot_and_last_success(self):
        self.sync([row()])
        first = self.items()[0]
        result = self.sync(error=snapshot.SnapshotError("source_read_failed"))
        self.assertEqual(result.error_code, "source_read_failed")
        current = self.items()[0]
        self.assertEqual(current.last_seen_at, first.last_seen_at)
        self.assertTrue(current.source_present)
        with self.factory() as db:
            latest, success = snapshot.last_snapshot_runs(db)
            self.assertEqual((latest.status, success.status), ("error", "success"))
            self.assertEqual(success.id, 1)
        self.assertEqual(self.sync([row(IdDocumento=101)]).status, "success")

    def test_invalid_batch_is_rejected_atomically(self):
        self.sync([row()])
        first = self.items()[0]
        invalids = [row(IdDocumento=None), {"IdDocumento": 1}, row(QtaUmMag="NaN"),
                    row(QtaUmMag="not-a-number"), row(CertificatoPresente=99)]
        for invalid in invalids:
            with self.subTest(invalid=invalid):
                result = self.sync([row(IdDocumento=101), invalid])
                self.assertEqual(result.status, "error")
                self.assertEqual(len(self.items()), 1)
                self.assertEqual(self.items()[0].last_seen_at, first.last_seen_at)
                self.assertTrue(self.items()[0].source_present)

    def test_duplicate_source_identity_is_not_summed_or_overwritten(self):
        self.sync([row()])
        for other in (row(), row(QtaUmMag=999)):
            result = self.sync([row(), other])
            self.assertEqual(result.error_code, "duplicate_source_identity")
            self.assertEqual(self.items()[0].quantita, Decimal("123.4567"))

    def test_mid_write_failure_rolls_back_changes_and_logs_no_secrets(self):
        self.sync([row()])
        original = snapshot._apply_snapshot

        def fail_after_flush(db, raw_rows, *, now):
            original(db, raw_rows, now=now)
            raise RuntimeError("secret-password-and-host")

        with patch.object(snapshot, "_apply_snapshot", side_effect=fail_after_flush):
            result = self.sync([row(IdDocumento=101)])
        self.assertEqual(result.error_code, "snapshot_write_failed")
        self.assertEqual(len(self.items()), 1)
        self.assertTrue(self.items()[0].source_present)
        with self.factory() as db:
            latest, success = snapshot.last_snapshot_runs(db)
            self.assertEqual(latest.error_code, "snapshot_write_failed")
            self.assertEqual(success.id, 1)
        self.assertNotIn("secret-password", str(snapshot.log_service.list_entries()))

    def test_busy_attempt_does_not_read_source_or_change_history(self):
        snapshot._PROCESS_LOCK.acquire()
        try:
            with patch.object(snapshot, "_fetch_complete_snapshot") as fetch:
                self.assertEqual(snapshot.sync_ddt_snapshot(session_factory=self.factory).status, "busy")
                fetch.assert_not_called()
        finally:
            snapshot._PROCESS_LOCK.release()
        with self.factory() as db:
            self.assertEqual(list(db.scalars(select(QuartaTaglioDdtSyncRun))), [])

    def test_unrecognized_date_keeps_raw_and_requires_review(self):
        self.sync([row(DDT="77-31/02/2026")])
        item = self.items()[0]
        self.assertEqual(item.ddt_raw, "77-31/02/2026")
        self.assertIsNone(item.ddt_date)
        self.assertEqual(item.source_review_reason, "ddt_date_unrecognized")

    def test_snapshot_does_not_mutate_certificate_or_old_cache(self):
        with self.factory.begin() as db:
            db.add(QuartaTaglioEsolverLink(cod_odp="OL1", rows=[{"ddt": "old"}], status="ok"))
            db.add(QuartaTaglioFinalCertificate(cod_odp="OL1", status="pdf_final", draft_number="TEST",
                                              unit_key="old", storage_key_pdf="test.pdf"))
        self.sync([row(CertificatoPresente=1)])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(QuartaTaglioEsolverLink)).rows, [{"ddt": "old"}])
            cert = db.scalar(select(QuartaTaglioFinalCertificate))
            self.assertEqual((cert.status, cert.unit_key, cert.storage_key_pdf), ("pdf_final", "old", "test.pdf"))

    def test_bootstrap_creates_tables_idempotently(self):
        Base.metadata.create_all(self.engine)
        self.sync([row()])
        Base.metadata.create_all(self.engine)
        self.assertEqual(len(self.items()), 1)

    def test_reader_uses_configured_view_without_date_or_ol_filter(self):
        with self.factory.begin() as db:
            db.add(ExternalConnection(code="esolver", label="test", server_host="fake-host", username="fake",
                                      database_name="fake-db", password_encrypted="fake-encrypted",
                                      schema_name="custom", object_settings={"righe_ddt_view": "TestDDT"}))
        driver = MagicMock()
        cursor = driver.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [row()]
        with self.factory() as db, patch.dict("sys.modules", {"pymssql": driver}), \
                patch.object(snapshot, "decrypt_secret", return_value="never-print-password"):
            self.assertEqual(snapshot._fetch_complete_snapshot(db), [row()])
        query = cursor.execute.call_args.args[0]
        self.assertIn("[custom].[TestDDT]", query)
        self.assertNotIn("where", query.lower())
        self.assertNotIn("cast(", query.lower())

    def test_reader_failure_is_safe_and_partial_fetch_is_not_applied(self):
        with self.factory.begin() as db:
            db.add(ExternalConnection(code="esolver", label="test", server_host="fake-host", username="fake",
                                      database_name="fake-db", password_encrypted="fake-encrypted"))
        self.sync([row()])
        driver = MagicMock()
        cursor = driver.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value

        def partial():
            yield row(IdDocumento=101)
            raise RuntimeError("SECRET-DRIVER-TEXT")

        cursor.fetchall.return_value = partial()
        with patch.dict("sys.modules", {"pymssql": driver}), \
                patch.object(snapshot, "decrypt_secret", return_value="password"):
            result = snapshot.sync_ddt_snapshot(session_factory=self.factory)
        self.assertEqual(result.error_code, "source_read_failed")
        self.assertEqual(len(self.items()), 1)
        self.assertTrue(self.items()[0].source_present)
        self.assertNotIn("SECRET-DRIVER", str(snapshot.log_service.list_entries()))


@unittest.skipUnless(os.environ.get("DDT_TEST_POSTGRES_URL"), "isolated PostgreSQL test URL not supplied")
class DdtSnapshotPostgresTest(unittest.TestCase):
    def setUp(self):
        url = make_url(os.environ["DDT_TEST_POSTGRES_URL"])
        if url.host not in ("127.0.0.1", "localhost") or not (url.database or "").startswith("certi_ddt_test"):
            self.fail("Only a dedicated local certi_ddt_test database is permitted")
        self.root_engine = create_engine(url)
        self.schema = "ddt_test_" + uuid4().hex
        with self.root_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = self.root_engine.execution_options(schema_translate_map={None: self.schema})
        for table in (QuartaTaglioDdtWorkItem.__table__, QuartaTaglioDdtSyncRun.__table__):
            table.create(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)

    def tearDown(self):
        with self.root_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.root_engine.dispose()

    def test_other_worker_lock_prevents_read_and_write_then_releases(self):
        with self.root_engine.connect() as connection, connection.begin():
            connection.execute(text("SELECT pg_advisory_xact_lock(:n, :k)"),
                               {"n": snapshot._LOCK_NAMESPACE, "k": snapshot._LOCK_ID})
            with patch.object(snapshot, "_fetch_complete_snapshot") as fetch:
                result = snapshot.sync_ddt_snapshot(session_factory=self.factory)
                self.assertEqual(result.status, "busy")
                fetch.assert_not_called()
        with patch.object(snapshot, "_fetch_complete_snapshot", return_value=[row()]):
            self.assertEqual(snapshot.sync_ddt_snapshot(session_factory=self.factory).status, "success")
            self.assertEqual(snapshot.sync_ddt_snapshot(session_factory=self.factory).inserted, 0)
        with self.factory() as db:
            items = list(db.scalars(select(QuartaTaglioDdtWorkItem)))
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].quantita, Decimal("123.4567"))
            self.assertIsNotNone(items[0].first_seen_at.tzinfo)

    def test_postgres_constraint_failure_rolls_back_snapshot_but_records_failure(self):
        with patch.object(snapshot, "_fetch_complete_snapshot", return_value=[row()]):
            snapshot.sync_ddt_snapshot(session_factory=self.factory)
        original = snapshot._apply_snapshot

        def invalid_write(db, rows, *, now):
            result = original(db, rows, now=now)
            item = db.scalar(select(QuartaTaglioDdtWorkItem).where(QuartaTaglioDdtWorkItem.source_present.is_(True)))
            item.id_documento = None
            db.flush()  # Real PostgreSQL NOT NULL violation inside the savepoint.
            return result

        with patch.object(snapshot, "_fetch_complete_snapshot", return_value=[row(IdDocumento=101)]), \
                patch.object(snapshot, "_apply_snapshot", side_effect=invalid_write):
            result = snapshot.sync_ddt_snapshot(session_factory=self.factory)
        self.assertEqual(result.error_code, "snapshot_write_failed")
        with self.factory() as db:
            items = list(db.scalars(select(QuartaTaglioDdtWorkItem)))
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].id_documento, "100")
            self.assertTrue(items[0].source_present)
            latest, successful = snapshot.last_snapshot_runs(db)
            self.assertEqual((latest.status, successful.status), ("error", "success"))


class DdtSnapshotSchedulerTest(unittest.TestCase):
    def test_snapshot_is_opt_in_and_quarta_continues_after_failure(self):
        from app.modules.quarta_taglio import scheduler

        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                with patch.object(scheduler, "settings") as settings, \
                        patch.object(scheduler.asyncio, "sleep", side_effect=[None, asyncio.CancelledError]), \
                        patch.object(scheduler, "sync_ddt_snapshot", side_effect=RuntimeError("private error")) as sync, \
                        patch.object(scheduler, "SessionLocal"), \
                        patch.object(scheduler, "sync_and_list_quarta_taglio") as quarta:
                    settings.ddt_snapshot_enabled = enabled
                    with self.assertRaises(asyncio.CancelledError):
                        asyncio.run(scheduler.quarta_taglio_periodic_sync_loop())
                    self.assertEqual(sync.call_count, int(enabled))
                    quarta.assert_called_once()


if __name__ == "__main__":
    unittest.main()
