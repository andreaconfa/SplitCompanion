from datetime import timedelta
import pytest
from sqlmodel import Session, select
from app import db
from app.config import get_settings

PASSWORD = "password12345"


def challenge(client, username="alex"):
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    assert "split_session" not in response.cookies
    return response.json()["challenge_token"]


def require_mfa(monkeypatch):
    monkeypatch.setitem(get_settings().__dict__, "mfa_required", True)


def test_required_login_cannot_access_api_before_enrollment(client, monkeypatch):
    require_mfa(monkeypatch)
    token = challenge(client)
    assert token
    assert client.get("/api/auth/me").status_code == 401


def enroll(client, monkeypatch):
    import pyotp

    require_mfa(monkeypatch)
    token = challenge(client)
    setup = client.post("/api/auth/mfa/setup", json={"challenge_token": token})
    assert setup.status_code == 200
    data = setup.json()
    assert "<svg" in data["qr_svg"]
    assert data["secret"] in data["otpauth_uri"]
    response = client.post(
        "/api/auth/mfa/confirm",
        json={"challenge_token": token, "code": pyotp.TOTP(data["secret"]).now()},
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["session"]["csrf_token"]
    return data["secret"], response.json()["recovery_codes"], token


def test_enroll_encrypts_secret_and_only_final_step_authenticates(client, monkeypatch):
    from app.models import User

    secret, codes, token = enroll(client, monkeypatch)
    assert len(codes) == 10 and len(set(codes)) == 10
    assert client.get("/api/auth/me").status_code == 200
    with Session(db.engine) as s:
        user = s.exec(select(User).where(User.username == "alex")).one()
        assert secret not in user.mfa_secret
    assert (
        client.post(
            "/api/auth/mfa/confirm", json={"challenge_token": token, "code": "000000"}
        ).status_code
        == 401
    )


def test_replay_recovery_single_use_and_enabled_enforced_without_policy(client, monkeypatch):
    import pyotp

    secret, codes, _ = enroll(client, monkeypatch)
    monkeypatch.setattr(get_settings(), "mfa_required", False)
    token = challenge(client)
    assert (
        client.post(
            "/api/auth/mfa/verify",
            json={"challenge_token": token, "code": pyotp.TOTP(secret).now()},
        ).status_code
        == 401
    )
    assert client.post("/api/auth/mfa/setup", json={"challenge_token": token}).status_code == 401
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
        ).status_code
        == 200
    )
    token = challenge(client)
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[1]}
        ).status_code
        == 200
    )


def test_password_failure_throttle_survives_request_rollback(client):
    statuses = [
        client.post("/api/auth/login", json={"username": "alex", "password": "wrong"}).status_code
        for _ in range(12)
    ]
    assert 429 in statuses


def test_legacy_session_denied_when_mfa_becomes_required(client, monkeypatch):
    require_mfa(monkeypatch)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_and_replaced_challenges_cannot_enroll(client, monkeypatch):
    from app.models import MFAChallenge, now

    require_mfa(monkeypatch)
    old = challenge(client)
    token = challenge(client)
    assert client.post("/api/auth/mfa/setup", json={"challenge_token": old}).status_code == 401
    with Session(db.engine) as s:
        row = s.exec(select(MFAChallenge)).one()
        row.expires_at = now() - timedelta(seconds=1)
        s.add(row)
        s.commit()
    assert client.post("/api/auth/mfa/setup", json={"challenge_token": token}).status_code == 401


def test_other_user_recovery_code_cannot_authenticate(client, monkeypatch):
    import pyotp

    _, codes, _ = enroll(client, monkeypatch)
    token = challenge(client, "laura")
    setup = client.post("/api/auth/mfa/setup", json={"challenge_token": token}).json()
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/mfa/confirm",
            json={"challenge_token": token, "code": pyotp.TOTP(setup["secret"]).now()},
        ).status_code
        == 200
    )
    token = challenge(client, "laura")
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
        ).status_code
        == 401
    )
    assert client.get("/api/auth/me").status_code == 401


def test_recovery_regeneration_requires_csrf_password_and_factor(client, monkeypatch):
    _, codes, _ = enroll(client, monkeypatch)
    del client.headers["X-CSRF-Token"]
    assert (
        client.post(
            "/api/auth/mfa/recovery-codes", json={"password": PASSWORD, "code": codes[0]}
        ).status_code
        == 403
    )
    client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf_token"]
    assert (
        client.post(
            "/api/auth/mfa/recovery-codes", json={"password": "wrong", "code": codes[0]}
        ).status_code
        == 401
    )
    assert client.get("/api/auth/mfa/status").json()["recovery_codes_remaining"] == 10
    rotated = client.post(
        "/api/auth/mfa/recovery-codes", json={"password": PASSWORD, "code": codes[0]}
    )
    assert rotated.status_code == 200
    assert len(rotated.json()["recovery_codes"]) == 10
    token = challenge(client)
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[1]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/mfa/verify",
            json={"challenge_token": token, "code": rotated.json()["recovery_codes"][0]},
        ).status_code
        == 200
    )


def test_cli_reset_mfa_revokes_sessions_challenges_recovery_and_push(client, monkeypatch):
    from app import cli
    from app.models import User, AuthSession, MFAChallenge, MFARecovery
    from app.push_models import PushDevice, PushOutbox

    _, _, _ = enroll(client, monkeypatch)
    challenge(client)
    from app.models import now

    with Session(db.engine) as s:
        device = PushDevice(
            user_id=1,
            endpoint="https://fcm.googleapis.com/reset-test",
            p256dh="test",
            auth="test",
            session_hash="test",
        )
        s.add(device)
        s.flush()
        s.add(
            PushOutbox(
                device_id=device.id, event_key="reset-test", expires_at=now() + timedelta(minutes=5)
            )
        )
        s.commit()
    monkeypatch.setattr(cli, "engine", db.engine)
    monkeypatch.setattr("sys.argv", ["cli", "reset-mfa", "alex"])
    cli.main()
    with Session(db.engine) as s:
        user = s.exec(select(User).where(User.username == "alex")).one()
        assert not user.mfa_enabled and user.mfa_secret is None
        for model in (AuthSession, MFAChallenge, MFARecovery, PushDevice):
            assert not s.exec(select(model).where(model.user_id == user.id)).all()
    with Session(db.engine) as s:
        assert not s.exec(select(PushOutbox)).all()
    assert (
        client.post("/api/auth/login", json={"username": "alex", "password": PASSWORD}).json()[
            "status"
        ]
        == "mfa_setup_required"
    )


def test_throttled_ip_does_not_create_unbounded_account_rows(client):
    from app.auth import hash_token
    from app.models import AuthThrottle

    with Session(db.engine) as s:
        row = s.get(AuthThrottle, hash_token("password:ip:testclient"))
        row.attempts = 100
        s.add(row)
        s.commit()
    for i in range(5):
        assert (
            client.post(
                "/api/auth/login", json={"username": f"unknown-{i}", "password": "wrong"}
            ).status_code
            == 429
        )
    with Session(db.engine) as s:
        assert len(s.exec(select(AuthThrottle)).all()) == 2


def test_mfa_failed_attempts_are_durable_and_exhaustion_blocks_valid_factor(client, monkeypatch):
    _, codes, _ = enroll(client, monkeypatch)
    token = challenge(client)
    statuses = [
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": "bad"}
        ).status_code
        for _ in range(11)
    ]
    assert 429 in statuses
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
        ).status_code
        == 429
    )
    assert client.get("/api/auth/me").status_code == 401


def test_concurrent_recovery_verification_succeeds_exactly_once(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from app.main import app

    _, codes, _ = enroll(client, monkeypatch)
    token = challenge(client)

    def verify():
        with TestClient(app) as other:
            return other.post(
                "/api/auth/mfa/verify", json={"challenge_token": token, "code": codes[0]}
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: verify(), range(2)))
    assert sorted(statuses) == [200, 401]


def test_cli_reset_password_invalidates_challenge_and_preserves_mfa(client, monkeypatch):
    from app import cli
    from app.models import MFAChallenge, User

    _, _, _ = enroll(client, monkeypatch)
    token = challenge(client)
    monkeypatch.setattr(cli, "engine", db.engine)
    monkeypatch.setattr("sys.argv", ["cli", "reset-password", "alex", "--password-stdin"])
    monkeypatch.setattr("builtins.input", lambda: "newpassword12345")
    cli.main()
    assert (
        client.post(
            "/api/auth/mfa/verify", json={"challenge_token": token, "code": "123456"}
        ).status_code
        == 401
    )
    with Session(db.engine) as s:
        assert s.exec(select(User).where(User.username == "alex")).one().mfa_enabled
        assert not s.exec(select(MFAChallenge)).all()
    response = client.post(
        "/api/auth/login", json={"username": "alex", "password": "newpassword12345"}
    )
    assert response.json()["status"] == "mfa_required"
    assert "split_session" not in response.cookies


def test_setup_is_idempotent_and_pending_secret_is_encrypted(client, monkeypatch):
    from app.models import MFAChallenge

    require_mfa(monkeypatch)
    token = challenge(client)
    first = client.post("/api/auth/mfa/setup", json={"challenge_token": token}).json()
    second = client.post("/api/auth/mfa/setup", json={"challenge_token": token}).json()
    assert first == second
    with Session(db.engine) as s:
        assert first["secret"] not in s.exec(select(MFAChallenge)).one().secret


@pytest.mark.parametrize("offset", [-1, 1])
def test_totp_accepts_adjacent_time_steps(client, monkeypatch, offset):
    import pyotp
    from types import SimpleNamespace
    from app.services import mfa_service

    require_mfa(monkeypatch)
    stamp = 1790884800
    monkeypatch.setattr(mfa_service, "time", SimpleNamespace(time=lambda: stamp))
    token = challenge(client)
    secret = client.post("/api/auth/mfa/setup", json={"challenge_token": token}).json()["secret"]
    code = pyotp.TOTP(secret).at(stamp + offset * 30)
    assert (
        client.post(
            "/api/auth/mfa/confirm", json={"challenge_token": token, "code": code}
        ).status_code
        == 200
    )


def test_recovery_rotation_rechecks_session_after_throttle_transaction(client, monkeypatch):
    from app.api import auth_mfa
    from app.models import AuthSession
    from sqlmodel import delete

    _, codes, _ = enroll(client, monkeypatch)
    original = auth_mfa.throttle

    def revoke_during_counter_commit(s, request, purpose, account):
        original(s, request, purpose, account)
        s.exec(delete(AuthSession))
        s.commit()

    monkeypatch.setattr(auth_mfa, "throttle", revoke_during_counter_commit)
    assert (
        client.post(
            "/api/auth/mfa/recovery-codes", json={"password": PASSWORD, "code": codes[0]}
        ).status_code
        == 401
    )


def test_mfa_reauth_preserves_push_consent_and_switch_or_logout_revokes(client, monkeypatch):
    from app.auth import hash_token
    from app.models import now
    from app.push_models import PushDevice, PushOutbox

    _, codes, _ = enroll(client, monkeypatch)
    with Session(db.engine) as s:
        device = PushDevice(
            user_id=1,
            endpoint="https://fcm.googleapis.com/mfa-browser",
            p256dh="test",
            auth="test",
            session_hash="previous-session",
        )
        s.add(device)
        s.flush()
        device_id = device.id
        s.add(
            PushOutbox(
                device_id=device.id,
                event_key="mfa-browser",
                expires_at=now() + timedelta(minutes=5),
            )
        )
        s.commit()
    client.cookies.set("split_push_device", f"{device_id}.{hash_token('push:' + str(device_id))}")
    response = client.post("/api/auth/login", json={"username": "alex", "password": PASSWORD})
    assert response.json()["status"] == "mfa_required"
    response = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_token": response.json()["challenge_token"], "code": codes[0]},
    )
    assert response.status_code == 200
    with Session(db.engine) as s:
        assert s.get(PushDevice, device_id) is not None
    # Switch to an account without MFA under optional policy; final login revokes old browser consent.
    monkeypatch.setattr(get_settings(), "mfa_required", False)
    response = client.post("/api/auth/login", json={"username": "laura", "password": PASSWORD})
    assert response.status_code == 200
    with Session(db.engine) as s:
        assert s.get(PushDevice, device_id) is None
        assert not s.exec(select(PushOutbox)).all()
