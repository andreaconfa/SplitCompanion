"""Private instance setup; never issues an authenticated session."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import Field, field_validator

from app.auth import DB, hasher, hash_token
from app.bootstrap import ATTEMPT_WINDOW, MAX_ATTEMPTS, setup_required, setup_state, utc
from app.models import User, now
from app.schemas import Input, Name, Password

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupComplete(Input):
    username: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_.-]{3,50}$")]
    display_name: Name
    password: Password

    @field_validator("username")
    @classmethod
    def normalize(cls, value):
        return value.lower()


@router.get("/status")
def status(s: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"setup_required": setup_required(s)}


@router.post("/complete")
def complete(
    data: SetupComplete,
    s: DB,
    response: Response,
    x_setup_token: Annotated[str, Header(max_length=256)] = "",
):
    # get_session holds BEGIN IMMEDIATE across all checks and the user insertion.
    state = setup_state(s)
    if state.completed:
        s.commit()
        raise HTTPException(409, "Configurazione già completata. Accedi con il tuo account.")
    current = now()
    if state.attempt_window_expires_at is None or utc(state.attempt_window_expires_at) <= current:
        state.attempts = 0
        state.attempt_window_expires_at = current + ATTEMPT_WINDOW
    if state.attempts >= MAX_ATTEMPTS:
        s.add(state)
        s.commit()
        raise HTTPException(
            429, "Troppi tentativi. Riprova tra 15 minuti.", headers={"Retry-After": "900"}
        )
    state.attempts += 1
    valid = bool(
        state.token_hash
        and state.expires_at
        and utc(state.expires_at) > current
        and secrets.compare_digest(state.token_hash, hash_token(x_setup_token))
    )
    if not valid:
        s.add(state)
        # Persist failures before raising; the dependency rolls back exceptions.
        s.commit()
        raise HTTPException(403, "Codice di configurazione non valido o scaduto.")
    s.add(
        User(
            username=data.username,
            display_name=data.display_name,
            password_hash=hasher.hash(data.password),
            is_admin=True,
        )
    )
    state.completed = True
    state.token_hash = None
    state.expires_at = None
    s.add(state)
    s.flush()
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}
