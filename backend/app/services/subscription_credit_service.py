from collections import defaultdict
from sqlmodel import select, delete
from app.models import (
    Subscription,
    Settlement,
    Expense,
    ExpenseSplit,
    SubscriptionAdvanceApplication as Application,
    AdvanceRefundAllocation as RefundAllocation,
)


def rebuild_credit(session, subscription_id):
    """Replay lots in local-date order. Allocations explain money; never add to balances."""
    transfers = session.exec(
        select(Settlement).where(Settlement.subscription_id == subscription_id)
    ).all()
    transfer_ids = [x.id for x in transfers]
    if transfer_ids:
        session.exec(delete(Application).where(Application.advance_settlement_id.in_(transfer_ids)))
        session.exec(
            delete(RefundAllocation).where(RefundAllocation.advance_settlement_id.in_(transfer_ids))
        )
    expenses = session.exec(select(Expense).where(Expense.subscription_id == subscription_id)).all()
    events = [
        (t.settlement_date, 0 if t.kind == "SUBSCRIPTION_ADVANCE" else 2, t.id, t)
        for t in transfers
    ]
    events += [(e.expense_date, 1, e.id, e) for e in expenses]
    lots = defaultdict(list)
    for day, kind, _, event in sorted(events, key=lambda item: item[:3]):
        if kind == 0:
            lots[event.paid_by_user_id, event.paid_to_user_id, event.currency].append(
                [event, event.amount_cents]
            )
        elif kind == 1:
            for part in session.exec(
                select(ExpenseSplit).where(ExpenseSplit.expense_id == event.id)
            ).all():
                remaining = part.amount_cents
                for lot in lots[part.user_id, event.paid_by_user_id, event.currency]:
                    used = min(remaining, lot[1])
                    if used:
                        session.add(
                            Application(
                                advance_settlement_id=lot[0].id,
                                expense_id=event.id,
                                user_id=part.user_id,
                                amount_cents=used,
                            )
                        )
                        lot[1] -= used
                        remaining -= used
                    if not remaining:
                        break
        else:
            remaining = event.amount_cents
            for lot in lots[event.paid_to_user_id, event.paid_by_user_id, event.currency]:
                used = min(remaining, lot[1])
                if used:
                    session.add(
                        RefundAllocation(
                            advance_settlement_id=lot[0].id,
                            refund_settlement_id=event.id,
                            amount_cents=used,
                        )
                    )
                    lot[1] -= used
                    remaining -= used
                if not remaining:
                    break
            if remaining:
                raise ValueError("Il rimborso supera il credito disponibile alla data indicata.")
    sub = session.get(Subscription, subscription_id)
    for (uid, payer, cur), user_lots in lots.items():
        if payer != sub.paid_by_user_id and any(lot[1] for lot in user_lots):
            raise ValueError(
                "La modifica riaprirebbe credito verso un precedente pagante. Lo storico resta invariato."
            )
    session.flush()


def credits(session, subscription_id):
    rows = {}
    advances = session.exec(
        select(Settlement)
        .where(
            Settlement.subscription_id == subscription_id, Settlement.kind == "SUBSCRIPTION_ADVANCE"
        )
        .order_by(Settlement.settlement_date, Settlement.id)
    ).all()
    for advance in advances:
        uid = advance.paid_by_user_id
        row = rows.setdefault(
            uid,
            {
                "user_id": uid,
                "advanced_cents": 0,
                "used_cents": 0,
                "refunded_cents": 0,
                "remaining_cents": 0,
                "history": [],
            },
        )
        row["advanced_cents"] += advance.amount_cents
        row["history"].append(
            {
                "date": advance.settlement_date.isoformat(),
                "kind": "ADVANCE",
                "amount_cents": advance.amount_cents,
                "settlement_id": advance.id,
            }
        )
        for app in session.exec(
            select(Application).where(Application.advance_settlement_id == advance.id)
        ).all():
            expense = session.get(Expense, app.expense_id)
            row["used_cents"] += app.amount_cents
            row["history"].append(
                {
                    "date": expense.expense_date.isoformat(),
                    "kind": "APPLICATION",
                    "amount_cents": app.amount_cents,
                    "expense_id": expense.id,
                }
            )
        for alloc in session.exec(
            select(RefundAllocation).where(RefundAllocation.advance_settlement_id == advance.id)
        ).all():
            refund = session.get(Settlement, alloc.refund_settlement_id)
            row["refunded_cents"] += alloc.amount_cents
            row["history"].append(
                {
                    "date": refund.settlement_date.isoformat(),
                    "kind": "REFUND",
                    "amount_cents": alloc.amount_cents,
                    "settlement_id": refund.id,
                }
            )
        row["remaining_cents"] = row["advanced_cents"] - row["used_cents"] - row["refunded_cents"]
    for row in rows.values():
        row["history"].sort(key=lambda h: (h["date"], h["kind"]))
    return list(rows.values())
