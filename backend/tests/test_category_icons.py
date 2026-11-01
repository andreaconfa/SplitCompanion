"""Category icons remain authoritative across old clients and historical rows."""

from datetime import date
import io

import pytest
from PIL import Image
from sqlmodel import Session, select

from app import db
from app.models import Expense, ImportBatch, LegacyTransaction, Subscription
from app.services.category_service import classify
from test_api import expense, group
from test_categories import category


def login_as(client, username):
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "password12345"}
    )
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def test_category_mutations_are_admin_only_but_reads_are_shared(client):
    cid = category(client, "pets")
    assert (
        client.patch(
            f"/api/categories/{cid}", json={"name": "Animali", "icon_key": "heart-pulse"}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/categories/{cid}").status_code == 409
    raw = io.BytesIO()
    Image.new("RGB", (2, 2)).save(raw, "PNG")
    icon = client.post("/api/icons", files={"file": ("pet.png", raw.getvalue())}).json()
    login_as(client, "laura")
    assert client.get("/api/categories").status_code == 200
    assert client.get(f"/api/icons/{icon['id']}/image").status_code == 200
    assert (
        client.post("/api/categories", json={"name": "Forbidden", "icon_key": "tag"}).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/categories/{cid}", json={"name": "Forbidden", "icon_key": "tag"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/categories/{cid}").status_code == 403
    assert client.post("/api/icons", files={"file": ("pet.png", raw.getvalue())}).status_code == 403
    assert client.delete(f"/api/icons/{icon['id']}").status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/categories").status_code == 401


@pytest.mark.parametrize("icon", [None, "", "missing", "upload:999999"])
def test_category_rejects_invalid_icon(client, icon):
    assert (
        client.post("/api/categories", json={"name": "Invalid", "icon_key": icon}).status_code
        == 422
    )


def test_category_requires_icon(client):
    assert client.post("/api/categories", json={"name": "Missing"}).status_code == 422


def test_record_icons_follow_category_edits_and_ignore_legacy_overrides(client):
    gid = group(client)
    cid = category(client, "pets")
    created = client.post(
        "/api/expenses", json={**expense(gid), "category_id": cid, "icon_key": "invalid-old-icon"}
    )
    assert created.status_code == 201, created.text
    eid = created.json()["id"]
    assert created.json()["icon_key"] == "paw-print"
    with Session(db.engine) as s:
        e = s.get(Expense, eid)
        assert e.icon_key is None
        e.icon_key = "chatgpt"
        s.add(e)
        batch = ImportBatch(
            format="CSV", original_filename="old.csv", file_hash="old", uploaded_by_user_id=1
        )
        s.add(batch)
        s.flush()
        legacy = LegacyTransaction(
            group_id=gid,
            import_batch_id=batch.id,
            date=date.today(),
            description="Pet",
            cost_cents=100,
            category_id=cid,
            icon_key="chatgpt",
        )
        s.add(legacy)
        s.commit()
        s.refresh(legacy)
        lid = legacy.id
    assert client.get(f"/api/expenses/{eid}").json()["icon_key"] == "paw-print"
    assert client.get(f"/api/legacy/{lid}").json()["icon_key"] == "paw-print"
    changed = client.patch(
        f"/api/categories/{cid}", json={"name": "Animali", "icon_key": "heart-pulse"}
    )
    assert changed.status_code == 200
    assert client.get(f"/api/expenses/{eid}").json()["icon_key"] == "heart-pulse"
    assert client.get(f"/api/legacy/{lid}").json()["icon_key"] == "heart-pulse"
    for path, model, rid in [("expenses", Expense, eid), ("legacy", LegacyTransaction, lid)]:
        response = client.patch(
            f"/api/{path}/{rid}/category",
            json={"category_id": None, "icon_key": "invalid-old-icon"},
        )
        assert response.status_code == 200
        assert response.json()["icon_key"] is None
        with Session(db.engine) as s:
            row = s.get(model, rid)
            assert row.icon_key is None
            assert row.category_source == "manual"


def test_subscription_and_generated_expense_store_no_override(client):
    gid = group(client)
    cid = category(client, "software")
    response = client.post(
        "/api/subscriptions",
        json={
            "group_id": gid,
            "name": "ChatGPT",
            "amount_cents": 2000,
            "paid_by_user_id": 1,
            "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
            "start_date": date.today().isoformat(),
            "splits": [{"user_id": 1}, {"user_id": 2}],
            "category_id": cid,
            "icon_key": "invalid-old-icon",
        },
    )
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    assert response.json()["icon_key"] == "bot"
    with Session(db.engine) as s:
        sub = s.get(Subscription, sid)
        assert sub.icon_key is None
        assert s.exec(select(Expense).where(Expense.subscription_id == sid)).one().icon_key is None
        sub.icon_key = "chatgpt"
        s.add(sub)
        s.commit()
    assert client.get(f"/api/subscriptions/{sid}").json()["icon_key"] == "bot"
    changed = client.patch(
        f"/api/subscriptions/{sid}", json={"category_id": None, "icon_key": "unknown"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["icon_key"] is None
    with Session(db.engine) as s:
        assert s.get(Subscription, sid).icon_key is None
        assert s.get(Subscription, sid).category_source == "manual"


@pytest.mark.parametrize(
    "description,slug",
    [
        ("Caricatore Apple Watch", "electronics"),
        ("Chiavetta USB", "electronics"),
        ("Cover telefono", "electronics"),
        ("Cover iPhone 17 Pro Max", "electronics"),
        ("Spazzolino", "personal-care"),
        ("Bagnoschiuma", "personal-care"),
        ("Coso Capelli", "personal-care"),
        ("Rimborso farmaco", "transfers"),
        ("Restituzione", "transfers"),
        ("Pareggio", "transfers"),
        ("Prestito", "transfers"),
        ("Finocchi", "groceries"),
        ("ChatGPT Pro", "chatgpt"),
        ("Amazon", None),
        ("Toppa", None),
        ("Lukketto", None),
        ("Zaino", None),
    ],
)
def test_precise_classification_uses_category_without_icon_override(description, slug):
    actual, icon, _ = classify(description)
    assert actual == slug
    assert icon is None


def test_pet_context_classifies_backpack():
    assert classify("Zaino", pet_context=True)[0] == "pets"


def test_full_expense_edit_ignores_and_clears_old_icon(client):
    gid = group(client)
    cid = category(client, "pets")
    eid = client.post("/api/expenses", json={**expense(gid), "category_id": cid}).json()["id"]
    with Session(db.engine) as s:
        row = s.get(Expense, eid)
        row.icon_key = "chatgpt"
        s.add(row)
        s.commit()
    response = client.patch(f"/api/expenses/{eid}", json={"notes": "Edited", "icon_key": "unknown"})
    assert response.status_code == 200
    assert response.json()["icon_key"] == "paw-print"
    with Session(db.engine) as s:
        row = s.get(Expense, eid)
        assert row.icon_key is None
        assert row.category_source == "manual"


def test_generated_expense_ignores_historical_subscription_override(client):
    from app.services.subscription_service import generate_due

    gid = group(client)
    cid = category(client, "software")
    response = client.post(
        "/api/subscriptions",
        json={
            "group_id": gid,
            "name": "Software",
            "amount_cents": 2000,
            "paid_by_user_id": 1,
            "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
            "start_date": "2099-01-01",
            "splits": [{"user_id": 1}, {"user_id": 2}],
            "category_id": cid,
        },
    )
    assert response.status_code == 201
    sid = response.json()["id"]
    with Session(db.engine) as s:
        sub = s.get(Subscription, sid)
        sub.icon_key = "chatgpt"
        s.add(sub)
        assert generate_due(s, sub, date(2099, 1, 1)) == 1
        generated = s.exec(select(Expense).where(Expense.subscription_id == sid)).one()
        assert generated.icon_key is None
        assert generated.category_id == cid
        s.commit()
    assert client.get(f"/api/expenses?subscription_id={sid}").json()[0]["icon_key"] == "bot"
