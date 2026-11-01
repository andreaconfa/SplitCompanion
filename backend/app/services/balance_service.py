from collections import defaultdict
from sqlmodel import select
from sqlalchemy import func
from app.models import (
    GroupMember,
    Expense,
    ExpenseSplit,
    Settlement,
    LegacyTransaction,
    LegacyTransactionEntry,
)


def balances(session, group_id):
    values = defaultdict(int)
    members = session.exec(select(GroupMember).where(GroupMember.group_id == group_id)).all()
    currencies = {"EUR"}
    # Aggregate in SQL: query count and result size are independent of history size.
    for currency, uid, amount in session.exec(
        select(Expense.currency, Expense.paid_by_user_id, func.sum(Expense.amount_cents))
        .where(Expense.group_id == group_id)
        .group_by(Expense.currency, Expense.paid_by_user_id)
    ):
        currencies.add(currency)
        values[currency, uid] += amount
    for currency, uid, amount in session.exec(
        select(Expense.currency, ExpenseSplit.user_id, func.sum(ExpenseSplit.amount_cents))
        .join(ExpenseSplit, ExpenseSplit.expense_id == Expense.id)
        .where(Expense.group_id == group_id)
        .group_by(Expense.currency, ExpenseSplit.user_id)
    ):
        values[currency, uid] -= amount
    for payer, sign in ((Settlement.paid_by_user_id, 1), (Settlement.paid_to_user_id, -1)):
        for currency, uid, amount in session.exec(
            select(Settlement.currency, payer, func.sum(Settlement.amount_cents))
            .where(Settlement.group_id == group_id)
            .group_by(Settlement.currency, payer)
        ):
            currencies.add(currency)
            values[currency, uid] += sign * amount
    currencies.update(
        session.exec(
            select(LegacyTransaction.currency)
            .where(LegacyTransaction.group_id == group_id)
            .distinct()
        ).all()
    )
    for currency, uid, amount in session.exec(
        select(
            LegacyTransaction.currency,
            LegacyTransactionEntry.user_id,
            func.sum(LegacyTransactionEntry.balance_delta_cents),
        )
        .join(
            LegacyTransactionEntry,
            LegacyTransactionEntry.legacy_transaction_id == LegacyTransaction.id,
        )
        .where(LegacyTransaction.group_id == group_id)
        .group_by(LegacyTransaction.currency, LegacyTransactionEntry.user_id)
    ):
        values[currency, uid] += amount
    for currency in currencies:
        for member in members:
            values.setdefault((currency, member.user_id), 0)
    return [
        {"user_id": uid, "currency": cur, "balance_cents": amount}
        for (cur, uid), amount in sorted(values.items())
    ]


def debts(session, group_id):
    result = []
    by_currency = defaultdict(list)
    for row in balances(session, group_id):
        by_currency[row["currency"]].append(row)
    for currency, rows in by_currency.items():
        creditors = [[r["user_id"], r["balance_cents"]] for r in rows if r["balance_cents"] > 0]
        debtors = [[r["user_id"], -r["balance_cents"]] for r in rows if r["balance_cents"] < 0]
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            amount = min(debtors[i][1], creditors[j][1])
            result.append(
                {
                    "paid_by_user_id": debtors[i][0],
                    "paid_to_user_id": creditors[j][0],
                    "amount_cents": amount,
                    "currency": currency,
                }
            )
            debtors[i][1] -= amount
            creditors[j][1] -= amount
            if debtors[i][1] == 0:
                i += 1
            if creditors[j][1] == 0:
                j += 1
    return result


def user_totals(session, group_ids, user_id):
    totals = {}
    for gid in group_ids:
        for row in balances(session, gid):
            if row["user_id"] != user_id:
                continue
            cur = row["currency"]
            value = row["balance_cents"]
            total = totals.setdefault(
                cur, {"currency": cur, "balance_cents": 0, "to_receive_cents": 0, "to_pay_cents": 0}
            )
            total["balance_cents"] += value
            total["to_receive_cents"] += max(0, value)
            total["to_pay_cents"] += max(0, -value)
    return list(totals.values()) or [
        {"currency": "EUR", "balance_cents": 0, "to_receive_cents": 0, "to_pay_cents": 0}
    ]
