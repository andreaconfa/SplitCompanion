from datetime import date, datetime
import pytest
from sqlmodel import Session, select
from app import db
from app.models import (
    Category,
    Expense,
    Group,
    GroupMember,
    ImportBatch,
    LegacyTransaction,
    Settlement,
    Subscription,
    SubscriptionOccurrence,
)

URL = "/api/dashboard/statistics"


def test_empty_and_auth(client):
    r = client.get(URL)
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["total_cents"] == d["summary"]["expense_count"] == 0
    assert d["currencies"] == ["EUR"]
    assert len(d["trend"]) == 6
    assert d["comparison"]["change_percent"] is None
    client.post("/api/auth/logout")
    assert client.get(URL).status_code == 401


def freeze(monkeypatch, instant="2024-03-31T22:30:00+00:00"):
    from app.config import get_settings
    from app.services import statistics_service

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(instant).astimezone(tz)

    monkeypatch.setattr(statistics_service, "datetime", Clock)
    monkeypatch.setattr(get_settings(), "timezone", "Europe/Rome")


def seed():
    with Session(db.engine) as s:
        groups = [
            Group(name=n, created_by_user_id=1, archived=n == "Archive")
            for n in ["Home", "Archive", "Secret"]
        ]
        s.add_all(groups)
        s.flush()
        for g in groups[:2]:
            s.add(GroupMember(group_id=g.id, user_id=1))
        batch = ImportBatch(
            format="CSV", original_filename="test.csv", file_hash="test", uploaded_by_user_id=1
        )
        food = Category(name="Food", slug="statistics-test-food", icon_key="cart")
        transfer = s.exec(select(Category).where(Category.slug == "transfers")).one()
        s.add_all([batch, food, transfer])
        s.flush()
        ids = [g.id for g in groups] + [batch.id, food.id, transfer.id]
        s.commit()
        return ids


def expense(s, gid, day, amount, **kw):
    e = Expense(
        group_id=gid,
        description="Expense",
        amount_cents=amount,
        expense_date=date.fromisoformat(day),
        paid_by_user_id=1,
        created_by_user_id=1,
        **kw,
    )
    s.add(e)
    return e


def test_scope_coverage_currencies_and_occurrences(client, monkeypatch):
    freeze(monkeypatch)
    home, archive, secret, batch, food, transfer = seed()
    with Session(db.engine) as s:
        expense(s, home, "2024-03-02", 100, category_id=food)
        expense(s, home, "2024-03-02", 201, source="SPLITWISE", category_id=transfer)
        expense(s, archive, "2024-03-03", 300)
        expense(s, home, "2024-03-03", 900, currency="USD")
        expense(s, secret, "2024-01-01", 99999, currency="GBP")
        expense(s, home, "2024-04-02", 99999, currency="JPY")
        for amount, cat in [
            (400, food),
            (500, transfer),
            (None, transfer),
            (None, None),
            (0, None),
            (-200, None),
        ]:
            s.add(
                LegacyTransaction(
                    group_id=home,
                    import_batch_id=batch,
                    date=date(2024, 3, 4),
                    description="Legacy",
                    cost_cents=amount,
                    category_id=cat,
                )
            )
        sub = Subscription(
            group_id=home,
            name="Monthly",
            amount_cents=9999,
            paid_by_user_id=1,
            recurrence_rule="FREQ=MONTHLY",
            start_date=date(2024, 3, 1),
            next_occurrence_date=date(2024, 4, 1),
            created_by_user_id=1,
        )
        s.add(sub)
        s.flush()
        e = expense(
            s,
            home,
            "2024-03-05",
            99,
            subscription_id=sub.id,
            subscription_occurrence_date=date(2024, 3, 5),
        )
        s.flush()
        s.add(
            SubscriptionOccurrence(
                subscription_id=sub.id, occurrence_date=date(2024, 3, 5), expense_id=e.id
            )
        )
        for kind in ["GENERAL", "SUBSCRIPTION_ADVANCE", "SUBSCRIPTION_REFUND"]:
            s.add(
                Settlement(
                    group_id=home,
                    paid_by_user_id=1,
                    paid_to_user_id=2,
                    amount_cents=8000,
                    settlement_date=date(2024, 3, 6),
                    kind=kind,
                    created_by_user_id=1,
                )
            )
        s.commit()
    r = client.get(URL, params={"month": "2024-03"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["current_month"] == "2024-04"
    assert d["currencies"] == ["EUR", "USD"]
    assert d["available_months"] == ["2024-04", "2024-03"]
    assert d["summary"] == dict(
        total_cents=1100,
        expense_count=5,
        average_cents=220,
        daily_average_cents=35,
        native_total_cents=700,
        legacy_total_cents=400,
    )
    assert d["coverage"] == dict(
        legacy_included_count=1,
        legacy_excluded_count=5,
        legacy_transfers_excluded_count=2,
        legacy_missing_cost_count=1,
        legacy_nonpositive_count=2,
    )
    assert [r["total_cents"] for r in d["categories"]] == [500, 399, 201]
    assert d["categories"][1]["name"] == "Senza categoria"
    assert sum(r["total_cents"] for r in d["groups"]) == 1100
    assert len(d["daily"]) == 31
    assert d["daily"][0]["cumulative_cents"] == 0
    assert d["daily"][-1]["cumulative_cents"] == 1100
    assert [r["month"] for r in d["trend"]] == [
        "2023-10",
        "2023-11",
        "2023-12",
        "2024-01",
        "2024-02",
        "2024-03",
    ]
    assert [r["total_cents"] for r in d["trend"]] == [0, 0, 0, 0, 0, 1100]
    assert (
        client.get(URL, params={"month": "2024-03", "group_id": home}).json()["summary"][
            "total_cents"
        ]
        == 800
    )
    assert (
        client.get(URL, params={"month": "2024-03", "currency": "USD"}).json()["summary"][
            "total_cents"
        ]
        == 900
    )
    assert client.get(URL, params={"group_id": secret}).status_code == 403
    assert client.get(URL, params={"group_id": 999999}).status_code == 403


@pytest.mark.parametrize(
    "today,month,end,previous_end,days",
    [
        ("2024-03-31", "2024-03", "2024-03-31", "2024-02-29", 31),
        ("2024-03-10", "2024-03", "2024-03-10", "2024-02-10", 10),
        ("2024-03-10", "2024-02", "2024-02-29", "2024-01-31", 29),
        ("2025-01-02", "2025-01", "2025-01-02", "2024-12-02", 2),
    ],
)
def test_periods(client, monkeypatch, today, month, end, previous_end, days):
    freeze(monkeypatch, today + "T12:00:00+00:00")
    d = client.get(URL, params={"month": month}).json()
    assert d["period"]["end"] == end
    assert d["period"]["days"] == days
    assert d["comparison"]["end"] == previous_end
    assert len(d["daily"]) == days
    assert d["trend"][-1]["is_partial"] == (month == today[:7])


def test_comparison_rounding_and_future_exclusion(client, monkeypatch):
    freeze(monkeypatch, "2024-03-02T12:00:00+00:00")
    home, *_ = seed()
    with Session(db.engine) as s:
        for day, amount in [
            ("2024-02-02", 100),
            ("2024-02-03", 9999),
            ("2024-03-01", 1),
            ("2024-03-02", 100),
            ("2024-03-03", 99999),
        ]:
            expense(s, home, day, amount)
        s.commit()
    d = client.get(URL).json()
    assert d["summary"]["total_cents"] == 101
    assert d["summary"]["average_cents"] == d["summary"]["daily_average_cents"] == 51
    assert d["comparison"]["total_cents"] == 100
    assert d["comparison"]["change_cents"] == d["comparison"]["change_percent"] == 1
    assert d["trend"][-2]["total_cents"] == 10099


@pytest.mark.parametrize(
    "params",
    [
        {"month": "2024-00"},
        {"month": "2024-13"},
        {"month": "1899-12"},
        {"month": "2024-4"},
        {"month": "9999-01"},
        {"currency": "eur"},
        {"currency": "EURO"},
    ],
)
def test_invalid_filters(client, params):
    assert client.get(URL, params=params).status_code == 422


def test_currency_default_empty_filter_and_earliest_month(client, monkeypatch):
    freeze(monkeypatch)
    home, archive, secret, batch, *_ = seed()
    with Session(db.engine) as s:
        expense(s, home, "2024-03-01", 100, currency="USD")
        expense(s, secret, "2024-02-01", 100, currency="EUR")
        expense(s, home, "1899-12-01", 100, currency="USD")
        s.add(
            LegacyTransaction(
                group_id=home,
                import_batch_id=batch,
                date=date(2090, 1, 1),
                description="Future",
                cost_cents=100,
                currency="CHF",
            )
        )
        s.commit()
    d = client.get(URL, params={"month": "2024-03"}).json()
    assert d["currency"] == "USD"
    assert d["currencies"] == ["USD"]
    assert d["available_months"] == ["2024-04", "2024-03"]
    d = client.get(URL, params={"month": "1900-01", "currency": "EUR"}).json()
    assert d["summary"]["total_cents"] == 0
    assert d["period"]["days"] == 31
    assert d["trend"][0]["month"] == "1899-08"
    d = client.get(URL, params={"group_id": archive}).json()
    assert d["currencies"] == ["EUR"]
    assert d["available_months"] == ["2024-04"]
