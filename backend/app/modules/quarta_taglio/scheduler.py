from __future__ import annotations

import asyncio
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.logs.service import log_service
from app.core.integrations.background import manager, register_operation
from app.modules.quarta_taglio.ddt_snapshot import sync_ddt_snapshot
from app.modules.quarta_taglio.service import sync_and_list_quarta_taglio


QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS = 15 * 60


def periodic_external_refresh(db):
    """Runs only in the durable worker, never on the server's event loop."""
    child_sessions = None
    if isinstance(db, Session) and db.info.get('integration_background'):
        # Snapshot and Word reuse keep their dedicated atomic Sessions, but
        # share the worker's owned physical connection and loss-of-lock fence.
        # Do not start a child inside a parent's incidental read transaction.
        db.rollback()
        child_sessions = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    if settings.ddt_snapshot_enabled:
        try:
            sync_ddt_snapshot(session_factory=child_sessions) if child_sessions else sync_ddt_snapshot()
        except Exception:
            log_service.record("ddt_snapshot", "Snapshot DDT non riuscito: verificare collegamento database")
    try:
        sync_and_list_quarta_taglio(db)
    except Exception:
        db.rollback()
        log_service.record("quarta_taglio", "Aggiornamento periodico fallito: verificare il collegamento")
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
    return {"finished": True}


PERIODIC_OPERATION = register_operation(periodic_external_refresh)


def enqueue_periodic_refresh():
    with SessionLocal() as db:
        return manager().enqueue(db, PERIODIC_OPERATION, {"db": db}).id


async def quarta_taglio_periodic_sync_loop() -> None:
    while True:
        await asyncio.sleep(QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS)
        try:
            # This only queues a short DB operation. A slow previous timer is
            # attached via its active key, not duplicated or expired by age.
            await asyncio.to_thread(enqueue_periodic_refresh)
        except Exception:
            log_service.record("quarta_taglio", "Avvio aggiornamento periodico non riuscito")
