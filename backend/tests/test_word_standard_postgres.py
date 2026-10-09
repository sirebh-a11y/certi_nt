"""Only the dedicated localhost certi_ddt_test database accepted by the fixture."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.modules.quarta_taglio import word_standard as ws, service
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as C, QuartaTaglioStandardSelection as Selection
from app.modules.standards.models import NormativeStandard as S
import test_quarta_taglio_ddt_history as history


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'), 'isolated PostgreSQL URL required')
class WordStandardPostgresTest(unittest.TestCase):
    setUp = history.DdtHistoryPostgresTest.setUp
    tearDown = history.DdtHistoryPostgresTest.tearDown

    def test_elongation_additive_schema_legacy_defaults_without_changing_rows(self):
        from app.modules.standards.elongation import ensure_schema
        self.seed()
        with self.engine.begin() as conn:
            table = f'"{self.schema}".normative_standards'
            conn.execute(text(f'ALTER TABLE {table} DROP COLUMN elongation_basis'))
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN regola_tipo VARCHAR(64) NOT NULL DEFAULT 'variante'"))
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN regola_tipo DROP DEFAULT'))
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT FALSE'))
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN is_active DROP DEFAULT'))
            assert ensure_schema(conn)
            assert not ensure_schema(conn)
            old = conn.execute(text(f'SELECT regola_tipo,is_active FROM {table}')).one()
            assert old == ('variante', False)
        with self.factory.begin() as db:
            std = S(code='new', lega_base='7003', lega_designazione='7003', elongation_basis='A50mm')
            db.add(std); db.flush()
            assert std.id is not None

    def seed(self):
        with self.factory.begin() as db:
            standard = S(code='TEST', lega_base='6082', lega_designazione='6082', trattamento_termico='T6')
            db.add(standard); db.flush()
            sid = standard.id
            db.add(Selection(cod_odp='OL1', standard_id=sid))
            db.add(C(cod_odp='OL1', draft_number='TEST', storage_key_docx='unchanged.docx'))
        return sid

    def test_old_schema_additive_migration_idempotent_baseline_preserves_dates(self):
        self.seed()
        with self.factory() as db:
            before = db.scalar(select(C.updated_at))
        with self.engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE "{self.schema}".quarta_taglio_final_certificates DROP COLUMN word_standard_snapshot'))
            self.assertTrue(ws.ensure_schema(conn))
            self.assertFalse(ws.ensure_schema(conn))
            with Session(bind=conn) as db:
                self.assertEqual(ws.baseline_legacy(db), 1)
                db.flush()
        with self.factory() as db:
            c = db.scalar(select(C))
            self.assertEqual(c.word_standard_snapshot['origin'], 'legacy_baseline')
            self.assertEqual(c.updated_at, before)
            self.assertEqual(ws.baseline_legacy(db), 0)

    def test_publication_check_locks_standard_against_limit_editor(self):
        sid = self.seed()
        attempted = Event()
        def edit():
            with self.factory.begin() as db:
                attempted.set()
                db.execute(select(S.id).where(S.id == sid).with_for_update()).all()
                std = db.get(S, sid); std.trattamento_termico = 'T73'
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.factory() as db:
                saved = ws.snapshot(db, 'OL1')
                ws.require_unchanged(db, 'OL1', saved)
                future = pool.submit(edit)
                self.assertTrue(attempted.wait(3))
                try:
                    with self.assertRaises(TimeoutError): future.result(timeout=0.2)
                finally: db.rollback()
            future.result(timeout=5)
        with self.factory() as db:
            with self.assertRaises(Exception) as exc:
                ws.require_unchanged(db, 'OL1', saved)
            self.assertEqual(exc.exception.status_code, 409)

    def test_migration_and_baseline_rollback_together_on_failure(self):
        self.seed()
        with self.engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE "{self.schema}".quarta_taglio_final_certificates DROP COLUMN word_standard_snapshot'))
        with self.assertRaisesRegex(RuntimeError, 'simulated preparation failure'):
            with self.engine.begin() as conn:
                self.assertTrue(ws.ensure_schema(conn))
                with Session(bind=conn) as db:
                    self.assertEqual(ws.baseline_legacy(db), 1)
                    db.flush()
                raise RuntimeError('simulated preparation failure')
        with self.engine.begin() as conn:
            # If ALTER rolled back, it must still be necessary on retry.
            self.assertTrue(ws.ensure_schema(conn))
            with Session(bind=conn) as db:
                self.assertEqual(ws.baseline_legacy(db), 1)
                db.flush()

    def test_selection_change_uses_same_ol_lock_as_publication(self):
        self.seed()
        attempted = Event()
        def acquire():
            with self.factory.begin() as db:
                attempted.set()
                service._lock_certificate_register_for_ol(db, cod_odp='OL1')
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.factory() as db:
                service._lock_certificate_register_for_ol(db, cod_odp='OL1')
                future = pool.submit(acquire)
                self.assertTrue(attempted.wait(3))
                try:
                    with self.assertRaises(TimeoutError): future.result(timeout=0.2)
                finally: db.rollback()
            future.result(timeout=5)
