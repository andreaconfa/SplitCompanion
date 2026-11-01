"""Push delivery metadata; no accounting foreign keys that prevent expense deletion."""

from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from app.models import Record, now


class PushDevice(Record, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    user_id: int = Field(foreign_key="user.id", index=True)
    endpoint: str = Field(unique=True)
    p256dh: str
    auth: str
    session_hash: str


class PushOutbox(Record, table=True):
    __table_args__ = (UniqueConstraint("event_key", "device_id"),)
    device_id: int = Field(index=True)
    event_key: str
    expense_id: int | None = None
    attempts: int = 0
    next_attempt: datetime = Field(default_factory=now, index=True)
    expires_at: datetime
    status: str = Field(default="pending", index=True)
