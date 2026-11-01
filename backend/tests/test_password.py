from sqlmodel import Session, select
from app import db
from app.auth import create_session, verify_password
from app.models import User, AuthSession, MFAChallenge, MFARecovery, now
from app.push_models import PushDevice, PushOutbox
from datetime import timedelta

NEW = "new-account-password-12345"


def test_member_changes_only_own_password_and_revokes_all_capabilities(client):
    login = client.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    with Session(db.engine) as s:
        member = s.get(User, 2)
        create_session(s, member)
        admin_hash = s.get(User, 1).password_hash
        s.add(
            MFAChallenge(
                token_hash="pending",
                user_id=2,
                purpose="setup",
                expires_at=now() + timedelta(minutes=5),
            )
        )
        device = PushDevice(
            user_id=2,
            endpoint="https://fcm.googleapis.com/password-test",
            p256dh="key",
            auth="key",
            session_hash="old",
        )
        s.add(device)
        s.flush()
        s.add(
            PushOutbox(
                device_id=device.id, event_key="test", expires_at=now() + timedelta(minutes=5)
            )
        )
        s.commit()
    response = client.post(
        "/api/auth/password", json={"current_password": "password12345", "new_password": NEW}
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    with Session(db.engine) as s:
        assert verify_password(s.get(User, 2).password_hash, NEW)
        assert s.get(User, 1).password_hash == admin_hash
        assert not s.exec(select(AuthSession).where(AuthSession.user_id == 2)).all()
        assert not s.exec(select(MFAChallenge).where(MFAChallenge.user_id == 2)).all()
        assert not s.exec(select(PushDevice)).all()
        assert not s.exec(select(PushOutbox)).all()
    assert (
        client.post(
            "/api/auth/login", json={"username": "laura", "password": "password12345"}
        ).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"username": "laura", "password": NEW}).status_code
        == 200
    )


def test_password_change_validates_auth_csrf_current_and_new_password(client):
    payload = {"current_password": "password12345", "new_password": NEW}
    assert (
        client.post(
            "/api/auth/password", json=payload, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/auth/password", json={**payload, "current_password": "wrong"}).status_code
        == 401
    )
    assert (
        client.post("/api/auth/password", json={**payload, "new_password": "short"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/password", json={**payload, "new_password": "password12345"}
        ).status_code
        == 422
    )
    assert client.post("/api/auth/password", json={**payload, "user_id": 2}).status_code == 422
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    assert client.post("/api/auth/password", json=payload).status_code == 401


def test_password_change_requires_second_factor_preserves_mfa_and_consumes_recovery(
    client, monkeypatch
):
    import pyotp
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "mfa_required", True)
    token = client.post(
        "/api/auth/login", json={"username": "alex", "password": "password12345"}
    ).json()["challenge_token"]
    secret = client.post("/api/auth/mfa/setup", json={"challenge_token": token}).json()["secret"]
    enrollment_code = pyotp.TOTP(secret).now()
    enrolled = client.post(
        "/api/auth/mfa/confirm", json={"challenge_token": token, "code": enrollment_code}
    ).json()
    client.headers["X-CSRF-Token"] = enrolled["session"]["csrf_token"]
    codes = enrolled["recovery_codes"]
    payload = {"current_password": "password12345", "new_password": NEW}
    assert client.post("/api/auth/password", json=payload).status_code == 401
    assert client.post("/api/auth/password", json={**payload, "code": "invalid"}).status_code == 401
    # Enrollment OTP was already consumed and must not work again.
    assert (
        client.post("/api/auth/password", json={**payload, "code": enrollment_code}).status_code
        == 401
    )
    assert client.post("/api/auth/password", json={**payload, "code": codes[0]}).status_code == 200
    with Session(db.engine) as s:
        assert s.get(User, 1).mfa_enabled
        assert len(s.exec(select(MFARecovery).where(MFARecovery.user_id == 1)).all()) == 9
    challenge = client.post("/api/auth/login", json={"username": "alex", "password": NEW})
    assert challenge.json()["status"] == "mfa_required"
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/mfa/verify",
            json={"challenge_token": challenge.json()["challenge_token"], "code": codes[1]},
        ).status_code
        == 200
    )


def test_password_change_failed_attempts_are_durably_limited(client):
    outcomes = [
        client.post(
            "/api/auth/password", json={"current_password": "wrong", "new_password": NEW}
        ).status_code
        for _ in range(11)
    ]
    assert outcomes[:10] == [401] * 10
    assert outcomes[10] == 429


def test_password_change_rechecks_revoked_session_after_throttle_commit(client, monkeypatch):
    from app.services import mfa_service
    from sqlmodel import delete

    original = mfa_service.throttle

    def revoke_during_boundary(s, request, purpose, account):
        original(s, request, purpose, account)
        s.exec(delete(AuthSession).where(AuthSession.user_id == 1))
        s.commit()

    monkeypatch.setattr(mfa_service, "throttle", revoke_during_boundary)
    response = client.post(
        "/api/auth/password", json={"current_password": "password12345", "new_password": NEW}
    )
    assert response.status_code == 401
    with Session(db.engine) as s:
        assert verify_password(s.get(User, 1).password_hash, "password12345")
