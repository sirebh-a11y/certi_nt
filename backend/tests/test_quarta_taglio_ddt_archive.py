"""Disposable DBs only: production boundary, historic selection and restoration."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.quarta_taglio import models as m, service
from app.modules.quarta_taglio.ddt_archive import archived_ids, invalidate_archives, restore_document
from app.modules.quarta_taglio.ddt_archive_plan import build_plan, apply_plan
from app.modules.quarta_taglio.ddt_context import resolve_saved_ddt, saved_ddt_row
from app.modules.quarta_taglio.ddt_decisions import source_revision
from app.modules.quarta_taglio.ddt_history_links import operational_links
from app.modules.quarta_taglio.ddt_word_reuse import plan_item
from test_quarta_taglio_ddt_queue import DdtQueueFixture
import os
import unittest
from tempfile import TemporaryDirectory
import test_quarta_taglio_ddt_history as history


CUTOFF = date(2026, 10, 1)
TARGET = {'environment': 'test', 'database_id': 'disposable'}


class DdtArchiveTest(DdtQueueFixture):
    def archive(self):
        report = build_plan(self.db, target=TARGET, cutoff=CUTOFF)
        ids = apply_plan(self.db, approved=report, target=TARGET, cutoff=CUTOFF, actor='Test')
        self.db.commit()
        return ids

    def test_boundary_and_no_rolling_deletion(self):
        old = self.item()
        recent = self.item(IdDocumento='2', DDT='2-01/10/2026')
        self.assertEqual(self.archive(), [old.id])
        self.assertEqual(self.read().active, 1)
        self.assertEqual(self.read(scope='archived').items[0].id, old.id)
        self.assertEqual(self.db.query(m.QuartaTaglioDdtWorkItem).count(), 2)
        self.assertEqual(plan_item(self.db, old)['reason'], 'archived_before_start')
        self.assertNotEqual(plan_item(self.db, recent)['reason'], 'archived_before_start')
        self.assertEqual(self.archive(), [])

    def test_empty_certificate_and_sibling_document_protected(self):
        first = self.item()
        self.cert(first, word=False)
        other = self.item(ORP='OL2', IdRigaDoc='2')
        self.assertEqual(self.archive(), [])
        self.assertEqual(self.read().active, 2)

    def test_partial_incoming_protects_whole_document(self):
        self.item()
        self.item(ORP='OL2', IdRigaDoc='2')
        self.material(complete=False, evaluation=None)
        self.assertEqual(self.archive(), [])

    def test_ai_still_processing_is_protected(self):
        self.item()
        self.material(complete=False, processing='in_lavorazione')
        self.assertEqual(self.archive(), [])

    def test_blank_date_never_archived(self):
        self.item(DDT='non leggibile')
        self.assertEqual(self.archive(), [])

    def test_manual_decision_protected(self):
        item = self.item()
        self.db.add(m.QuartaTaglioDdtDecision(work_item_id=item.id, action='restore', reason='test',
            actor_name='Test', source_facts={}, created_at=datetime.now(timezone.utc)))
        self.db.commit()
        self.assertEqual(self.archive(), [])

    def test_source_change_reopens_and_reverting_does_not_rearchive(self):
        item = self.item()
        self.archive()
        old = item.quantita
        item.quantita = 9
        self.db.flush()
        self.assertEqual(archived_ids(self.db, [item]), set())
        invalidate_archives(self.db, [item], datetime.now(timezone.utc))
        self.db.commit()
        item.quantita = old
        self.db.commit()
        self.assertEqual(archived_ids(self.db, [item]), set())
        self.assertEqual(self.archive(), [])

    def test_new_work_reopens_without_waiting_for_snapshot(self):
        item = self.item()
        self.archive()
        self.material(complete=False)
        self.assertEqual(self.read().active, 1)
        self.assertEqual(archived_ids(self.db, [item]), set())

    def test_new_old_dated_arrival_not_automatically_archived(self):
        self.item()
        self.archive()
        late = self.item(IdDocumento='2', DDT='2-01/07/2026')
        self.assertEqual(self.read().items[0].id, late.id)

    def test_snapshot_does_not_resurrect_unchanged_archive(self):
        from app.modules.quarta_taglio.ddt_snapshot import _apply_snapshot
        item = self.item()
        self.archive()
        raw = dict(IdDocumento='100', IdRigaDoc='1', RifLottoAlfanum='lot-a', ORP='OL1', CodF3='001230',
            DDT='77-01/09/2026', RagSoc='Cliente A', ODVCli='PO', ODVF3='ORD', QtaUmMag=42, CertificatoPresente=0)
        _apply_snapshot(self.db, [raw], now=datetime.now(timezone.utc))
        self.db.commit()
        self.assertEqual(archived_ids(self.db, [item]), {item.id})
        raw['QtaUmMag'] = 43
        _apply_snapshot(self.db, [raw], now=datetime.now(timezone.utc))
        self.db.commit()
        self.assertEqual(self.read().active, 1)

    def test_revision_and_permissions_on_restore(self):
        first = self.item()
        second = self.item(IdRigaDoc='2')
        self.archive()
        row = self.read(scope='archived').items[0]
        actor = SimpleNamespace(id=None, name='Test')
        payload = SimpleNamespace(source_revision=source_revision(first), reason='Riprendo lavoro',
                                  expected_decision_id=row.latest_archive.id)
        with patch('app.modules.quarta_taglio.ddt_archive.require_quality_decider', side_effect=HTTPException(403)):
            with self.assertRaises(HTTPException):
                restore_document(self.db, first.id, payload, actor)
        event = self.db.scalar(select(m.QuartaTaglioDdtArchiveEvent).where(m.QuartaTaglioDdtArchiveEvent.work_item_id == first.id))
        payload.expected_decision_id = event.id
        with patch('app.modules.quarta_taglio.ddt_archive.require_quality_decider'):
            self.assertEqual(restore_document(self.db, first.id, payload, actor)['restored'], 2)
        self.assertEqual(self.read().active, 2)
        self.assertEqual(self.archive(), [])

    def test_direct_detail_of_archived_is_blocked(self):
        item = self.item()
        self.archive()
        with self.assertRaises(HTTPException) as error:
            resolve_saved_ddt(self.db, cod_odp=item.cod_odp, work_item_id=item.id)
        self.assertEqual(error.exception.status_code, 409)

    def test_saved_history_survives_empty_live_view_without_cache_write(self):
        item = self.item()
        item.source_present = False
        self.db.commit()
        live = m.QuartaTaglioEsolverLink(cod_odp='OL1', rows=[], status='missing')
        self.db.add(live)
        self.db.commit()
        links = operational_links(self.db, {'OL1':live}, ['OL1'])
        self.assertEqual(links['OL1'].status, 'ok')
        self.assertEqual(links['OL1'].ddt, item.ddt_raw)
        self.assertEqual(live.rows, [])
        self.assertFalse(self.db.dirty or self.db.new)

    def test_archived_live_rows_not_reintroduced_into_certification(self):
        item = self.item()
        self.archive()
        live = m.QuartaTaglioEsolverLink(cod_odp='OL1', status='ok', rows=[saved_ddt_row(item).model_dump()])
        link = operational_links(self.db, {'OL1':live}, ['OL1'])['OL1']
        self.assertEqual(link.rows, [])
        self.assertEqual(len(live.rows), 1)

    def test_live_and_saved_are_not_duplicated(self):
        item = self.item()
        live = m.QuartaTaglioEsolverLink(cod_odp='OL1', status='ok', rows=[saved_ddt_row(item).model_dump()])
        self.assertEqual(len(operational_links(self.db, {'OL1':live}, ['OL1'])['OL1'].rows), 1)

    def test_changed_report_and_different_database_rejected(self):
        self.item()
        report = build_plan(self.db, target=TARGET, cutoff=CUTOFF)
        for target in ({'environment':'alpha'}, TARGET):
            if target == TARGET:
                self.item(IdDocumento='2')
            with self.assertRaises(ValueError):
                apply_plan(self.db, approved=report, target=target, cutoff=CUTOFF, actor='Test')
        self.assertEqual(self.db.query(m.QuartaTaglioDdtArchiveEvent).count(), 0)

    def test_expired_and_tampered_report_rejected(self):
        self.item()
        report = build_plan(self.db, target=TARGET, cutoff=CUTOFF)
        report['generated_at'] = (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        with self.assertRaises(ValueError):
            apply_plan(self.db, approved=report, target=TARGET, cutoff=CUTOFF, actor='Test')
        report = build_plan(self.db, target=TARGET, cutoff=CUTOFF)
        report['items'][0]['action'] = 'keep'
        with self.assertRaises(ValueError):
            apply_plan(self.db, approved=report, target=TARGET, cutoff=CUTOFF, actor='Test')


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'), 'isolated PostgreSQL test URL not supplied')
class DdtArchivePostgresTest(DdtArchiveTest):
    def setUp(self):
        history.DdtHistoryPostgresTest.setUp(self)
        self.addCleanup(lambda: history.DdtHistoryPostgresTest.tearDown(self))
        self.db = self.factory()
        self.addCleanup(self.db.close)
        self.db.query(m.QuartaTaglioDdtWorkItem).delete()
        self.files = TemporaryDirectory(prefix='certi-archive-test-')
        self.addCleanup(self.files.cleanup)
        storage = patch.object(service.settings, 'document_storage_root', self.files.name)
        storage.start()
        self.addCleanup(storage.stop)
        from app.modules.acquisition.models import Document
        self.document = Document(tipo_documento='certificato', nome_file_originale='test.pdf', storage_key='supplier.pdf')
        self.db.add(self.document)
        self.db.commit()

    def test_migration_repeatable_and_rollback_preserves_data(self):
        self.db.rollback()
        with self.engine.begin() as conn:
            m.QuartaTaglioDdtArchiveEvent.__table__.drop(conn)
        try:
            with self.engine.begin() as conn:
                m.QuartaTaglioDdtArchiveEvent.__table__.create(conn, checkfirst=True)
                raise ValueError('simulated_failure')
        except ValueError:
            pass
        from sqlalchemy import inspect
        self.assertFalse(inspect(self.root_engine).has_table(m.QuartaTaglioDdtArchiveEvent.__tablename__, schema=self.schema))
        with self.engine.begin() as conn:
            m.QuartaTaglioDdtArchiveEvent.__table__.create(conn, checkfirst=True)
            m.QuartaTaglioDdtArchiveEvent.__table__.create(conn, checkfirst=True)
        self.assertEqual(self.db.query(type(self.document)).count(), 1)

    def test_offline_apply_lock_and_rollback(self):
        from app.modules.quarta_taglio.ddt_word_recovery import lock_inputs
        from sqlalchemy.exc import DBAPIError
        from sqlalchemy import update
        item = self.item()
        self.db.rollback()
        with self.factory() as writer, writer.begin():
            writer.execute(update(m.QuartaTaglioDdtWorkItem).where(m.QuartaTaglioDdtWorkItem.id == item.id).values(cliente='writer'))
            with self.factory() as worker, worker.begin():
                with self.assertRaises(DBAPIError):
                    lock_inputs(worker)
            writer.rollback()
        with self.factory() as worker, worker.begin():
            lock_inputs(worker)
            report = build_plan(worker, target=TARGET, cutoff=CUTOFF)
            self.assertEqual(len(apply_plan(worker, approved=report, target=TARGET, cutoff=CUTOFF, actor='Test')), 1)
            worker.rollback()
        self.assertEqual(self.db.query(m.QuartaTaglioDdtArchiveEvent).count(), 0)
