from collections import deque
from datetime import UTC, datetime

from app.core.logs.schemas import LogEntry


class LogService:
    def __init__(self) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=200)

    def record(self, event_type: str, message: str, actor_email: str | None = None) -> None:
        self._entries.appendleft(
            LogEntry(
                timestamp=datetime.now(UTC),
                event_type=event_type,
                message=message,
                actor_email=actor_email,
            )
        )

    def list_entries(self) -> list[LogEntry]:
        return list(self._entries)


log_service = LogService()
