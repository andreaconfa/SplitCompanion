"""Restoring data must not revive authentication capabilities from a snapshot."""

import sqlite3
from pathlib import Path

import pyotp
import pytest
from sqlmodel import Session, delete, select

from app import db
from app.auth import hash_token
from app.backup import backup_full, restore_full
from app.config import Settings, get_settings
from app.models import AuthSession, MFAChallenge, MFARecovery, User
from app.services.mfa_service import cipher, issue_challenge


@pytest.mark.parametrize("capability", ["session", "mfa_challenge"])
def test_restore_requires_fresh_login_without_rotating_mfa(
    client, tmp_path, monkeypatch, capability
):
    secret = "JBSWY3DPEHPK3PXP"
    encrypted_secret = cipher().encrypt(secret.encode()).decode()
    recovery_code = "synthetic-recovery-code"
    source = Settings(
        db=db.engine.url.database, secret_key=get_settings().secret_key, _env_file=None
    )
    with sqlite3.connect(source.db) as connection:
        connection.execute("CREATE TABLE alembic_version(version_num TEXT)")
        connection.execute("INSERT INTO alembic_version VALUES ('audit-test')")
    with Session(db.engine) as session:
        user = session.exec(select(User).where(User.username == "alex")).one()
        user.mfa_enabled = True
        user.mfa_secret = encrypted_secret
        session.add(user)
        auth = session.get(AuthSession, hash_token(client.cookies.get("split_session")))
        auth.mfa_verified = True
        session.add(auth)
        session.add(MFARecovery(code_hash=hash_token("recovery:" + recovery_code), user_id=user.id))
        challenge = issue_challenge(session, user)["challenge_token"]
        session.commit()

    archive = backup_full(source, tmp_path / "backups")
    # Logout and challenge revocation happen after the snapshot was taken.
    with Session(db.engine) as session:
        session.exec(delete(AuthSession))
        session.exec(delete(MFAChallenge))
        session.commit()
    assert client.get("/api/auth/me").status_code == 401

    target = Settings(db=str(tmp_path / "restored" / "db.sqlite"), secret_key="", _env_file=None)
    restore_full(target, archive, {"audit-test"})
    restored_engine = db.make_engine(target.db)
    monkeypatch.setattr(db, "engine", restored_engine)
    try:
        if capability == "session":
            assert client.get("/api/auth/me").status_code == 401
        else:
            assert (
                client.post(
                    "/api/auth/mfa/verify",
                    json={"challenge_token": challenge, "code": pyotp.TOTP(secret).now()},
                ).status_code
                == 401
            )

        assert (Path(target.db).parent / "secret.key").read_text() == source.secret_key
        with Session(restored_engine) as session:
            user = session.exec(select(User).where(User.username == "alex")).one()
            assert user.mfa_secret == encrypted_secret
            assert cipher().decrypt(user.mfa_secret.encode()).decode() == secret
            assert session.get(MFARecovery, hash_token("recovery:" + recovery_code)) is not None

        login = client.post(
            "/api/auth/login", json={"username": "alex", "password": "password12345"}
        )
        assert login.status_code == 200
        assert (
            client.post(
                "/api/auth/mfa/verify",
                json={"challenge_token": login.json()["challenge_token"], "code": recovery_code},
            ).status_code
            == 200
        )
    finally:
        restored_engine.dispose()
