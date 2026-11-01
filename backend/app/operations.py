"""Bounded maintenance and sanitized operational status (never accounting payloads)."""

import json
import os
import threading
from datetime import timedelta
from pathlib import Path
from sqlmodel import Session, delete
from sqlalchemy import text
from app.models import AuthSession, MFAChallenge, AuthThrottle, now
from app.push_models import PushOutbox
from app.config import get_settings
from app.runtime import writable_directory

_guard = threading.Lock()


def status():
    path = Path(get_settings().db).parent / "operations.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def record(name, success):
    with _guard:
        data = status()
        stamp = now().isoformat()
        entry = data.get(name, {})
        entry.update(ok=success, at=stamp)
        entry["last_success_at" if success else "last_error_at"] = stamp
        if not success:
            entry["error_code"] = f"{name}_failed"
        data[name] = entry
        target = Path(get_settings().db).parent / "operations.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(data))
        temporary.chmod(0o600)
        os.replace(temporary, target)


def run_job(name, action, *args):
    try:
        action(*args)
    except Exception:
        record(name, False)
        import logging

        logging.getLogger(__name__).error(
            "Operazione %s fallita; controllare la diagnostica.", name
        )
    else:
        record(name, True)


def maintenance(engine):
    stamp = now()
    with Session(engine) as s:
        s.execute(text("BEGIN IMMEDIATE"))
        s.exec(delete(AuthSession).where(AuthSession.expires_at <= stamp))
        s.exec(delete(MFAChallenge).where(MFAChallenge.expires_at <= stamp))
        s.exec(delete(AuthThrottle).where(AuthThrottle.expires_at <= stamp))
        # Only terminal jobs are removed; pending jobs retain their delivery lease.
        s.exec(
            delete(PushOutbox).where(
                PushOutbox.status.in_(["sent", "failed", "discarded"]),
                PushOutbox.expires_at < stamp - timedelta(days=7),
            )
        )
        s.commit()


def daily_backup():
    from app.backup import backup_full

    backup_full(get_settings(), kind="daily")


def ready(engine):
    from app.container import schema_versions

    head, _ = schema_versions()
    cfg = get_settings()
    writable_directory(Path(cfg.db).parent)
    with Session(engine) as s:
        if s.execute(text("SELECT version_num FROM alembic_version")).scalar() != head:
            return False
        # Acquire and release a write reservation without changing user data.
        s.rollback()
        s.execute(text("BEGIN IMMEDIATE"))
        s.rollback()
        return True
