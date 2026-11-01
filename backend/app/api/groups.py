from fastapi import APIRouter, HTTPException
from sqlmodel import select
from app.auth import DB, CurrentUser
from app.models import Group, GroupMember, User, Subscription, SubscriptionSplit, now
from app.schemas import GroupCreate, GroupUpdate, GroupResponse, MemberCreate
from app.services.access import group_access, get_or_404, visible_ids
from app.services.balance_service import balances, debts

router = APIRouter(prefix="/api/groups")


@router.get("", response_model=list[GroupResponse])
def list_groups(user: CurrentUser, s: DB):
    return [
        GroupResponse.model_validate(g)
        for g in s.exec(
            select(Group).where(Group.id.in_(visible_ids(s, user))).order_by(Group.name)
        ).all()
    ]


@router.post("", response_model=GroupResponse, status_code=201)
def create_group(data: GroupCreate, user: CurrentUser, s: DB):
    g = Group(name=data.name, description=data.description, created_by_user_id=user.id)
    s.add(g)
    s.flush()
    for uid in sorted(set(data.member_ids + [user.id])):
        u = get_or_404(s, User, uid)
        if not u.is_active:
            raise ValueError("Utente non attivo.")
        s.add(GroupMember(group_id=g.id, user_id=uid))
    s.flush()
    return GroupResponse.model_validate(g)


@router.get("/{id}", response_model=GroupResponse)
def get_group(id: int, user: CurrentUser, s: DB):
    return GroupResponse.model_validate(group_access(s, user, id))


@router.patch("/{id}", response_model=GroupResponse)
def update_group(id: int, data: GroupUpdate, user: CurrentUser, s: DB):
    g = group_access(s, user, id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            raise ValueError("Campo gruppo non valido.")
        setattr(g, key, value)
    g.updated_at = now()
    s.add(g)
    s.flush()
    return GroupResponse.model_validate(g)


@router.get("/{id}/members")
def members(id: int, user: CurrentUser, s: DB):
    group_access(s, user, id)
    return [
        {
            "id": m.id,
            "user_id": u.id,
            "display_name": u.display_name,
            "username": u.username,
            "active": m.active and u.is_active,
        }
        for m, u in s.exec(
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == id)
        ).all()
    ]


@router.post("/{id}/members")
def add_member(id: int, data: MemberCreate, user: CurrentUser, s: DB):
    group_access(s, user, id, True)
    u = get_or_404(s, User, data.user_id)
    if not u.is_active:
        raise ValueError("Utente non attivo.")
    m = s.exec(
        select(GroupMember).where(GroupMember.group_id == id, GroupMember.user_id == u.id)
    ).first()
    if m:
        m.active = True
    else:
        m = GroupMember(group_id=id, user_id=u.id)
    s.add(m)
    s.flush()
    return {
        "id": m.id,
        "user_id": u.id,
        "display_name": u.display_name,
        "username": u.username,
        "active": True,
    }


@router.delete("/{id}/members/{user_id}")
def remove_member(id: int, user_id: int, user: CurrentUser, s: DB):
    g = group_access(s, user, id, True)
    if user.id != g.created_by_user_id and not user.is_admin:
        raise HTTPException(403, "Solo il creatore o un amministratore può rimuovere membri.")
    if user_id == g.created_by_user_id:
        raise ValueError("Non puoi rimuovere il creatore del gruppo.")
    if any(b["balance_cents"] for b in balances(s, id) if b["user_id"] == user_id):
        raise ValueError("Sistema prima i saldi del membro.")
    subs = s.exec(
        select(Subscription).where(Subscription.group_id == id, Subscription.deleted == False)
    ).all()
    for sub in subs:
        if (
            sub.paid_by_user_id == user_id
            or s.exec(
                select(SubscriptionSplit).where(
                    SubscriptionSplit.subscription_id == sub.id,
                    SubscriptionSplit.user_id == user_id,
                )
            ).first()
        ):
            raise ValueError("Rimuovi prima il membro dagli abbonamenti.")
    m = s.exec(
        select(GroupMember).where(GroupMember.group_id == id, GroupMember.user_id == user_id)
    ).first()
    if not m:
        raise HTTPException(404, "Membro non trovato.")
    m.active = False
    s.add(m)
    return {"ok": True}


@router.get("/{id}/balances")
def group_balances(id: int, user: CurrentUser, s: DB):
    group_access(s, user, id)
    return balances(s, id)


@router.get("/{id}/debts")
def group_debts(id: int, user: CurrentUser, s: DB):
    group_access(s, user, id)
    return debts(s, id)
