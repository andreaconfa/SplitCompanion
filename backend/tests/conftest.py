import os

os.environ["SPLIT_COMPANION_SECRET_KEY"] = "test-secret-not-for-production-1234567890"
os.environ["SPLIT_COMPANION_SCHEDULER"] = "false"
os.environ["SPLIT_COMPANION_DB"] = "/tmp/split-companion-tests-default.db"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session
from app import db
from app.auth import hasher
from app.models import User
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = db.make_engine(str(tmp_path / "api.db"))
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine) as s:
        for i, name in enumerate(["alex", "laura", "outsider"]):
            s.add(
                User(
                    username=name,
                    display_name=name.capitalize(),
                    password_hash=hasher.hash("password12345"),
                    is_admin=i == 0,
                )
            )
        s.commit()
    with TestClient(app) as c:
        login = c.post("/api/auth/login", json={"username": "alex", "password": "password12345"})
        assert login.status_code == 200
        c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        yield c
    engine.dispose()
