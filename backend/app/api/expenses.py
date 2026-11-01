from collections import defaultdict
from datetime import date
from fastapi import APIRouter, Query
from sqlmodel import select, delete
from app.auth import DB, CurrentUser
from app.models import (
    Category,
    Expense,
    ExpenseSplit,
    LegacyTransaction,
    LegacyTransactionEntry,
    now,
)
from app.schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.services.access import group_access, get_or_404, visible_ids
from app.services.records import (
    create_expense,
    expense_response,
    expense_responses,
    resolve_splits,
    delete_expense,
)
from app.services.subscription_credit_service import rebuild_credit
from app.services.category_service import category_icon

router = APIRouter(prefix="/api")


@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    user: CurrentUser,
    s: DB,
    group_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    participant_id: int | None = None,
    subscription_id: int | None = None,
    source: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    if group_id is not None:
        group_access(s, user, group_id)
    q = select(Expense).where(Expense.group_id.in_(visible_ids(s, user)))
    for col, val in [
        (Expense.group_id, group_id),
        (Expense.paid_by_user_id, payer_id),
        (Expense.subscription_id, subscription_id),
        (Expense.source, source),
    ]:
        if val is not None:
            q = q.where(col == val)
    if date_from:
        q = q.where(Expense.expense_date >= date_from)
    if date_to:
        q = q.where(Expense.expense_date <= date_to)
    if participant_id:
        q = q.where(
            Expense.id.in_(
                select(ExpenseSplit.expense_id).where(ExpenseSplit.user_id == participant_id)
            )
        )
    q = q.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return expense_responses(s, s.exec(q).all())


@router.post("/expenses", response_model=ExpenseResponse, status_code=201)
def add_expense(data: ExpenseCreate, user: CurrentUser, s: DB):
    group_access(s, user, data.group_id, True)
    return expense_response(s, create_expense(s, data, user.id))


@router.get("/expenses/{id}", response_model=ExpenseResponse)
def get_expense(id: int, user: CurrentUser, s: DB):
    e = get_or_404(s, Expense, id)
    group_access(s, user, e.group_id)
    return expense_response(s, e)


@router.patch("/expenses/{id}", response_model=ExpenseResponse)
def update_expense(id: int, data: ExpenseUpdate, user: CurrentUser, s: DB):
    e = get_or_404(s, Expense, id)
    group_access(s, user, e.group_id, True)
    if e.source == "SPLITWISE":
        raise ValueError("I movimenti importati si gestiscono tramite annullamento del batch.")
    values = data.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in ("category_id", "icon_key")):
        raise ValueError("Campo spesa non valido.")
    if "group_id" in values and values["group_id"] != e.group_id:
        raise ValueError("Non è possibile spostare una spesa tra gruppi.")
    if e.subscription_id:
        for key in ("paid_by_user_id", "currency", "expense_date"):
            if key in values and values[key] != getattr(e, key):
                raise ValueError(
                    "Per una scadenza modifica solo descrizione, importo, note e quote."
                )
    base = {
        k: getattr(e, k) for k in ExpenseCreate.model_fields if k not in ("splits", "split_mode")
    }
    base.update(values)
    if "splits" not in values:
        if "split_mode" in values:
            raise ValueError("Specifica le quote per cambiare divisione.")
        base.update(
            split_mode="exact",
            splits=[
                {"user_id": p.user_id, "amount_cents": p.amount_cents}
                for p in s.exec(select(ExpenseSplit).where(ExpenseSplit.expense_id == id)).all()
            ],
        )
    else:
        base.setdefault("split_mode", "equal")
    validated = ExpenseCreate.model_validate(base)
    parts = resolve_splits(s, validated)
    for key, value in validated.model_dump(exclude={"split_mode", "splits", "icon_key"}).items():
        setattr(e, key, value)
    s.exec(delete(ExpenseSplit).where(ExpenseSplit.expense_id == id))
    for uid, amount in parts.items():
        s.add(ExpenseSplit(expense_id=id, user_id=uid, amount_cents=amount))
    e.icon_key = None
    if "category_id" in values:
        e.category_source = "manual"
    e.updated_at = now()
    s.add(e)
    s.flush()
    if e.subscription_id:
        rebuild_credit(s, e.subscription_id)
    return expense_response(s, e)


@router.delete("/expenses/{id}")
def remove_expense(id: int, user: CurrentUser, s: DB):
    e = get_or_404(s, Expense, id)
    group_access(s, user, e.group_id, True)
    if e.source == "SPLITWISE":
        raise ValueError("Annulla il batch per eliminare una spesa importata.")
    delete_expense(s, e)
    return {"ok": True}


def legacy_response(s, t, entries=None, icons=None):
    return {
        "id": t.id,
        "group_id": t.group_id,
        "date": t.date,
        "description": t.description,
        "cost_cents": t.cost_cents,
        "currency": t.currency,
        "source": t.source,
        "category_id": t.category_id,
        "icon_key": category_icon(s, t.category_id) if icons is None else icons.get(t.category_id),
        "entries": [
            {"user_id": e.user_id, "balance_delta_cents": e.balance_delta_cents}
            for e in (
                entries
                if entries is not None
                else s.exec(
                    select(LegacyTransactionEntry).where(
                        LegacyTransactionEntry.legacy_transaction_id == t.id
                    )
                ).all()
            )
        ],
    }


@router.get("/legacy")
def legacy_list(
    user: CurrentUser,
    s: DB,
    group_id: int | None = None,
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    ids = visible_ids(s, user)
    if group_id is not None:
        group_access(s, user, group_id)
        ids = [group_id]
    rows = s.exec(
        select(LegacyTransaction)
        .where(LegacyTransaction.group_id.in_(ids))
        .order_by(LegacyTransaction.date.desc(), LegacyTransaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    icons = {c.id: c.icon_key for c in s.exec(select(Category)).all()}
    entries = defaultdict(list)
    row_ids = [row.id for row in rows]
    for offset in range(0, len(row_ids), 500):
        for entry in s.exec(
            select(LegacyTransactionEntry).where(
                LegacyTransactionEntry.legacy_transaction_id.in_(row_ids[offset : offset + 500])
            )
        ).all():
            entries[entry.legacy_transaction_id].append(entry)
    return [legacy_response(s, row, entries[row.id], icons) for row in rows]


@router.get("/legacy/{id}")
def legacy_detail(id: int, user: CurrentUser, s: DB):
    t = get_or_404(s, LegacyTransaction, id)
    group_access(s, user, t.group_id)
    return legacy_response(s, t)
