"""Read-only group expense statistics; legacy balance deltas are never costs."""

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlmodel import select
from sqlalchemy import case, extract, func

from app.config import get_settings
from app.models import Category, Expense, Group, LegacyTransaction
from app.services.access import visible_ids


def month_start(value: date, offset: int = 0) -> date:
    number = value.year * 12 + value.month - 1 + offset
    year, month = divmod(number, 12)
    return date(year, month + 1, 1)


def month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def rounded_average(total: int, count: int) -> int:
    # Integer half-up rounding avoids float precision and banker's rounding.
    return (2 * total + count) // (2 * count) if count else 0


def statistics(session, user, month=None, group_id=None, currency=None):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    current = month_start(today)
    try:
        start = date.fromisoformat(month + "-01") if month else current
    except ValueError:
        raise HTTPException(422, "Mese non valido.")
    if start < date(1900, 1, 1) or start > current:
        raise HTTPException(
            422, "Il mese deve essere compreso tra gennaio 1900 e il mese corrente."
        )
    ids = visible_ids(session, user)
    if group_id is not None:
        if group_id not in ids:
            raise HTTPException(403, "Non hai accesso a questo gruppo.")
        ids = [group_id]
    end = today if start == current else start.replace(day=monthrange(start.year, start.month)[1])
    days = (end - start).days + 1
    previous = month_start(start, -1)
    previous_last = monthrange(previous.year, previous.month)[1]
    previous_end = previous.replace(
        day=min(today.day, previous_last) if start == current else previous_last
    )
    trend_start = month_start(start, -5)

    # Distinct metadata covers all history without loading expense objects.
    currencies_found = set()
    available = {month_key(current)}
    for model, day_column in (
        (Expense, Expense.expense_date),
        (LegacyTransaction, LegacyTransaction.date),
    ):
        scope = (model.group_id.in_(ids), day_column <= today)
        currencies_found.update(session.exec(select(model.currency).where(*scope).distinct()).all())
        for year, month_number in session.exec(
            select(extract("year", day_column), extract("month", day_column))
            .where(*scope, day_column >= date(1900, 1, 1))
            .distinct()
        ):
            available.add(f"{int(year):04d}-{int(month_number):02d}")
    currencies = sorted(currencies_found) or ["EUR"]
    currency = currency or ("EUR" if "EUR" in currencies else currencies[0])
    categories = {c.id: c for c in session.exec(select(Category)).all()}
    groups = {g.id: g for g in session.exec(select(Group).where(Group.id.in_(ids))).all()}
    coverage = dict(
        legacy_included_count=0,
        legacy_excluded_count=0,
        legacy_transfers_excluded_count=0,
        legacy_missing_cost_count=0,
        legacy_nonpositive_count=0,
    )
    # Aggregate the six-month window in SQL. Each result represents a daily
    # category/group bucket, not a source record; counts remain exact.
    records = [
        (day, amount, cid, gid, False, count)
        for day, amount, cid, gid, count in session.exec(
            select(
                Expense.expense_date,
                func.sum(Expense.amount_cents),
                Expense.category_id,
                Expense.group_id,
                func.count(),
            )
            .where(
                Expense.group_id.in_(ids),
                Expense.currency == currency,
                Expense.expense_date >= trend_start,
                Expense.expense_date <= end,
            )
            .group_by(Expense.expense_date, Expense.category_id, Expense.group_id)
        )
    ]
    reason_column = case(
        (Category.slug == "transfers", "legacy_transfers_excluded_count"),
        (LegacyTransaction.cost_cents.is_(None), "legacy_missing_cost_count"),
        (LegacyTransaction.cost_cents <= 0, "legacy_nonpositive_count"),
        else_=None,
    )
    for day, amount, cid, gid, reason, count in session.exec(
        select(
            LegacyTransaction.date,
            func.sum(LegacyTransaction.cost_cents),
            LegacyTransaction.category_id,
            LegacyTransaction.group_id,
            reason_column,
            func.count(),
        )
        .outerjoin(Category, Category.id == LegacyTransaction.category_id)
        .where(
            LegacyTransaction.group_id.in_(ids),
            LegacyTransaction.currency == currency,
            LegacyTransaction.date >= trend_start,
            LegacyTransaction.date <= end,
        )
        .group_by(
            LegacyTransaction.date,
            LegacyTransaction.category_id,
            LegacyTransaction.group_id,
            reason_column,
        )
    ):
        if start <= day <= end:
            if reason:
                coverage[reason] += count
                coverage["legacy_excluded_count"] += count
            else:
                coverage["legacy_included_count"] += count
        if reason is None:
            records.append((day, amount, cid, gid, True, count))

    category_totals = defaultdict(lambda: [0, 0])
    group_totals = defaultdict(lambda: [0, 0])
    month_totals = defaultdict(lambda: [0, 0])
    daily_totals = defaultdict(int)
    total = count = legacy_total = comparison_total = 0
    for day, amount, category_id, gid, is_legacy, record_count in records:
        monthly = month_totals[month_key(day)]
        monthly[0] += amount
        monthly[1] += record_count
        if previous <= day <= previous_end:
            comparison_total += amount
        if start <= day <= end:
            total += amount
            count += record_count
            legacy_total += amount if is_legacy else 0
            daily_totals[day] += amount
            for bucket in (category_totals[category_id], group_totals[gid]):
                bucket[0] += amount
                bucket[1] += record_count
    category_rows = []
    for cid, (amount, n) in category_totals.items():
        category = categories.get(cid)
        category_rows.append(
            dict(
                category_id=cid,
                name=category.name if category else "Senza categoria",
                icon_key=category.icon_key if category else "tag",
                total_cents=amount,
                count=n,
            )
        )
    group_rows = [
        dict(group_id=gid, name=groups[gid].name, total_cents=amount, count=n)
        for gid, (amount, n) in group_totals.items()
    ]
    trend = []
    for offset in range(-5, 1):
        first = month_start(start, offset)
        amount, n = month_totals[month_key(first)]
        trend.append(
            dict(month=month_key(first), total_cents=amount, count=n, is_partial=first == current)
        )
    daily = []
    cumulative = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        amount = daily_totals[day]
        cumulative += amount
        daily.append(dict(date=day, total_cents=amount, cumulative_cents=cumulative))
    return dict(
        month=month_key(start),
        current_month=month_key(current),
        available_months=sorted(available, reverse=True),
        currencies=currencies,
        currency=currency,
        period=dict(start=start, end=end, days=days, is_current=start == current),
        comparison=dict(
            month=month_key(previous),
            start=previous,
            end=previous_end,
            total_cents=comparison_total,
            change_cents=total - comparison_total,
            change_percent=round((total - comparison_total) * 100 / comparison_total, 2)
            if comparison_total
            else None,
        ),
        summary=dict(
            total_cents=total,
            expense_count=count,
            average_cents=rounded_average(total, count),
            daily_average_cents=rounded_average(total, days),
            native_total_cents=total - legacy_total,
            legacy_total_cents=legacy_total,
        ),
        coverage=coverage,
        categories=sorted(category_rows, key=lambda r: (-r["total_cents"], r["name"])),
        groups=sorted(group_rows, key=lambda r: (-r["total_cents"], r["name"])),
        trend=trend,
        daily=daily,
    )
