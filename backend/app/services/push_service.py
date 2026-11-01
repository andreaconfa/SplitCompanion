"""Transactional queue with bounded, privacy-preserving Web Push delivery."""

import base64
import json
import os
import socket
import ipaddress
import threading
from datetime import timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from sqlmodel import Session, select
from app.models import User, GroupMember, Expense, ExpenseSplit, now
from app.push_models import PushDevice, PushOutbox
from app.config import get_settings

_lock = threading.Lock()


def validate_endpoint(value):
    try:
        u = urlsplit(value)
        host = u.hostname or ""
        allowed = host in {
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
            "web.push.apple.com",
        } or (host.endswith(".push.apple.com") and host.count(".") == 3)
        if not (
            len(value) <= 2048
            and u.scheme == "https"
            and allowed
            and u.port in (None, 443)
            and not u.username
            and not u.password
            and not u.fragment
            and not u.query
            and u.path.startswith("/")
            and not any(c.isspace() for c in value)
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Servizio push non supportato o indirizzo non valido.") from None
    return value


def vapid_keys():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    cfg = get_settings()
    path = Path(cfg.push_vapid_path or str(Path(cfg.db).parent / "push-vapid.pem"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if not path.exists():
            key = ec.generate_private_key(ec.SECP256R1())
            data = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
            except FileExistsError:
                pass
        os.chmod(path, 0o600)
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return str(path), base64.urlsafe_b64encode(public).decode().rstrip("=")


def expense_event_key(expense):
    return f"expense:{expense.id}:{expense.created_at.replace(tzinfo=timezone.utc).isoformat()}"


def enqueue_expense(s, expense, actor_id):
    if expense.source != "NATIVE":
        return
    ids = set(
        s.exec(select(ExpenseSplit.user_id).where(ExpenseSplit.expense_id == expense.id)).all()
    ) | {expense.paid_by_user_id}
    ids.discard(actor_id)
    for device in s.exec(select(PushDevice).where(PushDevice.user_id.in_(ids))).all():
        user = s.get(User, device.user_id)
        member = s.exec(
            select(GroupMember).where(
                GroupMember.group_id == expense.group_id,
                GroupMember.user_id == device.user_id,
                GroupMember.active == True,
            )
        ).first()
        event = expense_event_key(expense)
        exists = s.exec(
            select(PushOutbox).where(
                PushOutbox.device_id == device.id, PushOutbox.event_key == event
            )
        ).first()
        if user and user.is_active and member and not exists:
            s.add(
                PushOutbox(
                    device_id=device.id,
                    event_key=event,
                    expense_id=expense.id,
                    expires_at=now() + timedelta(hours=24),
                )
            )
    s.flush()


def valid_delivery(s, device, job):
    if not device:
        return False
    user = s.get(User, device.user_id)
    if not user or not user.is_active:
        return False
    if job.expense_id is None:
        return True
    expense = s.get(Expense, job.expense_id)
    if not expense or job.event_key != expense_event_key(expense):
        return False
    involved = (
        expense.paid_by_user_id == user.id
        or s.exec(
            select(ExpenseSplit).where(
                ExpenseSplit.expense_id == expense.id, ExpenseSplit.user_id == user.id
            )
        ).first()
    )
    return bool(
        involved
        and s.exec(
            select(GroupMember).where(
                GroupMember.group_id == expense.group_id,
                GroupMember.user_id == user.id,
                GroupMember.active == True,
            )
        ).first()
    )


def send_push(subscription, payload):
    from pywebpush import webpush
    import requests

    class NoRedirectSession(requests.Session):
        def request(self, method, url, **kwargs):
            validate_endpoint(url)
            addresses = socket.getaddrinfo(urlsplit(url).hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(
                not ipaddress.ip_address(item[4][0]).is_global for item in addresses
            ):
                raise ValueError("Il servizio push non risolve a un indirizzo pubblico.")
            kwargs["allow_redirects"] = False
            return super().request(method, url, **kwargs)

    key, _ = vapid_keys()
    with NoRedirectSession() as http:
        http.trust_env = False
        result = webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=key,
            vapid_claims={
                "sub": get_settings().push_vapid_subject
                or get_settings().public_origin
                or "mailto:admin@example.invalid"
            },
            ttl=3600,
            timeout=10,
            requests_session=http,
        )
        return result.status_code


def dispatch_push(engine, sender=None):
    if not get_settings().push_enabled:
        return
    sender = sender or send_push
    with Session(engine) as s:
        ids = list(
            s.exec(
                select(PushOutbox.id)
                .where(
                    PushOutbox.status.in_(["pending", "sending"]), PushOutbox.next_attempt <= now()
                )
                .order_by(PushOutbox.id)
                .limit(50)
            ).all()
        )
    for id in ids:
        # Claim + commit before networking. Leases recover jobs after process death.
        with Session(engine) as s:
            from sqlalchemy import text

            s.execute(text("BEGIN IMMEDIATE"))
            job = s.get(PushOutbox, id)
            if (
                not job
                or job.status not in ("pending", "sending")
                or job.next_attempt.replace(tzinfo=timezone.utc) > now()
            ):
                continue
            device = s.get(PushDevice, job.device_id)
            if (
                job.expires_at.replace(tzinfo=timezone.utc) <= now()
                or job.attempts >= 5
                or not valid_delivery(s, device, job)
            ):
                job.status = "discarded"
                s.add(job)
                s.commit()
                continue
            subscription = {
                "endpoint": validate_endpoint(device.endpoint),
                "keys": {"p256dh": device.p256dh, "auth": device.auth},
            }
            payload = {
                "title": "Split Companion",
                "body": "Una nuova spesa ti coinvolge."
                if job.expense_id
                else "Le notifiche su questo dispositivo sono attive.",
                "url": f"/expenses/{job.expense_id}" if job.expense_id else "/profile",
                "tag": job.event_key,
            }
            job.status = "sending"
            job.attempts += 1
            job.next_attempt = now() + timedelta(minutes=2)
            s.add(job)
            s.commit()
        status = 0
        try:
            status = sender(subscription, payload)
        except Exception as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", 0)
            # Never log exceptions: providers may include endpoint and encryption keys.
        with Session(engine) as s:
            job = s.get(PushOutbox, id)
            if not job:
                continue
            if status in (404, 410):
                device = s.get(PushDevice, job.device_id)
                if device:
                    s.delete(device)
                job.status = "discarded"
            elif 200 <= status < 300:
                job.status = "sent"
            elif (
                job.attempts >= 5
                or (400 <= status < 500 and status not in (408, 429))
                or 300 <= status < 400
            ):
                job.status = "failed"
            else:
                job.status = "pending"
                job.next_attempt = now() + timedelta(seconds=min(3600, 30 * 2**job.attempts))
            s.add(job)
            s.commit()
