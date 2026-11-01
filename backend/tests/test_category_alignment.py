from datetime import date
import pytest
from sqlmodel import Session, select
from app import db
from app.models import Category, Expense, Subscription
from app.category_backfill import backfill
from test_api import group


@pytest.mark.parametrize("review_auto", [False, True])
def test_alignment_classifies_unassigned_legacy_override_on_first_run(client, review_auto):
    gid = group(client)
    with Session(db.engine) as s:
        groceries = s.exec(select(Category).where(Category.slug == "groceries")).one()
        row = Expense(
            group_id=gid,
            description="Finocchi",
            amount_cents=1000,
            paid_by_user_id=1,
            expense_date=date(2026, 1, 1),
            created_by_user_id=1,
            icon_key="tag",
        )
        s.add(row)
        s.commit()
        assert backfill(s) == []
        assert len(backfill(s, review_auto=review_auto, align_icons=True)) == 1
        assert row.category_id == groceries.id
        assert row.icon_key is None
        s.commit()
        assert backfill(s, review_auto=review_auto, align_icons=True) == []


def test_review_alignment_preserves_manual_choices_and_accounting_is_idempotent(client):
    gid = group(client)
    with Session(db.engine) as s:
        groceries = s.exec(select(Category).where(Category.slug == "groceries")).one()
        pets = s.exec(select(Category).where(Category.slug == "pets")).one()
        rows = []
        for category_id, source, icon in [
            (groceries.id, "auto:csv:Alimentari", "shopping-basket"),
            (groceries.id, "manual", "chatgpt"),
            (None, "manual", None),
        ]:
            row = Expense(
                group_id=gid,
                description="Perlavet",
                amount_cents=1000,
                paid_by_user_id=1,
                expense_date=date(2026, 1, 1),
                created_by_user_id=1,
                category_id=category_id,
                category_source=source,
                icon_key=icon,
            )
            s.add(row)
            rows.append(row)
        s.commit()
        for r in rows:
            s.refresh(r)
        before = [r.model_dump() for r in rows]
        report = backfill(s, review_auto=True, align_icons=True)
        assert len(report) == 2
        assert rows[0].category_id == pets.id
        assert rows[1].category_id == groceries.id and rows[1].category_source == "manual"
        assert rows[2].category_id is None and rows[2].category_source == "manual"
        assert all(r.icon_key is None for r in rows)
        for old, row in zip(before, rows):
            assert {
                k: v
                for k, v in old.items()
                if k not in ("category_id", "icon_key", "category_source")
            } == {
                k: v
                for k, v in row.model_dump().items()
                if k not in ("category_id", "icon_key", "category_source")
            }
        s.commit()
        assert backfill(s, review_auto=True, align_icons=True) == []


def test_alignment_carries_chatgpt_legacy_icon_into_category_and_defaults_stay_conservative(client):
    gid = group(client)
    with Session(db.engine) as s:
        chat = s.exec(select(Category).where(Category.slug == "chatgpt")).first()
        if not chat:
            chat = Category(name="ChatGPT", slug="chatgpt", icon_key="chatgpt")
            s.add(chat)
            s.flush()
        row = Subscription(
            group_id=gid,
            name="ChatGPT Pro",
            amount_cents=10300,
            paid_by_user_id=1,
            recurrence_rule="FREQ=MONTHLY",
            start_date=date(2026, 1, 1),
            next_occurrence_date=date(2026, 2, 1),
            created_by_user_id=1,
            icon_key="chatgpt",
            category_source="manual",
        )
        s.add(row)
        s.commit()
        assert backfill(s) == []
        report = backfill(s, review_auto=True, align_icons=True)
        assert len(report) == 1
        assert row.category_id == chat.id and row.icon_key is None
        assert row.category_source == "manual"
        assert row.amount_cents == 10300 and row.next_occurrence_date == date(2026, 2, 1)
        s.commit()
        assert backfill(s, review_auto=True, align_icons=True) == []
