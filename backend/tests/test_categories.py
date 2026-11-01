import io
import json
from datetime import date
from PIL import Image
from sqlmodel import Session
from app import db
from app.models import Expense, LegacyTransaction, LegacyTransactionEntry, ImportBatch, Subscription
from app.category_backfill import backfill
from app.services.category_service import classify
from test_api import group, expense


def category(client, slug):
    return next(c["id"] for c in client.get("/api/categories").json() if c["slug"] == slug)


def test_category_metadata_preserves_accounting_and_manual_clear(client):
    gid = group(client)
    e = client.post("/api/expenses", json=expense(gid)).json()
    before = client.get(f"/api/groups/{gid}/balances").json()
    cat = category(client, "pets")
    changed = client.patch(
        f"/api/expenses/{e['id']}/category", json={"category_id": cat, "icon_key": "chatgpt"}
    )
    assert changed.status_code == 200
    assert changed.json()["category_id"] == cat
    assert {k: v for k, v in changed.json().items() if k not in ("category_id", "icon_key")} == {
        k: v for k, v in e.items() if k not in ("category_id", "icon_key")
    }
    assert client.get(f"/api/groups/{gid}/balances").json() == before
    assert (
        client.patch(f"/api/expenses/{e['id']}/category", json={"amount_cents": 1}).status_code
        == 422
    )
    assert (
        client.patch(f"/api/expenses/{e['id']}/category", json={"category_id": 9999}).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/expenses/{e['id']}/category", json={"icon_key": "https://evil.test/icon.svg"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/expenses/{e['id']}/category", json={"category_id": None, "icon_key": None}
        ).status_code
        == 200
    )
    with Session(db.engine) as s:
        assert s.get(Expense, e["id"]).category_source == "manual"
        assert backfill(s) == []


def test_category_permissions_and_in_use_deletion(client):
    gid = group(client)
    created = client.post("/api/categories", json={"name": "Orto", "icon_key": "house"}).json()
    assert (
        client.patch(
            f"/api/categories/{category(client, 'pets')}",
            json={"name": "Other", "icon_key": "paw-print"},
        ).status_code
        == 200
    )
    eid = client.post("/api/expenses", json={**expense(gid), "category_id": created["id"]}).json()[
        "id"
    ]
    assert client.delete(f"/api/categories/{created['id']}").status_code == 409
    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/login", json={"username": "outsider", "password": "password12345"}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert (
        client.patch(f"/api/expenses/{eid}/category", json={"category_id": None}).status_code == 403
    )
    assert (
        client.patch(
            f"/api/categories/{created['id']}", json={"name": "No", "icon_key": "tag"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/categories/{created['id']}").status_code == 403


def test_upload_normalizes_and_protects_icons(client):
    image = Image.new("RGB", (500, 250), "red")
    raw = io.BytesIO()
    image.save(raw, "JPEG", comment=b"remove this metadata")
    result = client.post("/api/icons", files={"file": ("test.jpg", raw.getvalue(), "image/jpeg")})
    assert result.status_code == 201, result.text
    icon = result.json()
    response = client.get(f"/api/icons/{icon['id']}/image")
    assert response.headers["content-type"] == "image/png"
    converted = Image.open(io.BytesIO(response.content))
    assert converted.size == (128, 64)
    assert "comment" not in converted.info
    assert (
        client.post(
            "/api/icons", files={"file": ("x.png", b'<svg onload="alert(1)"/>', "image/png")}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/icons", files={"file": ("x.png", b"x" * (1024 * 1024 + 1))}).status_code
        == 413
    )
    assert (
        client.post("/api/icons", files={"file": ("x.png", b"x" * (2 * 1024 * 1024))}).status_code
        == 413
    )
    huge = io.BytesIO()
    Image.new("RGB", (2049, 1)).save(huge, "PNG")
    assert client.post("/api/icons", files={"file": ("x.png", huge.getvalue())}).status_code == 422
    cat = client.post(
        "/api/categories", json={"name": "Custom", "icon_key": icon["icon_key"]}
    ).json()
    assert client.delete(f"/api/icons/{icon['id']}").status_code == 409
    assert client.delete(f"/api/categories/{cat['id']}").status_code == 200
    assert client.delete(f"/api/icons/{icon['id']}").status_code == 200
    client.post("/api/auth/logout")
    assert client.get(f"/api/icons/{icon['id']}/image").status_code == 401


def test_legacy_backfill_provenance_and_idempotency(client):
    gid = group(client)
    with Session(db.engine) as s:
        batch = ImportBatch(
            format="CSV", original_filename="original.csv", file_hash="abc", uploaded_by_user_id=1
        )
        s.add(batch)
        s.flush()
        row = LegacyTransaction(
            group_id=gid,
            import_batch_id=batch.id,
            date=date(2025, 1, 1),
            description="Perlavet",
            cost_cents=1000,
            raw_metadata_json=json.dumps({"Categorie": "Spese mediche"}),
        )
        unknown = LegacyTransaction(
            group_id=gid,
            import_batch_id=batch.id,
            date=date(2025, 1, 1),
            description="Amazon",
            cost_cents=100,
        )
        s.add(row)
        s.add(unknown)
        s.flush()
        s.add(
            LegacyTransactionEntry(legacy_transaction_id=row.id, user_id=1, balance_delta_cents=500)
        )
        s.add(
            LegacyTransactionEntry(
                legacy_transaction_id=row.id, user_id=2, balance_delta_cents=-500
            )
        )
        s.commit()
        s.refresh(row)
        original = row.model_dump()
        lid = row.id
        report = backfill(s)
        assert len(report) == 1
        assert report[0]["category_id"] == category(client, "pets")
        s.commit()
        assert backfill(s) == []
        updated = s.get(LegacyTransaction, lid).model_dump()
        assert {
            k: v
            for k, v in updated.items()
            if k not in ("category_id", "icon_key", "category_source")
        } == {
            k: v
            for k, v in original.items()
            if k not in ("category_id", "icon_key", "category_source")
        }
    before = client.get(f"/api/groups/{gid}/balances").json()
    assert (
        client.patch(f"/api/legacy/{lid}/category", json={"category_id": None}).status_code == 200
    )
    assert client.get(f"/api/groups/{gid}/balances").json() == before
    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/login", json={"username": "outsider", "password": "password12345"}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert (
        client.patch(f"/api/legacy/{lid}/category", json={"category_id": None}).status_code == 403
    )


def test_subscription_generated_expenses_inherit_category_and_icon(client):
    gid = group(client)
    cat = category(client, "software")
    payload = {
        "group_id": gid,
        "name": "ChatGPT Pro",
        "amount_cents": 22000,
        "paid_by_user_id": 1,
        "recurrence_rule": "FREQ=MONTHLY;INTERVAL=1",
        "start_date": date.today().isoformat(),
        "splits": [{"user_id": 1}, {"user_id": 2}],
        "category_id": cat,
        "icon_key": "chatgpt",
    }
    response = client.post("/api/subscriptions", json=payload)
    assert response.status_code == 201, response.text
    sub = response.json()
    rows = client.get(f"/api/expenses?subscription_id={sub['id']}").json()
    assert len(rows) == 1 and rows[0]["category_id"] == cat and rows[0]["icon_key"] == "bot"
    assert (
        client.patch(
            f"/api/subscriptions/{sub['id']}", json={"category_id": None, "icon_key": None}
        ).status_code
        == 200
    )
    with Session(db.engine) as s:
        assert s.get(Subscription, sub["id"]).category_source == "manual"


def test_classifier_conservative_original_categories_and_pet_context():
    assert classify("Perlavet", {"Categorie": "Spese mediche"})[0] == "pets"
    assert classify("Sconosciuto", {"Categorie": "Generi alimentari"})[0] == "groceries"
    assert classify("Cibo", pet_context=True)[0] == "pets"
    assert classify("Cibo")[0] is None
    for description, slug in [
        ("Donna Pulzie", "home"),
        ("TARI", "bills"),
        ("Fluimucil", "health"),
        ("ChatGPT Pro", "chatgpt"),
        ("Vererinario", "pets"),
    ]:
        assert classify(description)[0] == slug
    for description in ("Amazon", "Toppa", "Lukketto"):
        assert classify(description)[0] is None


def test_explicit_uncategorized_creation_survives_backfill(client):
    gid = group(client)
    row = client.post(
        "/api/expenses",
        json={**expense(gid), "description": "ChatGPT Pro", "category_id": None, "icon_key": None},
    ).json()
    with Session(db.engine) as s:
        assert s.get(Expense, row["id"]).category_source == "manual"
        assert backfill(s) == []
