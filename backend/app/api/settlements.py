from fastapi import APIRouter, Query
from sqlmodel import select, delete
from app.auth import DB, CurrentUser
from app.models import Settlement, SubscriptionAdvanceApplication, AdvanceRefundAllocation
from app.schemas import SettlementCreate, SettlementResponse
from app.services.access import group_access, get_or_404, visible_ids, members_active
from app.services.subscription_credit_service import rebuild_credit

router = APIRouter(prefix="/api/settlements")


@router.get("", response_model=list[SettlementResponse])
def list_settlements(
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
    return [
        SettlementResponse.model_validate(t)
        for t in s.exec(
            select(Settlement)
            .where(Settlement.group_id.in_(ids))
            .order_by(Settlement.settlement_date.desc(), Settlement.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    ]


@router.post("", response_model=SettlementResponse, status_code=201)
def add_settlement(data: SettlementCreate, user: CurrentUser, s: DB):
    group_access(s, user, data.group_id, True)
    members_active(s, data.group_id, [data.paid_by_user_id, data.paid_to_user_id])
    if data.paid_by_user_id == data.paid_to_user_id:
        raise ValueError("Scegli due persone diverse.")
    t = Settlement(**data.model_dump(), created_by_user_id=user.id)
    s.add(t)
    s.flush()
    return SettlementResponse.model_validate(t)


@router.get("/{id}", response_model=SettlementResponse)
def get_settlement(id: int, user: CurrentUser, s: DB):
    t = get_or_404(s, Settlement, id)
    group_access(s, user, t.group_id)
    return SettlementResponse.model_validate(t)


@router.delete("/{id}")
def remove_settlement(id: int, user: CurrentUser, s: DB):
    t = get_or_404(s, Settlement, id)
    group_access(s, user, t.group_id, True)
    if t.source == "SPLITWISE":
        raise ValueError("Annulla il batch per eliminare un pagamento importato.")
    if t.kind == "SUBSCRIPTION_ADVANCE":
        if (
            s.exec(
                select(SubscriptionAdvanceApplication).where(
                    SubscriptionAdvanceApplication.advance_settlement_id == id
                )
            ).first()
            or s.exec(
                select(AdvanceRefundAllocation).where(
                    AdvanceRefundAllocation.advance_settlement_id == id
                )
            ).first()
        ):
            raise ValueError(
                "L’anticipo è già stato utilizzato o rimborsato e non può essere eliminato."
            )
    if t.kind == "SUBSCRIPTION_REFUND":
        s.exec(
            delete(AdvanceRefundAllocation).where(
                AdvanceRefundAllocation.refund_settlement_id == id
            )
        )
    sid = t.subscription_id
    s.delete(t)
    s.flush()
    if sid:
        rebuild_credit(s, sid)
    return {"ok": True}
