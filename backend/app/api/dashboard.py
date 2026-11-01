from fastapi import APIRouter, Query
from sqlmodel import select
from app.auth import DB, CurrentUser
from app.models import Group, Expense, Subscription
from app.schemas import UserResponse, GroupResponse
from app.services.access import visible_ids
from app.services.records import expense_responses, subscription_responses
from app.services.balance_service import user_totals, debts

router = APIRouter(prefix="/api/dashboard")


@router.get("/summary")
def summary(user: CurrentUser, s: DB):
    ids = visible_ids(s, user)
    groups = s.exec(select(Group).where(Group.id.in_(ids))).all()
    suggested = []
    for group in groups:
        suggested.extend(
            [
                {**d, "group_id": group.id, "group_name": group.name}
                for d in debts(s, group.id)
                if user.id in (d["paid_by_user_id"], d["paid_to_user_id"])
            ]
        )
    recent = s.exec(
        select(Expense)
        .where(Expense.group_id.in_(ids))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .limit(8)
    ).all()
    upcoming = s.exec(
        select(Subscription)
        .where(
            Subscription.group_id.in_(ids),
            Subscription.active == True,
            Subscription.deleted == False,
        )
        .order_by(Subscription.next_occurrence_date)
        .limit(8)
    ).all()
    return {
        "user": UserResponse.model_validate(user),
        "balances": user_totals(s, ids, user.id),
        "debts": suggested,
        "upcoming": subscription_responses(s, upcoming),
        "recent_expenses": expense_responses(s, recent),
        "groups": [GroupResponse.model_validate(g) for g in groups],
    }


@router.get("/statistics")
def monthly_statistics(
    user: CurrentUser,
    s: DB,
    month: str | None = Query(default=None, pattern=r"^[0-9]{4}-[0-9]{2}$"),
    group_id: int | None = None,
    currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
):
    from app.services.statistics_service import statistics

    return statistics(s, user, month=month, group_id=group_id, currency=currency)
