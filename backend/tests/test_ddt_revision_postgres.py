"""Only the disposable local DB accepted by the shared PostgreSQL fixture."""
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime, timezone
from sqlalchemy import event, select
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.modules.quarta_taglio import ddt_snapshot as snap, ddt_revisions as rev
import test_quarta_taglio_ddt_snapshot as setup


@unittest.skipUnless(os.getenv('DDT_TEST_POSTGRES_URL'),'requires isolated local PostgreSQL')
class RevisionTransactionTest(unittest.TestCase):
    def test_notice_closed_by_quality_after_claim_but_before_smtp_is_never_sent(self):
        from app.modules.quarta_taglio import ddt_quality_notices as notices
        from app.modules.quarta_taglio.ddt_router import confirm_customer_delivery
        fixture=setup.DdtSnapshotPostgresTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with fixture.factory.begin() as db:
            notice=rev.Change(document='100',ddt='TEST',before=[],after=[],
                withdrawals=[dict(ol='OL1',f3='F3',numero='TEST',riga='1',pezzi=1)],
                delivery='sent',email_status='pending',created_at=datetime.now(timezone.utc))
            db.add(notice); db.flush()
            cid=notice.id
        worker=sessionmaker(bind=fixture.engine,autoflush=False)
        actor=SimpleNamespace(name='Quality', department=SimpleNamespace(name='Qualità'))
        def close_after_claim(session):
            with fixture.factory() as other:
                self.assertEqual(other.get(rev.Change,cid).email_status,'verify')
                confirm_customer_delivery(cid,'close_notice',other,actor)
        event.listen(worker,'after_commit',close_after_claim,once=True)
        with patch.object(settings,'ddt_quality_email','quality@example.invalid'),patch.object(
                notices.email_service,'_send_with_config') as send:
            notices.dispatch_emails(worker)
            notices.dispatch_emails(fixture.factory)
            send.assert_not_called()
        with fixture.factory() as db:
            ev=db.get(rev.Change,cid)
            self.assertEqual((ev.delivery,ev.email_status,ev.decided_by),
                             ('sent_notice_closed','not_needed','Quality'))

    def test_snapshot_withdrawal_version_and_notice_rollback_or_commit_together(self):
        fixture=setup.DdtSnapshotPostgresTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        def sync(rows):
            with patch.object(snap,'_fetch_complete_snapshot',return_value=rows):
                return snap.sync_ddt_snapshot(session_factory=fixture.factory)
        with patch.object(settings,'ddt_revisions_enabled',True):
            self.assertEqual(sync([setup.row()]).status,'success')
            with fixture.factory.begin() as db:
                item=db.scalar(select(rev.Item))
                c=rev.Certificate(cod_odp=item.cod_odp,cod_f3=item.cod_f3,draft_number='TEST',
                    certificate_number='7000_00_00/26',ddt=item.ddt_raw,unit_key=item.certification_unit_key,
                    esolver_id_documento=item.id_documento,esolver_id_riga_doc=item.id_riga_doc,
                    esolver_rif_lotto_alfanum=item.rif_lotto_alfanum,status='pdf_final',
                    storage_key_pdf='old.pdf',download_token='old',closed_at=datetime.now(timezone.utc))
                db.add(c);db.flush()
                cid=c.id
                db.add(rev.Version(certificate_id=cid,version=1,status='active',storage_key_pdf='old.pdf'))
            rows=[setup.row(IdRigaDoc=4,QtaUmMag=3),setup.row(IdRigaDoc=6,QtaUmMag=1)]
            with patch('app.modules.quarta_taglio.ddt_archive.invalidate_archives',side_effect=ValueError('rollback')):
                self.assertEqual(sync(rows).status,'error')
            with fixture.factory() as db:
                self.assertEqual(db.get(rev.Certificate,cid).download_token,'old')
                self.assertEqual(db.scalar(select(rev.Version)).status,'active')
                self.assertEqual(db.query(rev.Change).count(),0)
            self.assertEqual(sync(rows).status,'success')
            self.assertEqual(sync(rows).status,'success')
            with fixture.factory() as db:
                self.assertIsNone(db.get(rev.Certificate,cid).storage_key_pdf)
                self.assertEqual(db.scalar(select(rev.Version)).status,'withdrawn')
                self.assertEqual(db.query(rev.Change).count(),1)
