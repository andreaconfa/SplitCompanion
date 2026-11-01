import pytest
from sqlmodel import Session, select
from app import db
from test_api import group, expense


def test_push_endpoint_rejects_ssrf():
    from app.services.push_service import validate_endpoint

    for url in [
        "http://fcm.googleapis.com/a",
        "https://127.0.0.1/a",
        "https://evil.test/a",
        "https://fcm.googleapis.com.evil.test/a",
        "https://fcm.googleapis.com:444/a",
        "https://x@fcm.googleapis.com/a",
        "https://fcm.googleapis.com/a#x",
        "https://fcm.googleapis.com/a?x=y",
    ]:
        with pytest.raises(ValueError):
            validate_endpoint(url)
    assert validate_endpoint("https://fcm.googleapis.com/fcm/send/token")


def test_push_requires_auth_csrf_and_https(client):
    assert client.get("/api/push/config").status_code == 409
    assert (
        client.post(
            "/api/push/status",
            json={"endpoint": "https://fcm.googleapis.com/a"},
            headers={"X-CSRF-Token": ""},
        ).status_code
        == 403
    )
    client.post("/api/auth/logout")
    assert client.get("/api/push/config").status_code == 401


def test_outbox_is_atomic_recipient_scoped_and_idempotent(client):
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import enqueue_expense
    from app.models import Expense

    gid = group(client)
    with Session(db.engine) as s:
        for uid in [1, 2, 3]:
            s.add(
                PushDevice(
                    user_id=uid,
                    endpoint=f"https://fcm.googleapis.com/{uid}",
                    p256dh="key",
                    auth="key",
                    session_hash="session",
                )
            )
        s.commit()
    eid = client.post("/api/expenses", json=expense(gid)).json()["id"]
    with Session(db.engine) as s:
        rows = s.exec(select(PushOutbox)).all()
        assert len(rows) == 1
        assert s.get(PushDevice, rows[0].device_id).user_id == 2
        enqueue_expense(s, s.get(Expense, eid), 1)
        s.commit()
        assert len(s.exec(select(PushOutbox)).all()) == 1
        from app.services.records import create_expense
        from app.schemas import ExpenseCreate

        create_expense(s, ExpenseCreate(**expense(gid)), 1)
        s.rollback()
        assert len(s.exec(select(PushOutbox)).all()) == 1


def test_dispatch_survives_expired_session_retries_and_410(client):
    from datetime import timedelta
    from app.models import now
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import dispatch_push

    gid = group(client)
    with Session(db.engine) as s:
        s.add(
            PushDevice(
                user_id=2,
                endpoint="https://fcm.googleapis.com/receiver",
                p256dh="key",
                auth="key",
                session_hash="expired-session",
            )
        )
        s.commit()
    client.post("/api/expenses", json=expense(gid))
    seen = []

    def transient(subscription, payload):
        # A second writer can commit while the network call runs.
        with Session(db.engine) as other:
            from sqlalchemy import text

            other.execute(text("BEGIN IMMEDIATE"))
            other.commit()
        seen.append(payload)
        return 503

    dispatch_push(db.engine, transient)
    with Session(db.engine) as s:
        row = s.exec(select(PushOutbox)).one()
        assert row.status == "pending" and row.attempts == 1
        row.next_attempt = now() - timedelta(seconds=1)
        s.add(row)
        s.commit()
    assert len(seen) == 1
    assert "Spesa" not in seen[0]["body"] and "/expenses/" in seen[0]["url"]
    dispatch_push(db.engine, lambda *_: 410)
    with Session(db.engine) as s:
        assert not s.exec(select(PushDevice)).all()
        assert s.exec(select(PushOutbox)).one().status == "discarded"


def test_dispatch_rechecks_disabled_user_and_membership(client):
    from app.models import User
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import dispatch_push

    gid = group(client)
    with Session(db.engine) as s:
        s.add(
            PushDevice(
                user_id=2,
                endpoint="https://fcm.googleapis.com/receiver",
                p256dh="key",
                auth="key",
                session_hash="old",
            )
        )
        s.commit()
    client.post("/api/expenses", json=expense(gid))
    with Session(db.engine) as s:
        user = s.get(User, 2)
        user.is_active = False
        s.add(user)
        s.commit()

    def must_not_send(*_):
        pytest.fail("Disabled user received push")

    dispatch_push(db.engine, must_not_send)
    with Session(db.engine) as s:
        assert s.exec(select(PushOutbox)).one().status == "discarded"


def subscription_body(endpoint="https://fcm.googleapis.com/device"):
    import base64
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    key = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )

    def enc(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    return {"endpoint": endpoint, "keys": {"p256dh": enc(key), "auth": enc(b"0123456789abcdef")}}


def test_device_ownership_logout_and_account_switch(client, tmp_path, monkeypatch):
    from app.config import get_settings
    from app.push_models import PushDevice

    monkeypatch.setattr(get_settings(), "push_vapid_path", str(tmp_path / "vapid.pem"))
    client.base_url = "https://testserver"
    cfg = client.get("/api/push/config")
    assert cfg.status_code == 200 and set(cfg.json()) == {"public_key"}
    assert (tmp_path / "vapid.pem").stat().st_mode & 0o777 == 0o600
    body = subscription_body()
    assert client.post("/api/push/subscriptions", json=body).status_code == 200
    assert client.post("/api/push/test", json={"endpoint": body["endpoint"]}).json() == {
        "queued": True
    }
    assert client.post("/api/push/test", json={"endpoint": body["endpoint"]}).status_code == 429
    # Other browser without the signed cookie cannot capture this endpoint.
    cookie = client.cookies.get("split_push_device")
    client.cookies.delete("split_push_device")
    login = client.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.post("/api/push/subscriptions", json=body).status_code == 409
    assert (
        client.request(
            "DELETE",
            "/api/push/subscriptions",
            content=__import__("json").dumps({"endpoint": body["endpoint"]}),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 409
    )
    # Browser cookie proves same-device account switch and safely revokes previous consent.
    client.cookies.set("split_push_device", cookie, domain="testserver.local", path="/")
    login = client.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    with Session(db.engine) as s:
        assert not s.exec(select(PushDevice)).all()
    assert client.post("/api/push/subscriptions", json=body).status_code == 200
    # Same-account sign-in preserves device consent.
    login = client.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.post("/api/push/status", json={"endpoint": body["endpoint"]}).json()["enabled"]
    assert client.post("/api/auth/logout").status_code == 200
    with Session(db.engine) as s:
        assert not s.exec(select(PushDevice)).all()


def test_real_vapid_encryption_transport_disallows_redirects(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    import requests
    from app.config import get_settings
    from app.services.push_service import send_push

    monkeypatch.setattr(get_settings(), "push_vapid_path", str(tmp_path / "vapid.pem"))
    captured = []

    def transport(self, method, url, **kwargs):
        captured.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 201
        return response

    monkeypatch.setattr(requests.Session, "request", transport)
    assert send_push(subscription_body(), {"title": "Split Companion"}) == 201
    assert len(captured) == 1
    kwargs = captured[0][2]
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == 10
    assert kwargs["headers"]["authorization"].startswith("vapid ")
    assert b"Split Companion" not in kwargs["data"]


def test_dispatch_rechecks_group_membership(client):
    from app.models import GroupMember
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import dispatch_push

    gid = group(client)
    with Session(db.engine) as s:
        s.add(
            PushDevice(
                user_id=2,
                endpoint="https://fcm.googleapis.com/receiver",
                p256dh="key",
                auth="key",
                session_hash="old",
            )
        )
        s.commit()
    client.post("/api/expenses", json=expense(gid))
    with Session(db.engine) as s:
        member = s.exec(select(GroupMember).where(GroupMember.user_id == 2)).one()
        member.active = False
        s.add(member)
        s.commit()
    seen = []
    dispatch_push(db.engine, lambda *_: seen.append(True))
    assert not seen
    with Session(db.engine) as s:
        assert s.exec(select(PushOutbox)).one().status == "discarded"


def test_deleted_expense_id_reuse_cannot_replay_old_notification(client):
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import dispatch_push

    gid = group(client)
    with Session(db.engine) as s:
        s.add(
            PushDevice(
                user_id=2,
                endpoint="https://fcm.googleapis.com/receiver",
                p256dh="key",
                auth="key",
                session_hash="old",
            )
        )
        s.commit()
    eid = client.post("/api/expenses", json=expense(gid)).json()["id"]
    client.delete(f"/api/expenses/{eid}")
    client.post("/api/expenses", json=expense(gid))
    seen = []
    dispatch_push(db.engine, lambda sub, payload: seen.append(payload) or 201)
    with Session(db.engine) as s:
        rows = s.exec(select(PushOutbox)).all()
        assert len(rows) == 2
        assert sorted(r.status for r in rows) == ["discarded", "sent"]
    assert len(seen) == 1


def test_subscription_generation_notifies_once_and_import_does_not(client):
    from datetime import date
    from app.models import Subscription
    from app.push_models import PushDevice, PushOutbox
    from app.services.subscription_service import generate_due
    from app.services.records import create_expense
    from app.schemas import ExpenseCreate

    gid = group(client)
    with Session(db.engine) as s:
        s.add(
            PushDevice(
                user_id=2,
                endpoint="https://fcm.googleapis.com/receiver",
                p256dh="key",
                auth="key",
                session_hash="old",
            )
        )
        s.commit()
        create_expense(s, ExpenseCreate(**expense(gid)), 1, source="SPLITWISE")
        s.commit()
        assert not s.exec(select(PushOutbox)).all()
    response = client.post(
        "/api/subscriptions",
        json={
            "group_id": gid,
            "name": "Recurring",
            "amount_cents": 3000,
            "paid_by_user_id": 1,
            "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
            "start_date": "2090-01-01",
            "split_mode": "equal",
            "splits": [{"user_id": 1}, {"user_id": 2}],
        },
    )
    assert response.status_code == 201
    with Session(db.engine) as s:
        sub = s.get(Subscription, response.json()["id"])
        assert generate_due(s, sub, date(2090, 1, 1)) == 1
        s.commit()
        assert generate_due(s, sub, date(2090, 1, 1)) == 0
        assert len(s.exec(select(PushOutbox)).all()) == 1


def test_worker_stops_after_attempt_limit_and_ttl(client):
    from datetime import timedelta
    from app.models import now
    from app.push_models import PushDevice, PushOutbox
    from app.services.push_service import dispatch_push

    with Session(db.engine) as s:
        device = PushDevice(
            user_id=1,
            endpoint="https://fcm.googleapis.com/receiver",
            p256dh="key",
            auth="key",
            session_hash="old",
        )
        s.add(device)
        s.flush()
        for key, attempts, expires in [
            ("last-try", 4, now() + timedelta(hours=1)),
            ("exhausted", 5, now() + timedelta(hours=1)),
            ("expired", 0, now() - timedelta(seconds=1)),
        ]:
            s.add(
                PushOutbox(
                    device_id=device.id, event_key=key, attempts=attempts, expires_at=expires
                )
            )
        s.commit()
    seen = []
    dispatch_push(db.engine, lambda *_: seen.append(True) or 503)
    dispatch_push(db.engine, lambda *_: seen.append(True) or 201)
    assert len(seen) == 1
    with Session(db.engine) as s:
        assert sorted(row.status for row in s.exec(select(PushOutbox)).all()) == [
            "discarded",
            "discarded",
            "failed",
        ]


def test_whitelisted_push_host_cannot_resolve_to_private_address(tmp_path, monkeypatch):
    import socket
    import requests
    from app.config import get_settings
    from app.services.push_service import send_push

    monkeypatch.setattr(get_settings(), "push_vapid_path", str(tmp_path / "vapid.pem"))
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    calls = []

    def transport(*a, **k):
        calls.append(True)
        response = requests.Response()
        response.status_code = 201
        return response

    monkeypatch.setattr(requests.Session, "request", transport)
    with pytest.raises(ValueError):
        send_push(subscription_body(), {"title": "Split Companion"})
    assert calls == []
