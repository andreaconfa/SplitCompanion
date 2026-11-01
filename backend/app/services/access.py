from fastapi import HTTPException
from sqlmodel import select
from app.models import Group, GroupMember, User


def get_or_404(session, model, id):
    obj = session.get(model, id)
    if obj is None:
        raise HTTPException(404, "Elemento non trovato.")
    return obj


def group_access(session, user, group_id, write=False):
    group = get_or_404(session, Group, group_id)
    member = session.exec(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id,
            GroupMember.active == True,
        )
    ).first()
    if not member:
        raise HTTPException(403, "Non hai accesso a questo gruppo.")
    if write and group.archived:
        raise HTTPException(409, "Il gruppo è archiviato. Riattivalo prima di modificarlo.")
    return group


def members_active(session, group_id, ids):
    for uid in set(ids):
        member = session.exec(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == uid,
                GroupMember.active == True,
            )
        ).first()
        user = session.get(User, uid)
        if not member or not user or not user.is_active:
            raise ValueError("Tutti i partecipanti devono essere membri attivi del gruppo.")


def visible_ids(session, user):
    return list(
        session.exec(
            select(GroupMember.group_id).where(
                GroupMember.user_id == user.id, GroupMember.active == True
            )
        ).all()
    )
