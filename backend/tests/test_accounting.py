from datetime import date
import pytest
from sqlmodel import SQLModel, Session, select
from app.db import make_engine
from app.models import (
    User,
    Group,
    GroupMember,
    Subscription,
    SubscriptionSplit,
    Expense,
    ExpenseSplit,
    Settlement,
    SubscriptionAdvanceApplication,
    LegacyTransaction,
    LegacyTransactionEntry,
)
from app.services.balance_service import balances, debts
from app.services.subscription_service import generate_due, next_date
from app.services.subscription_credit_service import rebuild_credit, credits


@pytest.fixture
def session(tmp_path):
    engine = make_engine(str(tmp_path / "test.db"))
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for name in ["Alex", "Laura", "Marco"]:
            s.add(User(username=name, display_name=name, password_hash="hash"))
        s.flush()
        s.add(Group(name="Casa", created_by_user_id=1))
        s.flush()
        for uid in [1, 2, 3]:
            s.add(GroupMember(group_id=1, user_id=uid))
        s.commit()
        yield s
    engine.dispose()


def subscription(s, amount=3000, rule="FREQ=MONTHLY;INTERVAL=1"):
    sub = Subscription(
        group_id=1,
        name="Netflix",
        amount_cents=amount,
        paid_by_user_id=1,
        recurrence_rule=rule,
        start_date=date(2025, 1, 5),
        next_occurrence_date=date(2025, 1, 5),
        created_by_user_id=1,
    )
    s.add(sub)
    s.flush()
    for uid in [1, 2, 3]:
        s.add(SubscriptionSplit(subscription_id=sub.id, user_id=uid, amount_cents=amount // 3))
    s.flush()
    return sub


def advance(s, sub, amount, day=date(2025, 1, 1)):
    a = Settlement(
        group_id=1,
        paid_by_user_id=2,
        paid_to_user_id=1,
        amount_cents=amount,
        settlement_date=day,
        kind="SUBSCRIPTION_ADVANCE",
        subscription_id=sub.id,
        created_by_user_id=1,
    )
    s.add(a)
    s.flush()
    return a


def test_native_settlement_legacy_currency(session):
    s = session
    e = Expense(
        group_id=1,
        description="Marco",
        amount_cents=9000,
        paid_by_user_id=1,
        expense_date=date.today(),
        created_by_user_id=1,
    )
    s.add(e)
    s.flush()
    s.add(ExpenseSplit(expense_id=e.id, user_id=3, amount_cents=9000))
    s.flush()
    assert balances(s, 1) == [
        {"user_id": 1, "currency": "EUR", "balance_cents": 9000},
        {"user_id": 2, "currency": "EUR", "balance_cents": 0},
        {"user_id": 3, "currency": "EUR", "balance_cents": -9000},
    ]
    assert debts(s, 1) == [
        {"paid_by_user_id": 3, "paid_to_user_id": 1, "amount_cents": 9000, "currency": "EUR"}
    ]
    s.add(
        Settlement(
            group_id=1,
            paid_by_user_id=3,
            paid_to_user_id=1,
            amount_cents=4000,
            settlement_date=date.today(),
            created_by_user_id=1,
        )
    )
    s.flush()
    assert debts(s, 1)[0]["amount_cents"] == 5000
    s.add(
        Settlement(
            group_id=1,
            paid_by_user_id=3,
            paid_to_user_id=1,
            amount_cents=5000,
            settlement_date=date.today(),
            created_by_user_id=1,
        )
    )
    s.flush()
    assert debts(s, 1) == []


@pytest.mark.parametrize(
    "rule,expected",
    [
        ("FREQ=WEEKLY;INTERVAL=1", date(2025, 1, 12)),
        ("FREQ=WEEKLY;INTERVAL=2", date(2025, 1, 19)),
        ("FREQ=MONTHLY;INTERVAL=1", date(2025, 2, 5)),
        ("FREQ=MONTHLY;INTERVAL=3", date(2025, 4, 5)),
        ("FREQ=YEARLY;INTERVAL=1", date(2026, 1, 5)),
    ],
)
def test_recurrences(rule, expected):
    assert next_date(rule, date(2025, 1, 5), date(2025, 1, 5)) == expected


def test_advance_catchup_idempotent_fifo_refund(session):
    s = session
    sub = subscription(s)
    a = advance(s, sub, 1500)
    advance(s, sub, 5000, date(2025, 1, 2))
    assert generate_due(s, sub, date(2025, 3, 10)) == 3
    assert generate_due(s, sub, date(2025, 3, 10)) == 0
    c = credits(s, sub.id)[0]
    assert (c["advanced_cents"], c["used_cents"], c["remaining_cents"]) == (6500, 3000, 3500)
    apps = s.exec(
        select(SubscriptionAdvanceApplication).where(
            SubscriptionAdvanceApplication.advance_settlement_id == a.id
        )
    ).all()
    assert sum(x.amount_cents for x in apps) == 1500
    r = Settlement(
        group_id=1,
        paid_by_user_id=1,
        paid_to_user_id=2,
        amount_cents=2000,
        settlement_date=date(2025, 3, 11),
        kind="SUBSCRIPTION_REFUND",
        subscription_id=sub.id,
        created_by_user_id=1,
    )
    s.add(r)
    s.flush()
    rebuild_credit(s, sub.id)
    assert credits(s, sub.id)[0]["remaining_cents"] == 1500
    laura = next(b for b in balances(s, 1) if b["user_id"] == 2)
    assert laura["balance_cents"] == 1500
    s.commit()


def test_partial_credit_and_history_immutable(session):
    s = session
    sub = subscription(s)
    advance(s, sub, 700)
    assert generate_due(s, sub, date(2025, 1, 5)) == 1
    assert credits(s, sub.id)[0]["used_cents"] == 700
    old = s.exec(select(Expense)).one()
    sub.amount_cents = 6000
    for split in s.exec(select(SubscriptionSplit)).all():
        split.amount_cents = 2000
        s.add(split)
    s.flush()
    generate_due(s, sub, date(2025, 2, 5))
    assert old.amount_cents == 3000
    assert credits(s, sub.id)[0]["remaining_cents"] == 0


def test_pause_end_and_transaction_retry(session):
    s = session
    sub = subscription(s)
    sub.active = False
    assert generate_due(s, sub, date(2025, 4, 5)) == 0
    sub.active = True
    sub.end_date = date(2025, 2, 5)
    s.commit()
    assert generate_due(s, sub, date(2025, 4, 5)) == 2
    s.rollback()
    sub = s.get(Subscription, sub.id)
    assert generate_due(s, sub, date(2025, 4, 5)) == 2
    assert len(s.exec(select(Expense)).all()) == 2


def test_deleted_occurrence_never_regenerated(session):
    from app.services.records import delete_expense

    s = session
    sub = subscription(s)
    generate_due(s, sub, date(2025, 1, 5))
    e = s.exec(select(Expense)).one()
    delete_expense(s, e)
    sub.next_occurrence_date = date(2025, 1, 5)
    s.add(sub)
    s.flush()
    assert generate_due(s, sub, date(2025, 1, 5)) == 0
    assert s.exec(select(Expense)).all() == []


def test_no_reopening_credit_after_payer_change(session):
    from app.services.records import delete_expense

    s = session
    sub = subscription(s)
    advance(s, sub, 1000)
    generate_due(s, sub, date(2025, 1, 5))
    assert credits(s, sub.id)[0]["remaining_cents"] == 0
    sub.paid_by_user_id = 3
    s.add(sub)
    s.flush()
    with pytest.raises(ValueError):
        delete_expense(s, s.exec(select(Expense)).one())


def test_future_advance_not_applied_to_past_expense(session):
    s = session
    sub = subscription(s)
    advance(s, sub, 5000, date(2025, 2, 1))
    generate_due(s, sub, date(2025, 2, 5))
    assert credits(s, sub.id)[0]["used_cents"] == 1000


def test_refund_overdraft_rolls_back(session):
    s = session
    sub = subscription(s)
    advance(s, sub, 1000)
    s.commit()
    s.add(
        Settlement(
            group_id=1,
            paid_by_user_id=1,
            paid_to_user_id=2,
            amount_cents=1001,
            settlement_date=date(2025, 1, 2),
            kind="SUBSCRIPTION_REFUND",
            subscription_id=sub.id,
            created_by_user_id=1,
        )
    )
    s.flush()
    with pytest.raises(ValueError):
        rebuild_credit(s, sub.id)
    s.rollback()
    assert len(s.exec(select(Settlement)).all()) == 1


def test_legacy_currency_balances(session):
    from app.models import ImportBatch

    s = session
    b = ImportBatch(format="CSV", original_filename="x", file_hash="hash", uploaded_by_user_id=1)
    s.add(b)
    s.flush()
    for cur in ["EUR", "USD"]:
        t = LegacyTransaction(
            group_id=1,
            import_batch_id=b.id,
            date=date.today(),
            description="Legacy",
            cost_cents=1000,
            currency=cur,
        )
        s.add(t)
        s.flush()
        for uid, delta in [(1, 500), (2, -500)]:
            s.add(
                LegacyTransactionEntry(
                    legacy_transaction_id=t.id, user_id=uid, balance_delta_cents=delta
                )
            )
    s.flush()
    result = balances(s, 1)
    assert (
        next(x for x in result if x["user_id"] == 1 and x["currency"] == "EUR")["balance_cents"]
        == 500
    )
    assert (
        next(x for x in result if x["user_id"] == 1 and x["currency"] == "USD")["balance_cents"]
        == 500
    )
    assert len(debts(s, 1)) == 2


def test_concurrent_jobs_duplicate_prevention(session):
    from concurrent.futures import ThreadPoolExecutor
    from app.jobs.subscriptions import run_subscriptions

    s = session
    subscription(s)
    s.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: run_subscriptions(s.get_bind(), date(2025, 3, 5)), range(2))
        )
    assert sum(results) == 3
    assert len(s.exec(select(Expense)).all()) == 3


@pytest.mark.parametrize(
    "day,expected", [(date(2025, 3, 30), date(2025, 4, 6)), (date(2025, 10, 26), date(2025, 11, 2))]
)
def test_dst_local_dates(day, expected):
    assert next_date("FREQ=WEEKLY;INTERVAL=1", day, day) == expected


def test_month_end_rrule_skips_invalid_day():
    assert next_date("FREQ=MONTHLY;INTERVAL=1", date(2025, 1, 31), date(2025, 1, 31)) == date(
        2025, 3, 31
    )


def test_scheduler_waits_for_archived_group_or_disabled_participant(session):
    s = session
    sub = subscription(s)
    g = s.get(Group, 1)
    g.archived = True
    s.add(g)
    s.flush()
    assert generate_due(s, sub, date(2025, 1, 5)) == 0
    g.archived = False
    s.add(g)
    u = s.get(User, 2)
    u.is_active = False
    s.add(u)
    s.flush()
    assert generate_due(s, sub, date(2025, 1, 5)) == 0
    u.is_active = True
    s.add(u)
    s.flush()
    assert generate_due(s, sub, date(2025, 1, 5)) == 1
