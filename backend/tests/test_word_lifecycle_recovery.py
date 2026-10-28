"""Offline repair: synthetic files/isolated DB only, never company connections."""
from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from sqlalchemy import event, select

from app.modules.quarta_taglio import service, word_reference as refs, ddt_word_reuse as reuse
from app.modules.quarta_taglio import word_lifecycle_recovery as repair
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate as C
from scripts import recover_word_lifecycle_alpha as cli  # Register all models BEFORE fixture create_all.
import test_quarta_taglio_word_reference as fixture

TARGET = dict(environment='alpha', public_host='test.invalid', database_id='isolated-test', storage_root='/test')


class LifecycleRecoveryTest(fixture.WordReferenceTest):
    def requests(self, c, mode='equivalent_path'):
        request = dict(id=c.id, mode=mode)
        if mode == 'reviewed_fingerprint':
            request.update(verified_word_sha256=reuse.file_hash(c.storage_key_docx),
                           review_note='Independent synthetic document content verified against test original.')
        return [request]

    def stale_path(self, *, closed=True):
        _, c = self.base_word(closed=closed)
        self.publish(c)
        key = service._certificate_docx_storage_key(c.cod_odp)
        service._certificate_storage_path(key).parent.mkdir(parents=True, exist_ok=True)
        service._certificate_storage_path(key).write_bytes(service._certificate_storage_path(c.storage_key_docx).read_bytes())
        c.storage_key_docx = key
        self.db.commit()
        return c

    def stale_fingerprint(self):
        _, c = self.base_word(closed=False)
        self.publish(c)
        meta = deepcopy(refs.metadata(c))
        meta['template_hash'] = '0' * 64
        c.word_reference = meta
        self.db.commit()
        return c

    def apply(self, plan, **kwargs):
        with patch.object(repair, 'lock_inputs') if self.engine.dialect.name == 'sqlite' else nullcontext():
            return repair.apply_plan(self.db, approved=plan, target=TARGET,
                                     approved_plan_id=kwargs.pop('approved_plan_id', plan['plan_id']), **kwargs)

    def test_path_repair_is_read_only_in_preview_preserves_closed_pdf_and_is_repeatable(self):
        c = self.stale_path()
        before = {col.key:getattr(c,col.key) for col in c.__table__.columns}
        file_hashes = (reuse.file_hash(c.storage_key_docx), reuse.file_hash(c.storage_key_pdf))
        statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany): statements.append(statement.split()[0].upper())
        event.listen(self.engine, 'before_cursor_execute', capture)
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertTrue(set(statements) <= {'SELECT', 'PRAGMA'})
        self.assertFalse(self.db.dirty or self.db.new or self.db.deleted)
        self.assertEqual(self.apply(plan)['status'], 'applied_in_transaction')
        self.db.commit()
        self.assertEqual(self.apply(plan)['status'], 'already_applied')
        current = self.db.get(C,c.id)
        for key,value in before.items():
            if key != 'word_reference': self.assertEqual(getattr(current,key),value,key)
        self.assertEqual(refs.metadata(current)['revision'], before['word_reference']['revision'])
        self.assertEqual(refs.metadata(current)['storage_key'], current.storage_key_docx)
        self.assertEqual((reuse.file_hash(c.storage_key_docx), reuse.file_hash(c.storage_key_pdf)), file_hashes)

    def test_fingerprint_requires_content_review_not_automatic_hash_acceptance(self):
        c = self.stale_fingerprint()
        with self.assertRaisesRegex(ValueError, 'content_review'):
            repair.build_plan(self.db, target=TARGET, requests=[dict(id=c.id,mode='reviewed_fingerprint')])
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c, 'reviewed_fingerprint'))
        before=deepcopy(refs.metadata(c))
        self.apply(plan)
        self.assertIsNone(refs.integrity_reason(self.db.get(C,c.id)))
        self.assertEqual(refs.metadata(c)['revision'], before['revision'])
        self.db.rollback()
        self.assertEqual(refs.metadata(c), before)

    def test_changed_file_or_unrelated_user_work_refuses_all_writes(self):
        c = self.stale_path()
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        before = deepcopy(refs.metadata(c))
        c.ordine_cliente = 'USER CHANGED AFTER PREVIEW'
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'changed_repeat_preview'): self.apply(plan)
        self.db.rollback()
        self.assertEqual(refs.metadata(c), before)
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        service._certificate_storage_path(c.storage_key_pdf).write_bytes(b'%PDF changed fixture')
        with self.assertRaisesRegex(ValueError, 'changed_repeat_preview'): self.apply(plan)
        self.db.rollback()
        self.assertEqual(refs.metadata(c), before)

    def test_plan_identity_expiry_and_tampering_are_rejected(self):
        c = self.stale_path()
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        with self.assertRaisesRegex(ValueError, 'unapproved'): self.apply(plan, approved_plan_id='wrong')
        changed=deepcopy(plan);changed['actions'][0]['after']['revision']='FORGED'
        with self.assertRaisesRegex(ValueError, 'modified_plan'): self.apply(changed)
        with self.assertRaisesRegex(ValueError, 'expired'): self.apply(plan, now=datetime.now(timezone.utc)+timedelta(hours=2))
        with self.assertRaisesRegex(ValueError, 'wrong_target'):
            repair.apply_plan(self.db, approved=plan, target={**TARGET,'database_id':'another'}, approved_plan_id=plan['plan_id'])

    def test_closed_fingerprint_and_wrong_ownership_are_never_adopted(self):
        c = self.stale_fingerprint()
        c.status='pdf_final'
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'never_closed'):
            repair.build_plan(self.db, target=TARGET, requests=self.requests(c,'reviewed_fingerprint'))
        c.status='draft'; c.cod_f3='OTHER'; self.db.commit()
        with self.assertRaisesRegex(ValueError, 'identity_not_verified'):
            repair.build_plan(self.db, target=TARGET, requests=self.requests(c,'reviewed_fingerprint'))

    def test_reviewed_repair_unlocks_normal_ddt_reuse_not_pdf_closure(self):
        c = self.stale_fingerprint()
        item = self.later()
        self.assertEqual(reuse.plan_item(self.db, item)['reason'], 'reference_file_changed')
        original_key, original_hash = c.storage_key_docx, reuse.file_hash(c.storage_key_docx)
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c,'reviewed_fingerprint'))
        self.apply(plan)
        self.db.commit()
        self.assertEqual(reuse.plan_item(self.db,item)['action'], 'reuse')
        self.assertEqual(self.run_worker()['prepared'], 1)
        copy = self.target(item)
        self.assertNotEqual(copy.id, c.id)
        self.assertEqual(refs.metadata(copy)['source_id'], c.id)
        self.assertEqual(copy.ddt, item.ddt_raw)
        self.assertIsNone(copy.storage_key_pdf)
        self.assertEqual(reuse.file_hash(original_key), original_hash)

    def test_batch_is_atomic_and_a_partial_application_is_not_continued(self):
        c = self.stale_path()
        other = self.cert(self.later(), certificate_number=c.certificate_number)
        other.storage_key_docx = c.storage_key_docx
        self.publish(other)
        key = service._certificate_docx_storage_key(other.cod_odp)
        service._certificate_storage_path(key).write_bytes(service._certificate_storage_path(other.storage_key_docx).read_bytes())
        other.storage_key_docx = key
        self.db.commit()
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c)+self.requests(other))
        self.apply(plan)
        self.db.rollback()
        self.assertEqual(refs.metadata(c), plan['actions'][0]['before'])
        self.assertEqual(refs.metadata(other), plan['actions'][1]['before'])
        # A previous partial/manual attempt must not be silently continued.
        from sqlalchemy import update
        self.db.execute(update(C).where(C.id==c.id).values(word_reference=plan['actions'][0]['after'],updated_at=C.updated_at))
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'partial_application'): self.apply(plan)
        self.db.rollback()
        self.assertEqual(refs.metadata(other), plan['actions'][1]['before'])


for _name in dir(fixture.WordReferenceTest):
    if _name.startswith('test_') and _name not in LifecycleRecoveryTest.__dict__:
        setattr(LifecycleRecoveryTest, _name, None)


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'), 'isolated PostgreSQL test URL not supplied')
class LifecycleRecoveryPostgresTest(LifecycleRecoveryTest):
    setUp = fixture.existing.DdtWordReusePostgresTest.setUp

    def test_active_writer_is_refused_without_waiting_or_changing_reference(self):
        from sqlalchemy.exc import DBAPIError
        c = self.stale_path()
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        before = deepcopy(refs.metadata(c))
        self.db.rollback()
        with self.factory() as writer:
            obj=writer.get(C,c.id)
            obj.ordine_cliente='in-progress user edit'
            writer.flush()
            with self.assertRaises(DBAPIError): self.apply(plan)
            self.db.rollback()
            writer.rollback()
        self.assertEqual(refs.metadata(self.db.get(C,c.id)), before)

    def _cli_apply(self, *, existing_journal):
        import json
        from pathlib import Path
        c = self.stale_path()
        cid = c.id
        plan = repair.build_plan(self.db, target=TARGET, requests=self.requests(c))
        self.db.rollback()
        folder = Path(self.files.name)
        report, backup, storage = (folder / name for name in ('review.json','qa.sql','qa.tgz'))
        report.write_text(json.dumps(plan), encoding='utf-8')
        backup.write_text('-- PostgreSQL database dump\n-- isolated test fixture only', encoding='utf-8')
        storage.write_bytes(b'isolated test fixture only; not a company backup')
        journal = report.with_suffix('.journal.jsonl')
        if existing_journal: journal.write_text('existing evidence\n', encoding='utf-8')
        args = ['repair', '--apply', '--report', str(report), '--approved-plan-id', plan['plan_id'],
                '--maintenance-confirmed', '--backup', str(backup), '--storage-backup', str(storage)]
        # Only the environment identity is replaced with the isolated fixture;
        # the CLI performs real PostgreSQL locking, update, commit and journal IO.
        with patch('sys.argv', args), patch.object(cli, 'create_engine', return_value=self.engine), \
                patch.object(cli, 'alpha_database_identity', return_value=TARGET), patch.object(self.engine, 'dispose'):
            result = cli.main()
        self.db.expire_all()
        actual = refs.metadata(self.db.get(C,cid))
        if existing_journal:
            self.assertEqual(result,1)
            self.assertEqual(actual,plan['actions'][0]['before'])
            self.assertEqual(journal.read_text(encoding='utf-8'),'existing evidence\n')
        else:
            self.assertEqual(result,0)
            self.assertEqual(actual,plan['actions'][0]['after'])
            self.assertEqual([json.loads(line)['status'] for line in journal.read_text(encoding='utf-8').splitlines()],
                             ['pending_commit','committed'])

    def test_cli_commits_only_reviewed_metadata_and_records_durable_journal(self):
        self._cli_apply(existing_journal=False)

    def test_cli_existing_journal_rolls_back_without_overwriting_evidence(self):
        self._cli_apply(existing_journal=True)
