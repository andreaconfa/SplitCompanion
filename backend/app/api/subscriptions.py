from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Query
from sqlmodel import select, delete
from app.auth import DB, CurrentUser, Admin
from app.config import get_settings
from app.models import Subscription, SubscriptionSplit, SubscriptionOccurrence, Settlement, now
from app.schemas import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    AdvanceCreate,
    SettlementResponse,
)
from app.services.access import group_access, get_or_404, visible_ids, members_active
from app.services.records import subscription_response, subscription_responses, resolve_splits
from app.services.subscription_service import validate_rule, next_date, generate_due
from app.services.subscription_credit_service import credits, rebuild_credit

router = APIRouter(prefix="/api/subscriptions")


def local_today():
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def access(s, user, id, write=False):
    sub = get_or_404(s, Subscription, id)
    group_access(s, user, sub.group_id, write)
    return sub


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
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
    q = (
        select(Subscription)
        .where(Subscription.group_id.in_(ids))
        .order_by(Subscription.next_occurrence_date, Subscription.id)
        .offset(offset)
    )
    if limit is not None:
        q = q.limit(limit)
    return subscription_responses(s, s.exec(q).all())


@router.post("", response_model=SubscriptionResponse, status_code=201)
def add_subscription(data: SubscriptionCreate, user: CurrentUser, s: DB):
    group_access(s, user, data.group_id, True)
    from app.services.instance_settings import apply_currency_default

    apply_currency_default(s, data)
    validate_rule(data.recurrence_rule)
    if data.end_date and data.end_date < data.start_date:
        raise ValueError("La fine deve essere successiva all’inizio.")
    parts = resolve_splits(s, data)
    sub = Subscription(
        **data.model_dump(exclude={"split_mode", "splits", "icon_key"}),
        next_occurrence_date=data.start_date,
        created_by_user_id=user.id,
    )
    sub.category_source = "manual" if "category_id" in data.model_fields_set else None
    s.add(sub)
    s.flush()
    for uid, amount in parts.items():
        s.add(SubscriptionSplit(subscription_id=sub.id, user_id=uid, amount_cents=amount))
    s.flush()
    generate_due(s, sub, local_today())
    return subscription_response(s, sub)


@router.post("/run")
def run(admin: Admin, s: DB):
    total = 0
    for sub in s.exec(
        select(Subscription).where(Subscription.group_id.in_(visible_ids(s, admin)))
    ).all():
        total += generate_due(s, sub, local_today())
    return {"generated": total}


@router.get("/{id}", response_model=SubscriptionResponse)
def get_subscription(id: int, user: CurrentUser, s: DB):
    return subscription_response(s, access(s, user, id))


@router.patch("/{id}", response_model=SubscriptionResponse)
def update_subscription(id: int, data: SubscriptionUpdate, user: CurrentUser, s: DB):
    sub = access(s, user, id, True)
    if sub.deleted:
        raise ValueError("Abbonamento terminato.")
    generate_due(s, sub, local_today())
    values = data.model_dump(exclude_unset=True)
    if any(
        v is None for k, v in values.items() if k not in ("end_date", "category_id", "icon_key")
    ):
        raise ValueError("Campo abbonamento non valido.")
    if "group_id" in values and values["group_id"] != sub.group_id:
        raise ValueError("Non puoi spostare un abbonamento tra gruppi.")
    if values.get("paid_by_user_id", sub.paid_by_user_id) != sub.paid_by_user_id and any(
        c["remaining_cents"] for c in credits(s, id)
    ):
        raise ValueError("Non puoi cambiare il pagante finché esiste credito anticipato.")
    has_history = (
        s.exec(
            select(SubscriptionOccurrence).where(SubscriptionOccurrence.subscription_id == id)
        ).first()
        or s.exec(select(Settlement).where(Settlement.subscription_id == id)).first()
    )
    if has_history:
        for key in ("currency", "start_date"):
            if key in values and values[key] != getattr(sub, key):
                raise ValueError(
                    "Valuta e data iniziale non si modificano dopo il primo movimento."
                )
    base = {
        k: getattr(sub, k)
        for k in SubscriptionCreate.model_fields
        if k not in ("splits", "split_mode")
    }
    base.update(values)
    if "splits" not in values:
        if "split_mode" in values:
            raise ValueError("Specifica le quote per cambiare divisione.")
        base.update(
            split_mode="exact",
            splits=[
                {"user_id": p.user_id, "amount_cents": p.amount_cents}
                for p in s.exec(
                    select(SubscriptionSplit).where(SubscriptionSplit.subscription_id == id)
                ).all()
            ],
        )
    else:
        base.setdefault("split_mode", "equal")
    validated = SubscriptionCreate.model_validate(base)
    validate_rule(validated.recurrence_rule)
    if validated.end_date and validated.end_date < validated.start_date:
        raise ValueError("Data finale non valida.")
    parts = resolve_splits(s, validated)
    rule_changed = (
        validated.recurrence_rule != sub.recurrence_rule or validated.start_date != sub.start_date
    )
    for key, value in validated.model_dump(exclude={"splits", "split_mode", "icon_key"}).items():
        setattr(sub, key, value)
    if rule_changed:
        latest = s.exec(
            select(SubscriptionOccurrence)
            .where(SubscriptionOccurrence.subscription_id == id)
            .order_by(SubscriptionOccurrence.occurrence_date.desc())
        ).first()
        sub.next_occurrence_date = (
            next_date(sub.recurrence_rule, sub.start_date, latest.occurrence_date)
            if latest
            else sub.start_date
        )
    s.exec(delete(SubscriptionSplit).where(SubscriptionSplit.subscription_id == id))
    for uid, amount in parts.items():
        s.add(SubscriptionSplit(subscription_id=id, user_id=uid, amount_cents=amount))
    sub.icon_key = None
    if "category_id" in values:
        sub.category_source = "manual"
    sub.updated_at = now()
    s.add(sub)
    s.flush()
    return subscription_response(s, sub)


@router.delete("/{id}")
def terminate(id: int, user: CurrentUser, s: DB):
    sub = access(s, user, id, True)
    generate_due(s, sub, local_today())
    sub.active = False
    sub.deleted = True
    sub.updated_at = now()
    s.add(sub)
    return {"ok": True}


@router.post("/{id}/pause", response_model=SubscriptionResponse)
def pause(id: int, user: CurrentUser, s: DB):
    sub = access(s, user, id, True)
    generate_due(s, sub, local_today())
    sub.active = False
    sub.updated_at = now()
    s.add(sub)
    s.flush()
    return subscription_response(s, sub)


@router.post("/{id}/resume", response_model=SubscriptionResponse)
def resume(id: int, user: CurrentUser, s: DB):
    sub = access(s, user, id, True)
    if sub.deleted:
        raise ValueError("Abbonamento terminato: crea un nuovo abbonamento.")
    if sub.end_date and sub.end_date < local_today():
        raise ValueError("Aggiorna la data finale prima di riprendere.")
    sub.active = True
    sub.updated_at = now()
    s.add(sub)
    generate_due(s, sub, local_today())
    return subscription_response(s, sub)


@router.get("/{id}/credits")
def get_credits(id: int, user: CurrentUser, s: DB):
    access(s, user, id)
    return credits(s, id)


@router.get("/{id}/advances", response_model=list[SettlementResponse])
def get_advances(id: int, user: CurrentUser, s: DB):
    access(s, user, id)
    return [
        SettlementResponse.model_validate(t)
        for t in s.exec(
            select(Settlement)
            .where(Settlement.subscription_id == id, Settlement.kind == "SUBSCRIPTION_ADVANCE")
            .order_by(Settlement.settlement_date)
        ).all()
    ]


def transfer(s, sub, data, user, refund=False):
    members_active(s, sub.group_id, [sub.paid_by_user_id, data.user_id])
    if data.user_id == sub.paid_by_user_id:
        raise ValueError("Il pagante non può anticipare denaro a se stesso.")
    if data.settlement_date > local_today():
        raise ValueError("Registra solo trasferimenti già avvenuti.")
    if not refund and sub.deleted:
        raise ValueError("Abbonamento terminato: puoi solo rimborsare il credito.")
    if (
        not refund
        and not s.exec(
            select(SubscriptionSplit).where(
                SubscriptionSplit.subscription_id == sub.id,
                SubscriptionSplit.user_id == data.user_id,
            )
        ).first()
    ):
        raise ValueError("La persona deve partecipare all’abbonamento.")
    generate_due(s, sub, local_today())
    t = Settlement(
        group_id=sub.group_id,
        paid_by_user_id=sub.paid_by_user_id if refund else data.user_id,
        paid_to_user_id=data.user_id if refund else sub.paid_by_user_id,
        amount_cents=data.amount_cents,
        currency=sub.currency,
        settlement_date=data.settlement_date,
        kind="SUBSCRIPTION_REFUND" if refund else "SUBSCRIPTION_ADVANCE",
        subscription_id=sub.id,
        notes=data.notes,
        created_by_user_id=user.id,
    )
    s.add(t)
    s.flush()
    rebuild_credit(s, sub.id)
    return SettlementResponse.model_validate(t)


@router.post("/{id}/advances", response_model=SettlementResponse, status_code=201)
def add_advance(id: int, data: AdvanceCreate, user: CurrentUser, s: DB):
    return transfer(s, access(s, user, id, True), data, user)


@router.post("/{id}/refunds", response_model=SettlementResponse, status_code=201)
def add_refund(id: int, data: AdvanceCreate, user: CurrentUser, s: DB):
    return transfer(s, access(s, user, id, True), data, user, True)
