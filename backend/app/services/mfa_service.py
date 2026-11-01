"""Local TOTP secrets, one-use challenges and durable authentication rate limits."""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from cryptography.fernet import Fernet
from fastapi import HTTPException
import pyotp
from sqlalchemy import text
from sqlmodel import select, delete
from app.auth import hash_token
from app.config import get_settings
from app.models import AuthThrottle, MFAChallenge, MFARecovery, User, now


def cipher():
    key = hmac.new(
        get_settings().secret_key.encode(), b"split-companion/totp/v1", hashlib.sha256
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def throttle(s, request, purpose, account):
    """Commit only counters before auth mutations; re-acquire the SQLite write lock."""
    stamp = now()
    s.exec(delete(AuthThrottle).where(AuthThrottle.expires_at <= stamp))
    ip = request.client.host if request.client else "local"
    keys = [(f"{purpose}:ip:{ip}", 100), (f"{purpose}:account:{account}", 10)]
    blocked = False
    for raw, limit in keys:
        key = hash_token(raw)
        row = s.get(AuthThrottle, key)
        if row is None:
            row = AuthThrottle(key=key, expires_at=stamp + timedelta(minutes=5))
        blocked = blocked or row.attempts >= limit
        row.attempts = min(row.attempts + 1, limit)
        s.add(row)
        if blocked:
            break
    s.commit()
    s.execute(text("BEGIN IMMEDIATE"))
    if blocked:
        raise HTTPException(429, "Troppi tentativi. Riprova tra cinque minuti.")


def issue_challenge(s, user):
    s.exec(delete(MFAChallenge).where(MFAChallenge.expires_at <= now()))
    s.exec(delete(MFAChallenge).where(MFAChallenge.user_id == user.id))
    token = secrets.token_urlsafe(32)
    purpose = "verify" if user.mfa_enabled else "setup"
    s.add(
        MFAChallenge(
            token_hash=hash_token(token),
            user_id=user.id,
            purpose=purpose,
            expires_at=now() + timedelta(minutes=5),
        )
    )
    return {
        "status": "mfa_required" if user.mfa_enabled else "mfa_setup_required",
        "challenge_token": token,
    }


def get_challenge(s, request, token, purpose):
    # Invalid tokens share one per-IP budget; valid tokens additionally share the user's budget.
    row = s.get(MFAChallenge, hash_token(token))
    account = (
        str(row.user_id)
        if row
        else "invalid:" + (request.client.host if request.client else "local")
    )
    throttle(s, request, "mfa", account)
    # Counters commit above, so reload after reacquiring the serialized write transaction.
    s.expire_all()
    row = s.get(MFAChallenge, hash_token(token))
    user = s.get(User, row.user_id) if row else None
    if (
        not row
        or row.purpose != purpose
        or row.expires_at <= now()
        or not user
        or not user.is_active
    ):
        raise HTTPException(401, "Verifica scaduta o non valida. Accedi di nuovo.")
    if user.mfa_enabled != (purpose == "verify"):
        raise HTTPException(401, "Verifica non valida.")
    return row, user


def check_totp(user, secret, code):
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    totp = pyotp.TOTP(secret)
    counter = int(time.time()) // 30
    for offset in (-1, 0, 1):
        candidate = counter + offset
        if hmac.compare_digest(totp.at(candidate * 30), code) and candidate > user.mfa_last_counter:
            user.mfa_last_counter = candidate
            return True
    return False


def verify_factor(s, user, code):
    if user.mfa_secret and check_totp(
        user, cipher().decrypt(user.mfa_secret.encode()).decode(), code
    ):
        s.add(user)
        return True
    recovery = s.get(MFARecovery, hash_token("recovery:" + code))
    if recovery and recovery.user_id == user.id:
        s.delete(recovery)
        return True
    return False


def rotate_recovery(s, user):
    s.exec(delete(MFARecovery).where(MFARecovery.user_id == user.id))
    codes = [secrets.token_hex(10) for _ in range(10)]
    for code in codes:
        s.add(MFARecovery(code_hash=hash_token("recovery:" + code), user_id=user.id))
    return codes


def revoke_user_auth(s, user_id):
    """Revoke every auth and push capability, including queued notifications."""
    from app.models import AuthSession
    from app.push_models import PushDevice, PushOutbox

    for device in s.exec(select(PushDevice).where(PushDevice.user_id == user_id)).all():
        s.exec(delete(PushOutbox).where(PushOutbox.device_id == device.id))
        s.delete(device)
    s.exec(delete(MFAChallenge).where(MFAChallenge.user_id == user_id))
    s.exec(delete(AuthSession).where(AuthSession.user_id == user_id))
