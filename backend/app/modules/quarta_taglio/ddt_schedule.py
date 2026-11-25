"""Calendar for the daily eSolver DDT snapshot; shipment deadlines are separate."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


ROME = ZoneInfo("Europe/Rome")
DDT_READ_TIME = time(18)


def as_utc(value: datetime) -> datetime:
    # SQLite fixtures return naive timestamps written in UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def ddt_read_slots(now: datetime) -> tuple[datetime, datetime]:
    """Most recent scheduled time and next scheduled time, both UTC instants."""
    local_day = as_utc(now).astimezone(ROME).date()
    today = datetime.combine(local_day, DDT_READ_TIME, ROME).astimezone(timezone.utc)
    if as_utc(now) >= today:
        next_day = local_day + timedelta(days=1)
        return today, datetime.combine(next_day, DDT_READ_TIME, ROME).astimezone(timezone.utc)
    previous_day = local_day - timedelta(days=1)
    return datetime.combine(previous_day, DDT_READ_TIME, ROME).astimezone(timezone.utc), today


def attempted_slot(attempt, slot: datetime) -> bool:
    return bool(attempt and attempt.status in {"success", "error"} and as_utc(attempt.started_at) >= slot)
