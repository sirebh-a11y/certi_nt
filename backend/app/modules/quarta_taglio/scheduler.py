from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.logs.service import log_service
from app.core.integrations.background import manager, register_operation
from app.core.integrations.models import IntegrationBackgroundJob
from app.modules.quarta_taglio.ddt_schedule import ROME, as_utc, attempted_slot, ddt_read_slots
from app.modules.quarta_taglio.ddt_snapshot import last_snapshot_runs, sync_ddt_snapshot
from app.modules.quarta_taglio.service import _sync_quarta_rows


QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS = 15 * 60
DDT_SCHEDULE_CHECK_SECONDS = 60


def _owned_session_factory(db):
    if isinstance(db, Session) and db.info.get('integration_background'):
        # Keep separate atomic transactions on the worker's fenced connection.
        db.rollback()
        return sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return None


def _process_pending_revisions(db, child_sessions):
    if settings.ddt_revisions_enabled:
        from app.modules.quarta_taglio.ddt_revisions import process_repairs
        from app.modules.quarta_taglio.ddt_quality_notices import dispatch_emails
        for operation in (process_repairs,dispatch_emails):
            try:
                db.rollback()
                operation(child_sessions or SessionLocal)
            except Exception:
                log_service.record('ddt_revision','Notifica o aggiornamento Word rinviato: verificare gli avvisi DDT.')


def _reuse_pending_words(db, child_sessions):
    if settings.ddt_word_reuse_enabled:
        from app.modules.quarta_taglio.ddt_word_reuse import sync_ddt_words
        try:
            if child_sessions:
                db.rollback()  # same semantics as the request's final rollback
            outcome = sync_ddt_words(session_factory=child_sessions) if child_sessions else sync_ddt_words()
            if outcome['prepared'] or outcome['errors']:
                log_service.record('ddt_word_reuse', f"Word DDT: {outcome}")
        except Exception:
            log_service.record('ddt_word_reuse', 'Preparazione Word DDT non riuscita: verificare il Registro')


def periodic_external_refresh(db):
    """Quarta and retry of local work; never acquire the eSolver DDT snapshot."""
    child_sessions = _owned_session_factory(db)
    _process_pending_revisions(db, child_sessions)
    try:
        # The page-building service also reads eSolver DDT for visible OLs.
        # Periodic Quarta only acquires Quarta, without that page refresh.
        _sync_quarta_rows(db)
    except Exception:
        db.rollback()
        log_service.record("quarta_taglio", "Aggiornamento periodico fallito: verificare il collegamento")
    _reuse_pending_words(db, child_sessions)
    return {"finished": True}


def scheduled_ddt_refresh(db, slot: datetime):
    """Acquire just the latest daily slot, then handle its new local work."""
    if not settings.ddt_snapshot_enabled:
        return {"status": "disabled"}
    slot = as_utc(slot)
    if slot != ddt_read_slots(datetime.now(timezone.utc))[0]:
        return {"status": "superseded"}
    attempt, _ = last_snapshot_runs(db)
    if attempted_slot(attempt, slot):
        return {"status": "already_attempted"}
    child_sessions = _owned_session_factory(db)
    result = sync_ddt_snapshot(session_factory=child_sessions) if child_sessions else sync_ddt_snapshot()
    if result.status == "busy":
        # This slot has no recorded attempt yet. Permit the bounded retry.
        raise RuntimeError("Lettura DDT già in corso")
    if result.status == "success":
        _process_pending_revisions(db, child_sessions)
        _reuse_pending_words(db, child_sessions)
    return {"status": result.status}


PERIODIC_OPERATION = register_operation(periodic_external_refresh)
DDT_DAILY_OPERATION = register_operation(scheduled_ddt_refresh)


def enqueue_periodic_refresh():
    with SessionLocal() as db:
        return manager().enqueue(db, PERIODIC_OPERATION, {"db": db}).id


def daily_ddt_job_active(db) -> bool:
    return db.scalar(select(IntegrationBackgroundJob.id).where(
        IntegrationBackgroundJob.operation == DDT_DAILY_OPERATION,
        IntegrationBackgroundJob.status.in_(("queued", "running")),
    ).limit(1)) is not None


def daily_ddt_plan(db, now, latest_attempt):
    slot, next_slot = ddt_read_slots(now)
    if latest_attempt is None and slot.astimezone(ROME).date() != as_utc(now).astimezone(ROME).date():
        # A fresh installation before 18:00 has no missed run to recover; an
        # interrupted job from yesterday, even before its first DB write, does.
        if db.scalar(select(IntegrationBackgroundJob.id).where(
            IntegrationBackgroundJob.operation == DDT_DAILY_OPERATION,
        ).limit(1)) is None:
            return None, next_slot
    return slot, next_slot


def enqueue_daily_ddt_if_due(now: datetime):
    if not settings.ddt_snapshot_enabled:
        return None
    with SessionLocal() as db:
        attempt, _ = last_snapshot_runs(db)
        slot, _ = daily_ddt_plan(db, now, attempt)
        if slot is None or attempted_slot(attempt, slot) or daily_ddt_job_active(db):
            return None
        args = {"db": db, "slot": slot}
        # Existing durable request receipts deduplicate across schedulers and
        # restarts. A lost worker before any recorded attempt gets one retry;
        # an actual eSolver error is recorded and is NOT polled repeatedly.
        request = f"ddt-daily:{slot.isoformat()}"
        job = manager().enqueue(db, DDT_DAILY_OPERATION, args, request_id=request)
        if job.status in {"interrupted", "failed"}:
            job = manager().enqueue(db, DDT_DAILY_OPERATION, args, request_id=f"{request}:recover")
        return job.id


async def daily_ddt_sync_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(enqueue_daily_ddt_if_due, datetime.now(timezone.utc))
        except Exception:
            log_service.record("ddt_snapshot", "Avvio lettura giornaliera DDT non riuscito")
        now = datetime.now(timezone.utc)
        _, next_slot = ddt_read_slots(now)
        await asyncio.sleep(min(DDT_SCHEDULE_CHECK_SECONDS, max(0.1, (next_slot - now).total_seconds())))


async def quarta_taglio_periodic_sync_loop() -> None:
    while True:
        await asyncio.sleep(QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS)
        try:
            # This only queues a short DB operation. A slow previous timer is
            # attached via its active key, not duplicated or expired by age.
            await asyncio.to_thread(enqueue_periodic_refresh)
        except Exception:
            log_service.record("quarta_taglio", "Avvio aggiornamento periodico non riuscito")
