"""Use the real durable job queue with an isolated DB, never eSolver."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.startup import bootstrap  # noqa: F401
from app.core.database import Base
from app.core.integrations.background import BackgroundManager
from app.core.integrations.models import IntegrationBackgroundJob as Job
from app.modules.quarta_taglio import ddt_queue, scheduler
from app.modules.quarta_taglio.ddt_schedule import ddt_read_slots
from app.modules.quarta_taglio.ddt_snapshot import SnapshotResult
from app.modules.quarta_taglio.models import QuartaTaglioDdtSyncRun as SyncRun


SLOT = datetime(2026, 11, 25, 17, tzinfo=timezone.utc)
YESTERDAY = SLOT - timedelta(days=1)


@pytest.fixture(params=['sqlite', 'postgresql'])
def daily_fixture(tmp_path, monkeypatch, request):
    admin = schema = None
    if request.param == 'postgresql':
        uri = os.getenv('CERTI_EXTERNAL_WAIT_TEST_DATABASE_URL')
        if not uri:
            pytest.skip('Isolated PostgreSQL opt-in not configured')
        url = make_url(uri)
        assert url.host in {'localhost', '127.0.0.1'} and url.port == 55440
        assert url.database == 'certi_ddt_test_external_wait'
        schema = 'qa_daily_' + uuid4().hex
        admin = create_engine(uri)
        with admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(uri, connect_args={'options': '-csearch_path=' + schema})
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "daily.sqlite"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False)
    worker = BackgroundManager(engine, root=tmp_path / 'private', revision='daily-qa')
    monkeypatch.setattr(scheduler, 'SessionLocal', factory)
    monkeypatch.setattr(scheduler, 'manager', lambda: worker)
    monkeypatch.setattr(scheduler.settings, 'ddt_snapshot_enabled', True)
    monkeypatch.setattr(scheduler.settings, 'ddt_word_reuse_enabled', False)
    monkeypatch.setattr(scheduler.settings, 'ddt_revisions_enabled', False)
    try:
        yield factory, worker
    finally:
        engine.dispose()
        if admin is not None:
            assert schema.startswith('qa_daily_') and len(schema) == 41
            with admin.begin() as db:
                db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            admin.dispose()


def record_attempt(factory, when, status='success'):
    with factory.begin() as db:
        db.add(SyncRun(started_at=when, finished_at=when + timedelta(seconds=5), status=status))


def test_18_rome_and_clock_changes_including_sundays():
    for before, expected, after in [
        ('2026-03-28T17:00:00+00:00', '2026-03-29T16:00:00+00:00', '2026-03-30T16:00:00+00:00'),
        ('2026-10-24T16:00:00+00:00', '2026-10-25T17:00:00+00:00', '2026-10-26T17:00:00+00:00'),
    ]:
        before, expected, after = map(datetime.fromisoformat, (before, expected, after))
        assert ddt_read_slots(expected - timedelta(seconds=1)) == (before, expected)
        assert ddt_read_slots(expected) == (expected, after)


def test_fresh_install_and_restart_before_18_wait_for_the_next_slot(daily_fixture):
    factory, _ = daily_fixture
    before = SLOT - timedelta(seconds=1)
    assert scheduler.enqueue_daily_ddt_if_due(before) is None
    with factory() as db:
        assert scheduler.daily_ddt_plan(db, before, None) == (None, SLOT)
    record_attempt(factory, YESTERDAY)
    assert scheduler.enqueue_daily_ddt_if_due(before) is None
    assert scheduler.enqueue_daily_ddt_if_due(SLOT) is not None


def test_catch_up_multiple_schedulers_once_and_restart_after_success(daily_fixture, monkeypatch):
    factory, worker = daily_fixture
    record_attempt(factory, YESTERDAY - timedelta(days=3))
    now = SLOT + timedelta(hours=3)
    # Both schedulers can see that the evening was missed. Only one job wins.
    with ThreadPoolExecutor(max_workers=2) as pool:
        queued = list(pool.map(scheduler.enqueue_daily_ddt_if_due, (now, now)))
    ids = {i for i in queued if i}
    assert len(ids) == 1
    with factory() as db:
        assert scheduler.daily_ddt_job_active(db)
        assert db.scalar(select(func.count()).select_from(Job)) == 1

    reads = []
    def snapshot(*, session_factory):
        reads.append(now)
        record_attempt(session_factory, now)
        return SnapshotResult(status='success')

    monkeypatch.setattr(scheduler, 'sync_ddt_snapshot', snapshot)
    with patch.object(scheduler, 'ddt_read_slots', return_value=(SLOT, SLOT + timedelta(days=1))):
        assert worker.run_one()
    assert reads == [now]
    # After midnight this is still the same elapsed slot, not another run.
    assert scheduler.enqueue_daily_ddt_if_due(SLOT + timedelta(hours=8)) is None
    assert not worker.run_one()


def test_error_from_esolver_not_repeated_and_does_not_delete_last_success(daily_fixture):
    factory, worker = daily_fixture
    record_attempt(factory, YESTERDAY)
    assert scheduler.enqueue_daily_ddt_if_due(SLOT)

    def failure(*, session_factory):
        record_attempt(session_factory, SLOT, 'error')
        return SnapshotResult(status='error', error_code='source_read_failed')

    with patch.object(scheduler, 'ddt_read_slots', return_value=(SLOT, SLOT + timedelta(days=1))), \
            patch.object(scheduler, 'sync_ddt_snapshot', side_effect=failure) as sync, \
            patch.object(scheduler, '_process_pending_revisions') as revisions:
        assert worker.run_one()
        sync.assert_called_once()
        revisions.assert_not_called()
    assert scheduler.enqueue_daily_ddt_if_due(SLOT + timedelta(minutes=20)) is None
    with patch.object(ddt_queue, 'datetime', wraps=datetime) as clock, factory() as db:
        clock.now.return_value = SLOT + timedelta(minutes=20)
        status = ddt_queue.read_ddt_sync(db)
        assert (status.last_attempt.status, status.last_success.status) == ('error', 'success')
        assert status.last_scheduled_at == SLOT and status.next_scheduled_at == SLOT + timedelta(days=1)
        assert not status.in_progress


def test_worker_interrupted_before_read_has_one_recovery_and_no_loop(daily_fixture):
    factory, worker = daily_fixture
    original = scheduler.enqueue_daily_ddt_if_due(SLOT)

    def interrupt(job_id):
        with factory.begin() as db:
            db.get(Job, job_id).status = 'running'
        assert worker.run_one()  # There is no owned worker lock after a restart.
        with factory() as db:
            assert db.get(Job, job_id).status == 'interrupted'

    interrupt(original)
    recovered = scheduler.enqueue_daily_ddt_if_due(SLOT + timedelta(minutes=10))
    assert recovered != original
    interrupt(recovered)
    assert scheduler.enqueue_daily_ddt_if_due(SLOT + timedelta(minutes=12)) == recovered
    assert not worker.run_one()
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Job)) == 2


def test_disabled_or_superseded_job_never_reads_esolver(daily_fixture, monkeypatch):
    factory, _ = daily_fixture
    monkeypatch.setattr(scheduler.settings, 'ddt_snapshot_enabled', False)
    assert scheduler.enqueue_daily_ddt_if_due(SLOT) is None
    with factory() as db, patch.object(scheduler, 'sync_ddt_snapshot') as sync:
        assert scheduler.scheduled_ddt_refresh(db, SLOT)['status'] == 'disabled'
        monkeypatch.setattr(scheduler.settings, 'ddt_snapshot_enabled', True)
        with patch.object(scheduler, 'ddt_read_slots', return_value=(SLOT, SLOT + timedelta(days=1))):
            assert scheduler.scheduled_ddt_refresh(db, YESTERDAY)['status'] == 'superseded'
        sync.assert_not_called()


def test_daily_loop_only_queues_and_first_check_runs_on_restart():
    with patch.object(scheduler, 'enqueue_daily_ddt_if_due') as enqueue, \
            patch.object(scheduler.asyncio, 'sleep', new=AsyncMock(side_effect=asyncio.CancelledError)):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(scheduler.daily_ddt_sync_loop())
        enqueue.assert_called_once()
