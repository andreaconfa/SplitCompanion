import os

os.environ.setdefault("SPLIT_COMPANION_SECRET_KEY", "test-secret-not-for-production-1234567890")
os.environ.setdefault("SPLIT_COMPANION_SCHEDULER", "false")
import pytest
from fastapi.testclient import TestClient
from app.main import app


def group(c):
    r = c.post("/api/groups", json={"name": "Casa", "member_ids": [2]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def expense(gid):
    return {
        "group_id": gid,
        "description": "Spesa",
        "amount_cents": 9000,
        "paid_by_user_id": 1,
        "expense_date": "2025-01-01",
        "split_mode": "single",
        "splits": [{"user_id": 2}],
    }


def test_expenses_balance_filters_settlement(client):
    c = client
    gid = group(c)
    r = c.post("/api/expenses", json=expense(gid))
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert c.get(f"/api/groups/{gid}/debts").json()[0]["amount_cents"] == 9000
    assert len(c.get("/api/expenses?participant_id=2&source=NATIVE").json()) == 1
    assert c.patch(f"/api/expenses/{eid}", json={"amount_cents": 10000}).status_code == 422
    assert c.patch(f"/api/expenses/{eid}", json={"notes": "nota"}).status_code == 200
    r = c.post(
        "/api/settlements",
        json={
            "group_id": gid,
            "paid_by_user_id": 2,
            "paid_to_user_id": 1,
            "amount_cents": 9000,
            "settlement_date": "2025-01-02",
        },
    )
    assert r.status_code == 201, r.text
    assert c.get(f"/api/groups/{gid}/debts").json() == []
    assert c.get("/api/dashboard/summary").status_code == 200
    assert c.delete(f"/api/settlements/{r.json()['id']}").status_code == 200
    assert c.delete(f"/api/expenses/{eid}").status_code == 200


def test_auth_csrf_cross_group_and_manipulation(client):
    c = client
    gid = group(c)
    eid = c.post("/api/expenses", json=expense(gid)).json()["id"]
    assert (
        c.post("/api/expenses", json={**expense(gid), "splits": [{"user_id": 3}]}).status_code
        == 422
    )
    assert (
        c.post("/api/groups", json={"name": "Bad"}, headers={"X-CSRF-Token": ""}).status_code == 403
    )
    assert (
        c.post(
            "/api/groups", json={"name": "Bad"}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    c.post("/api/auth/logout")
    assert c.get("/api/groups").status_code == 401
    r = c.post("/api/auth/login", json={"username": "outsider", "password": "password12345"})
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert c.get(f"/api/expenses/{eid}").status_code == 403
    assert c.get(f"/api/groups/{gid}/balances").status_code == 403
    assert (
        c.post("/api/imports/splitwise/analyze", files={"file": ("x.csv", b"bad")}).status_code
        == 403
    )
    assert c.get("/api/groups").json() == []


def test_subscription_advance_refund_and_payer_lock(client):
    c = client
    gid = group(c)
    r = c.post(
        "/api/subscriptions",
        json={
            "group_id": gid,
            "name": "Netflix",
            "amount_cents": 3000,
            "paid_by_user_id": 1,
            "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
            "start_date": "2090-01-01",
            "split_mode": "equal",
            "splits": [{"user_id": 1}, {"user_id": 2}],
        },
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = c.post(
        f"/api/subscriptions/{sid}/advances",
        json={"user_id": 2, "amount_cents": 12000, "settlement_date": "2025-01-01"},
    )
    assert r.status_code == 201, r.text
    assert c.get(f"/api/subscriptions/{sid}/credits").json()[0]["remaining_cents"] == 12000
    assert c.patch(f"/api/subscriptions/{sid}", json={"paid_by_user_id": 2}).status_code == 422
    assert (
        c.post(
            f"/api/subscriptions/{sid}/refunds",
            json={"user_id": 2, "amount_cents": 13000, "settlement_date": "2025-01-02"},
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/subscriptions/{sid}/refunds",
            json={"user_id": 2, "amount_cents": 12000, "settlement_date": "2025-01-02"},
        ).status_code
        == 201
    )
    assert c.patch(f"/api/subscriptions/{sid}", json={"paid_by_user_id": 2}).status_code == 200
    assert c.post(f"/api/subscriptions/{sid}/pause").json()["active"] is False
    assert c.post(f"/api/subscriptions/{sid}/resume").json()["active"] is True


@pytest.mark.parametrize("resource", ["expenses", "settlements", "subscriptions"])
def test_cross_group_mutations(client, resource):
    c = client
    gid = group(c)
    if resource == "expenses":
        body = expense(gid)
    elif resource == "settlements":
        body = {
            "group_id": gid,
            "paid_by_user_id": 2,
            "paid_to_user_id": 1,
            "amount_cents": 100,
            "settlement_date": "2025-01-01",
        }
    else:
        body = {
            "group_id": gid,
            "name": "Monthly",
            "amount_cents": 100,
            "paid_by_user_id": 1,
            "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
            "start_date": "2090-01-01",
            "split_mode": "single",
            "splits": [{"user_id": 2}],
        }
    r = c.post("/api/" + resource, json=body)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    login = c.post("/api/auth/login", json={"username": "outsider", "password": "password12345"})
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert c.get(f"/api/{resource}/{rid}").status_code == 403
    assert c.delete(f"/api/{resource}/{rid}").status_code == 403
    if resource == "subscriptions":
        assert (
            c.post(
                f"/api/subscriptions/{rid}/advances",
                json={"user_id": 2, "amount_cents": 100, "settlement_date": "2025-01-01"},
            ).status_code
            == 403
        )


@pytest.mark.parametrize("amount", [1.5, "100", True, 0, -1, 10**13])
def test_reject_bad_money(client, amount):
    c = client
    gid = group(c)
    assert c.post("/api/expenses", json={**expense(gid), "amount_cents": amount}).status_code == 422


def test_user_reset_invalidates_session_and_disable(client):
    c = client
    with TestClient(app) as other:
        r = other.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
        assert r.status_code == 200
        assert c.patch("/api/users/2", json={"password": "changedpassword123"}).status_code == 200
        assert other.get("/api/auth/me").status_code == 401
    assert c.patch("/api/users/2", json={"is_active": False}).status_code == 200
    assert (
        c.post(
            "/api/auth/login", json={"username": "laura", "password": "changedpassword123"}
        ).status_code
        == 401
    )


def test_health_and_no_secret_in_users(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert all("password_hash" not in u for u in client.get("/api/users").json())
    assert client.get("/api/not-a-route").status_code == 404


def test_chunked_import_upload_size_limit_before_parser(client):
    response = client.post(
        "/api/imports/splitwise/analyze",
        content=(b"x" * (1024 * 1024) for _ in range(12)),
        headers={"Content-Type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 413


def test_auth_exposes_configured_timezone(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "timezone", "Pacific/Honolulu")
    assert client.get("/api/auth/me").json()["timezone"] == "Pacific/Honolulu"
    response = client.post(
        "/api/auth/login", json={"username": "alex", "password": "password12345"}
    )
    assert response.json()["timezone"] == "Pacific/Honolulu"


def test_balance_reads_one_snapshot_during_concurrent_import(client):
    from sqlalchemy import event, text
    from sqlmodel import Session
    from app import db
    from app.models import Expense, ExpenseSplit, Settlement
    from datetime import date

    gid = group(client)
    inserted = False

    def concurrent_commit(connection, cursor, statement, parameters, context, many):
        nonlocal inserted
        if not inserted and statement.startswith("SELECT") and "FROM expense " in statement:
            inserted = True
            with Session(db.engine) as writer:
                writer.execute(text("BEGIN IMMEDIATE"))
                e = Expense(
                    group_id=gid,
                    description="Atomic pair",
                    amount_cents=100,
                    paid_by_user_id=1,
                    expense_date=date.today(),
                    created_by_user_id=1,
                )
                writer.add(e)
                writer.flush()
                writer.add(ExpenseSplit(expense_id=e.id, user_id=2, amount_cents=100))
                writer.add(
                    Settlement(
                        group_id=gid,
                        paid_by_user_id=2,
                        paid_to_user_id=1,
                        amount_cents=100,
                        settlement_date=date.today(),
                        created_by_user_id=1,
                    )
                )
                writer.commit()

    event.listen(db.engine, "after_cursor_execute", concurrent_commit)
    try:
        result = client.get(f"/api/groups/{gid}/balances")
        assert result.status_code == 200
        assert inserted
        assert all(row["balance_cents"] == 0 for row in result.json())
    finally:
        event.remove(db.engine, "after_cursor_execute", concurrent_commit)
