"""Stable upload reference for Incoming and Gemba (never the AI completion time)."""

from datetime import UTC, date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

from fastapi import HTTPException

ROME = ZoneInfo("Europe/Rome")


def as_utc(value: datetime) -> datetime:
    # SQLite test fixtures and legacy timestamps can be naive; database time is UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def row_load_time(row) -> datetime | None:
    value = getattr(row, "incoming_loaded_at", None)
    if value is None:
        document = row.ddt_document or row.certificate_document
        value = document.data_upload if document is not None else row.created_at
    return as_utc(value) if value is not None else None


def detached_certificate(row) -> bool:
    return any(event.azione == "certificato_separato_da_ddt" for event in row.history_events)


def certificate_load_time_on_ddt_link(row, ddt) -> datetime | None:
    return as_utc(ddt.data_upload) if detached_certificate(row) else row_load_time(row)


def gemba_time_bounds(day_from: date, day_to: date, time_from: str, time_to: str) -> tuple[datetime, datetime]:
    """Italian wall-clock minutes, including the entire selected final minute."""
    values = []
    for day, clock, fold in ((day_from, time_from, 0), (day_to, time_to, 1)):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
            raise HTTPException(status_code=400, detail="Orario non valido: usa HH:MM.")
        local = datetime.combine(day, time.fromisoformat(clock), tzinfo=ROME).replace(fold=fold)
        if local.astimezone(UTC).astimezone(ROME).replace(tzinfo=None) != local.replace(tzinfo=None):
            raise HTTPException(status_code=400, detail="Orario non disponibile nel giorno del cambio ora.")
        values.append(local)
    start, end = values
    if (day_to, time_to) < (day_from, time_from):
        raise HTTPException(status_code=400, detail="L'orario finale non può precedere quello iniziale.")
    # On the autumn transition include both occurrences of an ambiguous minute.
    return start.astimezone(UTC), end.astimezone(UTC) + timedelta(minutes=1)
