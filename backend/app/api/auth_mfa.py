import io
import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from sqlmodel import select, delete
from app.auth import DB, CurrentUser, current_user, verify_password
from app.config import get_settings
from app.models import MFAChallenge, MFARecovery, AuthSession
from app.schemas import Input
from app.services.mfa_service import (
    cipher,
    get_challenge,
    check_totp,
    verify_factor,
    rotate_recovery,
    throttle,
)
from app.api.auth_users import finish_login

router = APIRouter(prefix="/api/auth/mfa")


class ChallengeInput(Input):
    challenge_token: str = Field(min_length=1, max_length=256)


class VerifyInput(ChallengeInput):
    code: str = Field(min_length=1, max_length=128)


class RecoveryInput(Input):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=1, max_length=128)


@router.post("/setup")
def setup(data: ChallengeInput, request: Request, s: DB):
    row, user = get_challenge(s, request, data.challenge_token, "setup")
    if row.secret is None:
        row.secret = cipher().encrypt(pyotp.random_base32().encode()).decode()
        s.add(row)
    secret = cipher().decrypt(row.secret.encode()).decode()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name="Split Companion")
    output = io.BytesIO()
    qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage).save(output)
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": output.getvalue().decode()}


@router.post("/confirm")
def confirm(data: VerifyInput, request: Request, response: Response, s: DB):
    row, user = get_challenge(s, request, data.challenge_token, "setup")
    if not row.secret or not check_totp(
        user, cipher().decrypt(row.secret.encode()).decode(), data.code
    ):
        raise HTTPException(401, "Codice non valido.")
    user.mfa_secret = row.secret
    user.mfa_enabled = True
    s.add(user)
    s.exec(delete(AuthSession).where(AuthSession.user_id == user.id))
    codes = rotate_recovery(s, user)
    s.exec(delete(MFAChallenge).where(MFAChallenge.user_id == user.id))
    return {"session": finish_login(s, user, request, response, True), "recovery_codes": codes}


@router.post("/verify")
def verify(data: VerifyInput, request: Request, response: Response, s: DB):
    row, user = get_challenge(s, request, data.challenge_token, "verify")
    if not verify_factor(s, user, data.code):
        raise HTTPException(401, "Codice non valido o già utilizzato.")
    s.delete(row)
    return finish_login(s, user, request, response, True)


@router.get("/status")
def status(user: CurrentUser, s: DB):
    codes = s.exec(select(MFARecovery).where(MFARecovery.user_id == user.id)).all()
    return {
        "enabled": user.mfa_enabled,
        "required": get_settings().mfa_required,
        "recovery_codes_remaining": len(codes),
    }


@router.post("/recovery-codes")
def recovery_codes(data: RecoveryInput, request: Request, user: CurrentUser, s: DB):
    throttle(s, request, "mfa", str(user.id))
    s.expire_all()
    user = current_user(request, s)
    if (
        not user.mfa_enabled
        or not verify_password(user.password_hash, data.password)
        or not verify_factor(s, user, data.code)
    ):
        raise HTTPException(401, "Password o codice non valido.")
    return {"recovery_codes": rotate_recovery(s, user)}
