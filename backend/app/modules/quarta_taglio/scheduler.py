from __future__ import annotations

import asyncio

from app.core.database import SessionLocal
from app.core.logs.service import log_service
from app.modules.quarta_taglio.service import sync_and_list_quarta_taglio


QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS = 15 * 60


async def quarta_taglio_periodic_sync_loop() -> None:
    while True:
        await asyncio.sleep(QUARTA_TAGLIO_SYNC_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            sync_and_list_quarta_taglio(db)
        except Exception as exc:  # pragma: no cover - defensive background guard
            log_service.record("quarta_taglio", f"Aggiornamento periodico fallito: {exc}")
        finally:
            db.close()
