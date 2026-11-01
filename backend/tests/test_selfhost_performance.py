from datetime import date
import json
import pytest
from sqlalchemy import event, insert
from sqlmodel import Session, select
from app import db
from app.models import Expense, ExpenseSplit, Group, GroupMember, ImportBatch
from app.services.balance_service import balances


def seed_history(count):
    with Session(db.engine) as s:
        group = Group(name="Large history", created_by_user_id=1)
        s.add(group)
        s.flush()
        gid = group.id
        s.add_all([GroupMember(group_id=gid, user_id=i) for i in (1, 2)])
        s.execute(
            insert(Expense),
            [
                dict(
                    id=i,
                    group_id=gid,
                    description="Expense",
                    amount_cents=101,
                    currency="EUR",
                    expense_date=date(2024, 1, 1),
                    paid_by_user_id=1,
                    created_by_user_id=1,
                )
                for i in range(1, count + 1)
            ],
        )
        s.execute(
            insert(ExpenseSplit),
            [dict(expense_id=i, user_id=2, amount_cents=101) for i in range(1, count + 1)],
        )
        s.commit()
        return gid


def test_fifty_thousand_expenses_bounded_balance_queries(client):
    gid = seed_history(50000)
    queries = []

    def track(*args):
        queries.append(args[2])
        assert len(queries) <= 10, "Balance queries must not grow with history"

    event.listen(db.engine, "before_cursor_execute", track)
    try:
        with Session(db.engine) as s:
            assert balances(s, gid) == [
                dict(user_id=1, currency="EUR", balance_cents=5050000),
                dict(user_id=2, currency="EUR", balance_cents=-5050000),
            ]
    finally:
        event.remove(db.engine, "before_cursor_execute", track)
    queries.clear()

    def track(*args):
        queries.append(args[2])
        assert len(queries) <= 12

    event.listen(db.engine, "before_cursor_execute", track)
    try:
        response = client.get("/api/dashboard/statistics?month=2024-01")
    finally:
        event.remove(db.engine, "before_cursor_execute", track)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_cents"] == 5050000
    assert data["summary"]["expense_count"] == 50000
    assert data["summary"]["average_cents"] == 101
    assert data["daily"][0]["total_cents"] == 5050000
    assert data["trend"][-1]["count"] == 50000


def test_optional_pagination_preserves_legacy_list(client):
    seed_history(12)
    all_rows = client.get("/api/expenses").json()
    response = client.get("/api/expenses?limit=3&offset=4")
    assert response.status_code == 200
    assert response.json() == all_rows[4:7]
    assert client.get("/api/expenses?limit=0").status_code == 422
    assert client.get("/api/expenses?offset=-1").status_code == 422


def test_import_record_limit_rejects_before_writes(client):
    response = client.post(
        "/api/imports/splitwise/analyze",
        files={"file": ("large.json", json.dumps([{}] * 10001), "application/json")},
    )
    assert response.status_code == 413
    with Session(db.engine) as s:
        assert s.exec(select(ImportBatch)).all() == []


def test_login_length_limit(client):
    assert (
        client.post(
            "/api/auth/login", json={"username": "x" * 1001, "password": "x" * 1001}
        ).status_code
        == 422
    )


def test_expense_list_batches_splits_and_categories(client):
    seed_history(100)
    queries = []

    def track(*args):
        queries.append(args[2])

    event.listen(db.engine, "before_cursor_execute", track)
    try:
        response = client.get("/api/expenses?limit=100")
    finally:
        event.remove(db.engine, "before_cursor_execute", track)
    assert response.status_code == 200
    assert len(response.json()) == 100
    assert all(row["splits"] == [{"user_id": 2, "amount_cents": 101}] for row in response.json())
    assert len(queries) <= 10


@pytest.mark.parametrize(
    "filename,content",
    [
        (
            "large.csv",
            b"Date,Description,Cost,Currency,A,B\n" + b"2024-01-01,Test,1,EUR,1,-1\n" * 10001,
        ),
        (
            "large.json",
            json.dumps({"groups": [{"id": 1, "name": "Group", "expenses": [{}] * 10001}]}).encode(),
        ),
        ("oversize.json", b" " * (10 * 1024 * 1024 + 1)),
    ],
)
def test_import_all_formats_limits_no_batch(client, filename, content):
    response = client.post("/api/imports/splitwise/analyze", files={"file": (filename, content)})
    assert response.status_code == 413
    with Session(db.engine) as s:
        assert s.exec(select(ImportBatch)).all() == []


def test_import_exact_record_limit_allowed(client):
    content = b"Date,Description,Cost,Currency,A,B\n" + b"2024-01-01,Test,1,EUR,1,-1\n" * 10000
    response = client.post(
        "/api/imports/splitwise/analyze", files={"file": ("boundary.csv", content)}
    )
    assert response.status_code == 200
    assert response.json()["records_total"] == 10000


def test_oversized_preexisting_import_cannot_commit(client):
    from app.importers.splitwise_csv import parse_csv

    data = parse_csv(b"Date,Description,Cost,Currency,A,B\n2024-01-01,Test,1,EUR,1,-1\n", "Group")
    data["records"] *= 10001
    with Session(db.engine) as s:
        batch = ImportBatch(
            format="JSON",
            original_filename="old.json",
            file_hash="oversized-old",
            uploaded_by_user_id=1,
            status="MAPPED",
            previewed=True,
            data_json=json.dumps(data),
        )
        s.add(batch)
        s.commit()
        batch_id = batch.id
    response = client.post(f"/api/imports/splitwise/{batch_id}/commit")
    assert response.status_code == 413
    with Session(db.engine) as s:
        assert s.get(ImportBatch, batch_id).status == "MAPPED"
        assert s.exec(select(Expense)).all() == []
