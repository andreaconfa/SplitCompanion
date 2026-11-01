"""Single-use, operator-authorized first administrator provisioning."""

import secrets
from datetime import timedelta, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.auth import hash_token
from app.models import SetupState, User, now

TOKEN_LIFETIME = timedelta(minutes=30)
ATTEMPT_WINDOW = timedelta(minutes=15)
MAX_ATTEMPTS = 5


def setup_required(session: Session) -> bool:
    state = session.get(SetupState, 1)
    return (
        not (state and state.completed) and session.exec(select(User.id).limit(1)).first() is None
    )


def setup_state(session: Session) -> SetupState:
    state = session.get(SetupState, 1)
    if state is None:
        state = SetupState(id=1)
    if session.exec(select(User.id).limit(1)).first() is not None:
        state.completed = True
        state.token_hash = None
        state.expires_at = None
    session.add(state)
    session.flush()
    return state


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def issue_setup_token(engine) -> str:
    """Rotate a setup code. Only the caller receives the plaintext."""
    with Session(engine) as session:
        session.execute(text("BEGIN IMMEDIATE"))
        state = setup_state(session)
        if state.completed:
            session.commit()
            raise ValueError("Configurazione già completata: usa un amministratore esistente.")
        token = secrets.token_urlsafe(32)
        state.token_hash = hash_token(token)
        state.expires_at = now() + TOKEN_LIFETIME
        state.attempts = 0
        state.attempt_window_expires_at = None
        session.add(state)
        session.commit()
        return token
