import re
from datetime import datetime, time, date
from dateutil.rrule import rrulestr
from sqlmodel import select
from app.models import (
    Group,
    GroupMember,
    User,
    SubscriptionSplit,
    SubscriptionOccurrence,
    Expense,
    ExpenseSplit,
    now,
)
from app.services.subscription_credit_service import rebuild_credit


def validate_rule(rule):
    if not re.fullmatch(r"FREQ=(WEEKLY|MONTHLY|YEARLY);INTERVAL=([1-9][0-9]?)", rule):
        raise ValueError("Ricorrenza non valida: intervallo da 1 a 99.")
    return rule


def next_date(rule, start, after):
    validate_rule(rule)
    result = rrulestr(rule, dtstart=datetime.combine(start, time.min)).after(
        datetime.combine(after, time.min)
    )
    if result is None:
        raise ValueError("Ricorrenza senza prossima data.")
    return result.date()


def generate_due(session, sub, today: date):
    if not sub.active or sub.deleted:
        return 0
    group = session.get(Group, sub.group_id)
    if group.archived:
        return 0
    participant_ids = [sub.paid_by_user_id] + list(
        session.exec(
            select(SubscriptionSplit.user_id).where(SubscriptionSplit.subscription_id == sub.id)
        ).all()
    )
    for uid in set(participant_ids):
        user = session.get(User, uid)
        member = session.exec(
            select(GroupMember).where(
                GroupMember.group_id == sub.group_id,
                GroupMember.user_id == uid,
                GroupMember.active == True,
            )
        ).first()
        if not user or not user.is_active or not member:
            return 0
    count = 0
    while sub.next_occurrence_date <= today and (
        sub.end_date is None or sub.next_occurrence_date <= sub.end_date
    ):
        due = sub.next_occurrence_date
        existing = session.exec(
            select(SubscriptionOccurrence).where(
                SubscriptionOccurrence.subscription_id == sub.id,
                SubscriptionOccurrence.occurrence_date == due,
            )
        ).first()
        if not existing:
            parts = session.exec(
                select(SubscriptionSplit).where(SubscriptionSplit.subscription_id == sub.id)
            ).all()
            if sum(p.amount_cents for p in parts) != sub.amount_cents:
                raise ValueError("Quote abbonamento incoerenti.")
            e = Expense(
                group_id=sub.group_id,
                description=sub.name,
                category_id=sub.category_id,
                category_source=sub.category_source,
                amount_cents=sub.amount_cents,
                currency=sub.currency,
                paid_by_user_id=sub.paid_by_user_id,
                expense_date=due,
                notes=sub.description,
                created_by_user_id=sub.created_by_user_id,
                subscription_id=sub.id,
                subscription_occurrence_date=due,
            )
            session.add(e)
            session.flush()
            for p in parts:
                session.add(
                    ExpenseSplit(expense_id=e.id, user_id=p.user_id, amount_cents=p.amount_cents)
                )
            session.add(
                SubscriptionOccurrence(subscription_id=sub.id, occurrence_date=due, expense_id=e.id)
            )
            session.flush()
            from app.services.push_service import enqueue_expense

            enqueue_expense(session, e, sub.created_by_user_id)
            count += 1
        sub.next_occurrence_date = next_date(sub.recurrence_rule, sub.start_date, due)
        sub.updated_at = now()
        session.add(sub)
    if sub.end_date and sub.next_occurrence_date > sub.end_date:
        sub.active = False
        session.add(sub)
    if count:
        rebuild_credit(session, sub.id)
    session.flush()
    return count
