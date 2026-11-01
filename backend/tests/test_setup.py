from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app import db
from app.api.setup import router
from app.bootstrap import issue_setup_token
from app.models import AuthSession, SetupState, User, now

DATA = {"username": "owner", "display_name": "Owner", "password": "strong-password-123"}


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    engine = db.make_engine(str(tmp_path / "setup.db"))
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def complete(client, token, **extra):
    return client.post(
        "/api/setup/complete", headers={"X-Setup-Token": token}, json={**DATA, **extra}
    )


def test_setup_single_use_no_session_and_permanent_gate(fresh):
    client, engine = fresh
    assert client.get("/api/setup/status").json() == {"setup_required": True}
    token = issue_setup_token(engine)
    with Session(engine) as s:
        assert s.get(SetupState, 1).token_hash != token
    response = complete(client, token)
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    with Session(engine) as s:
        user = s.exec(select(User)).one()
        assert user.is_admin
        assert not s.exec(select(AuthSession)).all()
        s.delete(user)
        s.commit()
        assert s.get(SetupState, 1).token_hash is None
    assert client.get("/api/setup/status").json() == {"setup_required": False}
    assert complete(client, token).status_code == 409
    with pytest.raises(ValueError):
        issue_setup_token(engine)


def test_invalid_expired_rotated_and_throttled_tokens(fresh):
    client, engine = fresh
    old = issue_setup_token(engine)
    token = issue_setup_token(engine)
    assert complete(client, old).status_code == 403
    with Session(engine) as s:
        state = s.get(SetupState, 1)
        state.expires_at = now() - timedelta(seconds=1)
        s.add(state)
        s.commit()
    assert complete(client, token).status_code == 403
    for _ in range(3):
        assert complete(client, "wrong").status_code == 403
    assert complete(client, "wrong").status_code == 429
    with Session(engine) as s:
        assert s.get(SetupState, 1).attempts == 5
        assert not s.exec(select(User)).all()


def test_concurrent_completion_creates_exactly_one_admin(fresh):
    client, engine = fresh
    token = issue_setup_token(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: complete(client, token).status_code, range(2)))
    assert sorted(results) == [200, 409]
    with Session(engine) as s:
        assert len(s.exec(select(User)).all()) == 1


@pytest.mark.parametrize("extra", [{"is_admin": False}, {"username": "!"}, {"password": "short"}])
def test_rejects_invalid_fields(fresh, extra):
    client, engine = fresh
    assert complete(client, issue_setup_token(engine), **extra).status_code == 422


def test_disabled_legacy_user_closes_gate(fresh):
    client, engine = fresh
    with Session(engine) as s:
        s.add(
            User(
                username="legacy", display_name="Legacy", password_hash="disabled", is_active=False
            )
        )
        s.commit()
    assert client.get("/api/setup/status").json() == {"setup_required": False}
    with pytest.raises(ValueError):
        issue_setup_token(engine)
    with Session(engine) as s:
        assert s.get(SetupState, 1).completed


@pytest.mark.parametrize("existing", [False, True])
def test_real_migration_closes_existing_installations(tmp_path, monkeypatch, existing):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    root = Path(__file__).resolve().parents[1]
    engine = db.make_engine(str(tmp_path / "migration.db"))
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    monkeypatch.setattr(db, "engine", engine)
    command.upgrade(config, "0006_user_avatars")
    with engine.begin() as connection:
        if existing:
            connection.execute(
                text(
                    "INSERT INTO \"user\" (username, display_name, password_hash, is_admin, is_active, created_at, updated_at, mfa_enabled, mfa_last_counter) VALUES ('legacy', 'Legacy', 'disabled', 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, -1)"
                )
            )
    command.upgrade(config, "head")
    with Session(engine) as s:
        assert s.get(SetupState, 1).completed is existing
    engine.dispose()
