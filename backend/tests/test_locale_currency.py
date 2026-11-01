"""Public locale and administrator currency contracts; accounting stays unchanged."""

from datetime import date

import pytest
from sqlmodel import Session

from app import db
from app.models import Subscription
from app.services.subscription_service import generate_due
from test_api import expense, group
from test_push import subscription_body


def test_default_currency_only_applies_to_new_records(client):
    gid = group(client)
    old = client.post("/api/expenses", json=expense(gid)).json()
    sub_body = dict(
        group_id=gid,
        name="Original",
        amount_cents=1200,
        paid_by_user_id=1,
        recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
        start_date="2090-01-01",
        splits=[{"user_id": 1}, {"user_id": 2}],
    )
    old_sub = client.post("/api/subscriptions", json=sub_body).json()
    saved = client.patch("/api/admin/settings", json={"default_currency": "USD"})
    assert saved.status_code == 200
    assert saved.json()["default_currency"] == "USD"
    assert client.get("/api/meta").json()["default_currency"] == "USD"
    assert client.get("/api/auth/me").json()["default_currency"] == "USD"
    assert client.get("/api/admin/settings").json()["default_currency"] == "USD"
    assert client.post("/api/expenses", json=expense(gid)).json()["currency"] == "USD"
    assert client.post("/api/subscriptions", json=sub_body).json()["currency"] == "USD"
    assert (
        client.post("/api/expenses", json={**expense(gid), "currency": "GBP"}).json()["currency"]
        == "GBP"
    )
    payment = client.post(
        "/api/settlements",
        json=dict(
            group_id=gid,
            paid_by_user_id=2,
            paid_to_user_id=1,
            amount_cents=100,
            settlement_date="2090-01-01",
        ),
    )
    assert payment.json()["currency"] == "USD"
    assert (
        client.patch(f"/api/expenses/{old['id']}", json={"notes": "Keep me"}).json()["currency"]
        == "EUR"
    )
    assert (
        client.patch(f"/api/subscriptions/{old_sub['id']}", json={"description": "Keep me"}).json()[
            "currency"
        ]
        == "EUR"
    )
    with Session(db.engine) as session:
        generate_due(session, session.get(Subscription, old_sub["id"]), date(2090, 1, 1))
        session.commit()
    generated = client.get(f"/api/expenses?subscription_id={old_sub['id']}").json()
    assert len(generated) == 1 and generated[0]["currency"] == "EUR"
    assert client.get(f"/api/expenses/{old['id']}").json()["amount_cents"] == 9000
    assert client.get(f"/api/subscriptions/{old_sub['id']}").json()["currency"] == "EUR"


def test_currency_settings_require_admin_csrf_and_valid_code(client):
    assert client.patch("/api/admin/settings", json={"default_currency": "XYZ"}).status_code == 422
    assert (
        client.patch(
            "/api/admin/settings", json={"default_currency": "USD"}, headers={"X-CSRF-Token": ""}
        ).status_code
        == 403
    )
    assert client.get("/api/admin/settings").json()["default_currency"] == "EUR"
    login = client.post("/api/auth/login", json={"username": "laura", "password": "password12345"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get("/api/admin/settings").status_code == 403
    assert client.patch("/api/admin/settings", json={"default_currency": "USD"}).status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/admin/settings").status_code == 401
    assert client.get("/api/meta").json()["default_currency"] == "EUR"


@pytest.mark.parametrize(
    "header, expected",
    [(None, "en"), ("it-IT,it;q=0.9,en;q=0.5", "it"), ("fr", "en"), ("it;q=0.1,en;q=0.9", "en")],
)
def test_errors_use_requested_language_without_changing_user_data(client, header, expected):
    if header:
        client.headers["Accept-Language"] = header
    gid = group(client)
    assert client.get(f"/api/groups/{gid}").json()["name"] == "Casa"
    response = client.get("/api/expenses/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Elemento non trovato." if expected == "it" else "Item not found."
    )
    assert response.headers["Content-Language"] == expected
    client.post("/api/auth/logout")
    denied = client.get("/api/groups")
    assert denied.status_code == 401
    assert denied.json()["detail"] == (
        "Accedi per continuare." if expected == "it" else "Sign in to continue."
    )


def test_push_uses_each_devices_language_and_refreshes_it(client):
    from app.services.push_service import dispatch_push

    client.base_url = "https://testserver"
    english = subscription_body("https://fcm.googleapis.com/english")
    italian = subscription_body("https://fcm.googleapis.com/italian")
    # Clear browser binding to represent two independent browsers.
    assert client.post("/api/push/subscriptions", json=english).status_code == 200
    client.cookies.delete("split_push_device")
    assert (
        client.post(
            "/api/push/subscriptions", json=italian, headers={"Accept-Language": "it"}
        ).status_code
        == 200
    )
    for body in [english, italian]:
        assert client.post("/api/push/test", json={"endpoint": body["endpoint"]}).status_code == 200
    delivered = {}
    dispatch_push(
        db.engine,
        lambda subscription, payload: (
            delivered.update({subscription["endpoint"]: payload}) or 201
        ),
    )
    assert delivered[english["endpoint"]]["body"] == "Notifications are enabled on this device."
    assert delivered[english["endpoint"]].get("language") == "en"
    assert delivered[italian["endpoint"]]["body"] == "Le notifiche su questo dispositivo sono attive."
    assert delivered[italian["endpoint"]].get("language") == "it"
    assert (
        client.post("/api/push/subscriptions", json={**italian, "language": "en"}).status_code
        == 200
    )
    from app.push_models import PushDevice
    from sqlmodel import select

    with Session(db.engine) as session:
        assert (
            session.exec(select(PushDevice).where(PushDevice.endpoint == italian["endpoint"]))
            .one()
            .language
            == "en"
        )


def test_import_reports_follow_current_language_without_translating_names(client):
    content = b"Date,Description,Cost,Currency,Alex,Laura\n2025-01-01,Casa,10.00,USD,5.00,-5.00\n"
    created = client.post("/api/imports/splitwise/analyze", files={"file": ("Casa.csv", content)})
    assert created.status_code == 200
    report = created.json()
    assert report["groups"] == ["Casa"]
    assert report["warnings"] == ["Currencies kept separate, without conversion: USD"]
    italian = client.get(f"/api/imports/{report['id']}", headers={"Accept-Language": "it"}).json()
    assert italian["groups"] == ["Casa"]
    assert italian["warnings"] == ["Valute conservate separatamente, senza conversione: USD"]
    invalid = client.post(
        "/api/imports/splitwise/analyze", files={"file": ("bad.csv", b"wrong,header\n1,2")}
    ).json()
    assert invalid["errors"] == [
        "Unexpected header: Date, Description, Cost and Currency are required."
    ]


def test_validation_and_middleware_errors_are_localized(client):
    for locale, fragment in [("en", "Invalid data."), ("it", "Dati non validi.")]:
        client.headers["Accept-Language"] = locale
        response = client.post("/api/groups", json={})
        assert response.status_code == 422
        assert response.json()["detail"].startswith(fragment)
        response = client.post(
            "/api/groups", json={"name": "Test"}, headers={"Origin": "https://evil.test"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Request origin not allowed."
            if locale == "en"
            else "Origine della richiesta non consentita."
        )


def test_currency_migration_preserves_rows_and_default_survives_restart(tmp_path, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from app.models import Expense, Group, InstanceSettings, User
    from app.push_models import PushDevice
    from app.services.instance_settings import default_currency

    path = str(tmp_path / "upgraded.db")
    engine = db.make_engine(path)
    monkeypatch.setattr(db, "engine", engine)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "0007_setup")
    with Session(engine) as session:
        user = User(username="legacy", display_name="Casa", password_hash="disabled")
        session.add(user)
        session.flush()
        group_record = Group(name="Casa", created_by_user_id=user.id)
        session.add(group_record)
        session.flush()
        row = Expense(
            group_id=group_record.id,
            description="Casa",
            amount_cents=12345,
            currency="GBP",
            paid_by_user_id=user.id,
            created_by_user_id=user.id,
            expense_date=date(2020, 1, 1),
        )
        session.add(row)
        session.execute(
            text(
                "INSERT INTO pushdevice (created_at, user_id, endpoint, p256dh, auth, session_hash) VALUES (CURRENT_TIMESTAMP, :user, 'https://fcm.googleapis.com/old', 'key', 'key', 'session')"
            ),
            {"user": user.id},
        )
        session.commit()
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.get(Expense, 1).currency == "GBP"
        assert session.get(Expense, 1).amount_cents == 12345
        assert session.get(PushDevice, 1).language == "en"
        assert default_currency(session) == "EUR"
        settings = session.get(InstanceSettings, 1)
        settings.default_currency = "USD"
        session.add(settings)
        session.commit()
    engine.dispose()
    reopened = db.make_engine(path)
    with Session(reopened) as session:
        assert default_currency(session) == "USD"
        assert session.get(Expense, 1).currency == "GBP"
    reopened.dispose()


def test_builtin_category_display_is_localized_and_custom_names_are_preserved(client):
    gid = group(client)
    categories = client.get("/api/categories").json()
    home = next(row for row in categories if row["slug"] == "home")
    assert home["name"] == "Casa"  # Editable stored value never changes with locale.
    assert home.get("display_name") == "Home"
    client.post("/api/expenses", json={**expense(gid), "category_id": home["id"]})
    client.post("/api/expenses", json=expense(gid))
    stats = client.get("/api/dashboard/statistics?month=2025-01").json()
    assert {row["name"] for row in stats["categories"]} == {"Home", "Uncategorized"}
    italian = client.get("/api/categories", headers={"Accept-Language": "it"}).json()
    assert next(row for row in italian if row["id"] == home["id"])["display_name"] == "Casa"
    changed = client.patch(
        f"/api/categories/{home['id']}", json={"name": "My Casa", "icon_key": "house"}
    )
    assert changed.json()["display_name"] == "My Casa"
    custom = client.post("/api/categories", json={"name": "Casa", "icon_key": "tag"}).json()
    assert custom["display_name"] == "Casa"
    assert any(
        row["name"] == "My Casa"
        for row in client.get("/api/dashboard/statistics?month=2025-01").json()["categories"]
    )
