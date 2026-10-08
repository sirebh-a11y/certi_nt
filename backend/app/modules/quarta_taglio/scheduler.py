from __future__ import annotations

import asyncio

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.logs.service import log_service
from app.modules.quarta_taglio.ddt_snapshot import sync_ddt_snapshot
from app.modules.quarta_taglio.service import sync_and_list_quarta_taglio


QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS = 15 * 60


async def quarta_taglio_periodic_sync_loop() -> None:
    while True:
        await asyncio.sleep(QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS)
        if settings.ddt_snapshot_enabled:
            try:
                # The snapshot owns its session; network I/O runs off the event loop.
                await asyncio.to_thread(sync_ddt_snapshot)
            except Exception:  # pragma: no cover - e.g. database unavailable
                log_service.record("ddt_snapshot", "Snapshot DDT non riuscito: verificare collegamento database")
        db = SessionLocal()
        try:
            sync_and_list_quarta_taglio(db)
        except Exception as exc:  # pragma: no cover - defensive background guard
            log_service.record("quarta_taglio", f"Aggiornamento periodico fallito: {exc}")
        finally:
            db.close()
        if settings.ddt_word_reuse_enabled:
            from app.modules.quarta_taglio.ddt_word_reuse import sync_ddt_words
            try:
                outcome = await asyncio.to_thread(sync_ddt_words)
                if outcome['prepared'] or outcome['errors']:
                    log_service.record('ddt_word_reuse', f"Word DDT: {outcome}")
            except Exception:
                log_service.record('ddt_word_reuse', 'Preparazione Word DDT non riuscita: verificare il Registro')
