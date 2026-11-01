import base64
import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import select, delete
from app.auth import DB, CurrentUser, hash_token
from app.push_models import PushDevice, PushOutbox
from app.models import now
from app.services.push_service import validate_endpoint, vapid_keys

router = APIRouter(prefix="/api/push")


class Endpoint(BaseModel):
    endpoint: str = Field(max_length=2048)
    _validate = field_validator("endpoint")(validate_endpoint)


class SubscriptionInput(Endpoint):
    keys: dict[str, str]

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, values):
        from cryptography.hazmat.primitives.asymmetric import ec

        try:
            if set(values) != {"p256dh", "auth"} or any(len(v) > 128 for v in values.values()):
                raise ValueError()
            public = base64.urlsafe_b64decode(values["p256dh"] + "=" * (-len(values["p256dh"]) % 4))
            auth = base64.urlsafe_b64decode(values["auth"] + "=" * (-len(values["auth"]) % 4))
            if len(auth) != 16 or len(public) != 65:
                raise ValueError()
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
        except (KeyError, ValueError, TypeError):
            raise ValueError("Chiavi push non valide.") from None
        return {key: values[key] for key in ("p256dh", "auth")}


def secure(request):
    if request.url.scheme != "https":
        raise HTTPException(409, "Le notifiche richiedono una connessione HTTPS.")


def own_device(s, endpoint, user):
    device = s.exec(select(PushDevice).where(PushDevice.endpoint == endpoint)).first()
    if device and device.user_id != user.id:
        raise HTTPException(
            409,
            "Questo dispositivo è associato a un altro account. Disattiva le notifiche nel browser e riprova.",
        )
    return device


@router.get("/config")
def config(request: Request, user: CurrentUser):
    secure(request)
    return {"public_key": vapid_keys()[1]}


@router.post("/status")
def status(data: Endpoint, request: Request, user: CurrentUser, s: DB):
    secure(request)
    device = own_device(s, data.endpoint, user)
    return {"enabled": bool(device)}


@router.post("/subscriptions")
def subscribe(
    data: SubscriptionInput, request: Request, response: Response, user: CurrentUser, s: DB
):
    secure(request)
    previous = browser_device(s, request)
    if previous and previous.endpoint != data.endpoint:
        revoke_browser(s, request, response)
    device = own_device(s, data.endpoint, user)
    if not device:
        if len(s.exec(select(PushDevice).where(PushDevice.user_id == user.id)).all()) >= 20:
            raise HTTPException(409, "Limite di dispositivi raggiunto.")
        device = PushDevice(
            user_id=user.id,
            endpoint=data.endpoint,
            p256dh=data.keys["p256dh"],
            auth=data.keys["auth"],
            session_hash=request.state.auth.token_hash,
        )
    device.p256dh, device.auth = data.keys["p256dh"], data.keys["auth"]
    device.session_hash = request.state.auth.token_hash
    s.add(device)
    s.flush()
    response.set_cookie(
        "split_push_device",
        f"{device.id}.{hash_token('push:' + str(device.id))}",
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=365 * 86400,
        path="/",
    )
    return {"enabled": True}


@router.delete("/subscriptions")
def unsubscribe(data: Endpoint, request: Request, user: CurrentUser, s: DB):
    secure(request)
    device = own_device(s, data.endpoint, user)
    if device:
        s.exec(delete(PushOutbox).where(PushOutbox.device_id == device.id))
        s.delete(device)
    return {"enabled": False}


@router.post("/test")
def test_push(data: Endpoint, request: Request, user: CurrentUser, s: DB):
    secure(request)
    device = own_device(s, data.endpoint, user)
    if not device:
        raise HTTPException(409, "Attiva prima le notifiche su questo dispositivo.")
    recent = s.exec(
        select(PushOutbox).where(
            PushOutbox.device_id == device.id,
            PushOutbox.expense_id.is_(None),
            PushOutbox.created_at > now() - timedelta(minutes=1),
        )
    ).first()
    if recent:
        raise HTTPException(429, "Attendi un minuto prima di inviare un altro test.")
    s.add(
        PushOutbox(
            device_id=device.id,
            event_key="test:" + secrets.token_hex(12),
            expires_at=now() + timedelta(minutes=10),
        )
    )
    return {"queued": True}


def revoke_session(s, token_hash):
    devices = s.exec(select(PushDevice).where(PushDevice.session_hash == token_hash)).all()
    for device in devices:
        s.exec(delete(PushOutbox).where(PushOutbox.device_id == device.id))
        s.delete(device)


def browser_device(s, request):
    value = request.cookies.get("split_push_device", "")
    parts = value.split(".")
    if (
        len(parts) != 2
        or not parts[0].isdigit()
        or not secrets.compare_digest(parts[1], hash_token("push:" + parts[0]))
    ):
        return None
    return s.get(PushDevice, int(parts[0]))


def revoke_browser(s, request, response, new_user_id=None):
    device = browser_device(s, request)
    if device and device.user_id != new_user_id:
        s.exec(delete(PushOutbox).where(PushOutbox.device_id == device.id))
        s.delete(device)
        response.delete_cookie("split_push_device", path="/")
