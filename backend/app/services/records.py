from collections import defaultdict
from sqlmodel import select, delete
from app.models import (
    Category,
    Expense,
    ExpenseSplit,
    SubscriptionSplit,
    SubscriptionOccurrence,
    SubscriptionAdvanceApplication,
)
from app.schemas import ExpenseResponse, SubscriptionResponse, SplitResponse
from app.services.split_service import calculate_splits
from app.services.access import members_active
from app.services.subscription_credit_service import rebuild_credit


def _responses(s, records, split_model, foreign_key, response_model):
    records = list(records)
    if not records:
        return []
    categories = {c.id: c.icon_key for c in s.exec(select(Category)).all()}
    parts = defaultdict(list)
    # Chunk IDs to stay below SQLite's bind-parameter limit for legacy unpaged clients.
    ids = [r.id for r in records]
    for offset in range(0, len(ids), 500):
        for part in s.exec(
            select(split_model)
            .where(foreign_key.in_(ids[offset : offset + 500]))
            .order_by(split_model.user_id)
        ).all():
            parts[getattr(part, foreign_key.key)].append(
                SplitResponse(user_id=part.user_id, amount_cents=part.amount_cents)
            )
    result = []
    for record in records:
        response = response_model.model_validate(record)
        response.icon_key = categories.get(record.category_id)
        response.splits = parts[record.id]
        result.append(response_model.model_validate(response.model_dump()))
    return result


def expense_responses(s, records):
    return _responses(s, records, ExpenseSplit, ExpenseSplit.expense_id, ExpenseResponse)


def expense_response(s, e):
    return expense_responses(s, [e])[0]


def subscription_responses(s, records):
    return _responses(
        s, records, SubscriptionSplit, SubscriptionSplit.subscription_id, SubscriptionResponse
    )


def subscription_response(s, sub):
    return subscription_responses(s, [sub])[0]


def resolve_splits(s, data):
    from app.services.category_service import validate_metadata

    validate_metadata(s, data.category_id)
    parts = calculate_splits(
        data.amount_cents, data.split_mode, [p.model_dump() for p in data.splits]
    )
    members_active(s, data.group_id, [data.paid_by_user_id, *parts])
    return parts


def create_expense(s, data, actor_id, **metadata):
    parts = resolve_splits(s, data)
    e = Expense(
        **data.model_dump(exclude={"split_mode", "splits", "icon_key"}),
        created_by_user_id=actor_id,
        **metadata,
    )
    e.category_source = "manual" if "category_id" in data.model_fields_set else None
    s.add(e)
    s.flush()
    for uid, amount in parts.items():
        s.add(ExpenseSplit(expense_id=e.id, user_id=uid, amount_cents=amount))
    s.flush()
    from app.services.push_service import enqueue_expense

    enqueue_expense(s, e, actor_id)
    return e


def delete_expense(s, e):
    sid = e.subscription_id
    for occurrence in s.exec(
        select(SubscriptionOccurrence).where(SubscriptionOccurrence.expense_id == e.id)
    ).all():
        occurrence.expense_id = None
        s.add(occurrence)
    s.flush()
    s.exec(
        delete(SubscriptionAdvanceApplication).where(
            SubscriptionAdvanceApplication.expense_id == e.id
        )
    )
    s.exec(delete(ExpenseSplit).where(ExpenseSplit.expense_id == e.id))
    s.delete(e)
    s.flush()
    if sid:
        rebuild_credit(s, sid)
