import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session
from app.config import get_settings
from app.db import get_session
from app.models import User, AuthSession, now

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
DB = Annotated[Session, Depends(get_session, scope="function")]


def hash_token(token):
    return hmac.new(get_settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def verify_password(stored, password):
    try:
        return hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def create_session(session, user, mfa_verified=False):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            mfa_verified=mfa_verified,
            csrf_token=csrf,
            expires_at=now() + timedelta(hours=get_settings().session_hours),
        )
    )
    session.flush()
    return token, csrf


def current_user(request: Request, session: DB):
    token = request.cookies.get("split_session", "")
    auth = session.get(AuthSession, hash_token(token)) if token else None
    if not auth or auth.expires_at <= now():
        raise HTTPException(401, "Accedi per continuare.")
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account non attivo.")
    if (get_settings().mfa_required or user.mfa_enabled) and not auth.mfa_verified:
        raise HTTPException(401, "Completa la verifica a due fattori.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
        request.headers.get("X-CSRF-Token", ""), auth.csrf_token
    ):
        raise HTTPException(403, "Sessione non valida. Ricarica la pagina.")
    request.state.auth = auth
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def admin_user(user: CurrentUser):
    if not user.is_admin:
        raise HTTPException(403, "Questa funzione è riservata agli amministratori.")
    return user


Admin = Annotated[User, Depends(admin_user)]
