"""Operational failures stay observable without changing accounting or readiness."""

from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

from app import db, operations
from app.models import AuthSession, AuthThrottle, MFAChallenge, User, Group, Expense, now
from app.push_models import PushOutbox


def test_failed_backup_retains_last_success_and_sanitizes_error(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(
        operations, "get_settings", lambda: SimpleNamespace(db=str(tmp_path / "instance.db"))
    )
    first = now()
    monkeypatch.setattr(operations, "now", lambda: first)
    operations.run_job("backup", lambda: None)
    later = first + timedelta(hours=1)
    monkeypatch.setattr(operations, "now", lambda: later)

    def fail():
        raise RuntimeError("sensitive-secret-and-private-path")

    operations.run_job("backup", fail)
    state = operations.status()["backup"]
    assert state == {
        "ok": False,
        "at": later.isoformat(),
        "last_success_at": first.isoformat(),
        "last_error_at": later.isoformat(),
        "error_code": "backup_failed",
    }
    assert "sensitive-secret" not in (tmp_path / "operations.json").read_text()
    assert "sensitive-secret" not in caplog.text
    assert (tmp_path / "operations.json").stat().st_mode & 0o777 == 0o600


def test_failed_provider_queue_is_diagnostic_and_does_not_change_readiness(
    client, tmp_path, monkeypatch
):
    from app.container import schema_versions

    monkeypatch.setattr(
        operations, "get_settings", lambda: SimpleNamespace(db=str(tmp_path / "instance.db"))
    )
    head, _ = schema_versions()
    with Session(db.engine) as s:
        s.execute(text("CREATE TABLE alembic_version(version_num TEXT)"))
        s.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": head})
        for index, status in enumerate(["failed", "failed", "pending", "sent"]):
            s.add(
                PushOutbox(
                    device_id=1,
                    event_key=f"event-{index}",
                    status=status,
                    expires_at=now() + timedelta(days=1),
                )
            )
        s.commit()

    def fail():
        raise RuntimeError("provider unavailable")

    operations.run_job("push", fail)
    diagnostics = client.get("/api/admin/status")
    assert diagnostics.status_code == 200
    assert diagnostics.json()["push_queue"] == {"failed": 2, "pending": 1, "sent": 1}
    assert diagnostics.json()["operations"]["push"]["ok"] is False
    assert client.get("/api/ready").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/admin/status").status_code == 401


def test_maintenance_preserves_pending_jobs_live_sessions_and_accounting(tmp_path, monkeypatch):
    engine = db.make_engine(str(tmp_path / "maintenance.db"))
    SQLModel.metadata.create_all(engine)
    stamp = now()
    monkeypatch.setattr(operations, "now", lambda: stamp)
    with Session(engine) as s:
        user = User(username="owner", display_name="Owner", password_hash="hash")
        s.add(user)
        s.flush()
        group = Group(name="House", created_by_user_id=user.id)
        s.add(group)
        s.flush()
        expense = Expense(
            group_id=group.id,
            description="Keep accounting",
            amount_cents=1200,
            paid_by_user_id=user.id,
            expense_date=stamp.date(),
            created_by_user_id=user.id,
        )
        s.add(expense)
        for label, expiry in [("expired", stamp), ("live", stamp + timedelta(days=1))]:
            s.add(
                AuthSession(token_hash=label, user_id=user.id, csrf_token=label, expires_at=expiry)
            )
            s.add(
                MFAChallenge(token_hash=label, user_id=user.id, purpose="login", expires_at=expiry)
            )
            s.add(AuthThrottle(key=label, expires_at=expiry))
        for status in ["pending", "sending", "sent", "failed", "discarded"]:
            for age in [8, 7, 6]:
                s.add(
                    PushOutbox(
                        device_id=1,
                        event_key=f"{status}-{age}",
                        status=status,
                        expires_at=stamp - timedelta(days=age),
                    )
                )
        s.commit()
        s.refresh(expense)
        before = expense.model_dump()
    operations.maintenance(engine)
    with Session(engine) as s:
        assert [row.token_hash for row in s.exec(select(AuthSession))] == ["live"]
        assert [row.token_hash for row in s.exec(select(MFAChallenge))] == ["live"]
        assert [row.key for row in s.exec(select(AuthThrottle))] == ["live"]
        remaining = {row.event_key for row in s.exec(select(PushOutbox))}
        assert remaining == {
            f"{status}-{age}"
            for status in ["pending", "sending", "sent", "failed", "discarded"]
            for age in [8, 7, 6]
            if age != 8 or status in ["pending", "sending"]
        }
        saved = s.exec(select(Expense)).one().model_dump()
        # SQLite loads datetimes without offsets; compare stored accounting fields.
        for key in ["created_at", "updated_at"]:
            before.pop(key)
            saved.pop(key)
        assert saved == before
        assert len(s.exec(select(User)).all()) == 1
        assert len(s.exec(select(Group)).all()) == 1
    engine.dispose()
