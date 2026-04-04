from datetime import datetime

from pydantic import BaseModel


class LogEntry(BaseModel):
    timestamp: datetime
    event_type: str
    message: str
    actor_email: str | None = None


class LogListResponse(BaseModel):
    items: list[LogEntry]
