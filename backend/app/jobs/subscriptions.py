import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlmodel import Session, select
from sqlalchemy import text
from app.config import get_settings
from app.models import Subscription
from app.services.subscription_service import generate_due

logger = logging.getLogger(__name__)


def run_subscriptions(engine, today=None):
    today = today or datetime.now(ZoneInfo(get_settings().timezone)).date()
    with Session(engine) as s:
        ids = list(
            s.exec(
                select(Subscription.id).where(
                    Subscription.active == True, Subscription.deleted == False
                )
            ).all()
        )
    total = 0
    failed = False
    for sid in ids:
        try:
            with Session(engine) as s:
                s.execute(text("BEGIN IMMEDIATE"))
                sub = s.get(Subscription, sid)
                if sub:
                    total += generate_due(s, sub, today)
                s.commit()
        except Exception:
            failed = True
            logger.error("Generazione scadenze fallita; dati dell’abbonamento omessi.")
    if failed:
        raise RuntimeError("Generazione di alcune scadenze fallita.")
    return total
