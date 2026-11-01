import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session
from app.config import get_settings
from app import operations
from app.version import SERVER_VERSION, API_VERSION
from app.auth import Admin, DB
from app.api.setup import router as setup_router
from app.bootstrap import setup_required
import uuid
import time
from app.upload_limit import ImportBodyLimit
from app import db
from app.jobs.subscriptions import run_subscriptions
from app.api import auth_mfa, auth_users, groups, expenses, settlements, subscriptions, dashboard
from app.api.imports import router as imports_router
from app.api.categories import router as categories_router
from app.api.push import router as push_router
from app.api.avatars import router as avatars_router
from app.services.category_service import seed as seed_categories
from app.services.push_service import dispatch_push

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    cfg = get_settings()
    if len(cfg.secret_key) < 32:
        raise RuntimeError(
            "SPLIT_COMPANION_SECRET_KEY deve avere almeno 32 caratteri. Vedi README."
        )
    with Session(db.engine) as s:
        s.execute(text("BEGIN IMMEDIATE"))
        s.execute(text("SELECT id FROM user LIMIT 1"))
        seed_categories(s)
        s.commit()
    scheduler = None
    if cfg.scheduler:
        operations.run_job("subscriptions", run_subscriptions, db.engine)
        scheduler = BackgroundScheduler(timezone=cfg.timezone)
        scheduler.add_job(
            operations.run_job,
            "interval",
            hours=1,
            args=["subscriptions", run_subscriptions, db.engine],
            id="subscriptions",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            operations.run_job,
            "interval",
            seconds=15,
            args=["push", dispatch_push, db.engine],
            id="push-notifications",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            operations.run_job,
            "interval",
            hours=1,
            args=["maintenance", operations.maintenance, db.engine],
            id="maintenance",
            max_instances=1,
            coalesce=True,
        )
        if cfg.backups_enabled:
            scheduler.add_job(
                operations.run_job,
                "cron",
                hour=cfg.backup_hour,
                args=["backup", operations.daily_backup],
                id="backup",
                max_instances=1,
                coalesce=True,
            )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=True)


app = FastAPI(title="Split Companion", version=SERVER_VERSION, lifespan=lifespan)
app.add_middleware(ImportBodyLimit)


@app.middleware("http")
async def protections(request: Request, call_next):
    public_origin = get_settings().public_origin
    if public_origin and request.url.path not in ("/api/health", "/api/ready"):
        if request.url.scheme != "https":
            return JSONResponse(
                {"detail": "Accedi tramite il dominio HTTPS configurato sul reverse proxy."},
                status_code=403,
            )
        if request.url.netloc != urlsplit(public_origin).netloc:
            return JSONResponse({"detail": "Host non consentito."}, status_code=400)

    if request.url.path == "/api/imports/splitwise/analyze":
        try:
            if int(request.headers.get("content-length", "0")) > 11 * 1024 * 1024:
                return JSONResponse(
                    {"detail": "Il file supera il limite di 10 MB."}, status_code=413
                )
        except ValueError:
            return JSONResponse({"detail": "Richiesta non valida."}, status_code=400)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and (origin != (public_origin or f"{request.url.scheme}://{request.url.netloc}")):
            return JSONResponse(
                {"detail": "Origine della richiesta non consentita."}, status_code=403
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Richiesta cross-site non consentita."}, status_code=403)
    request_id = uuid.uuid4().hex
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    # Route templates deliberately exclude query strings, uploaded filenames and user data.
    route = getattr(request.scope.get("route"), "path", "unmatched")
    logging.getLogger("split.requests").info(
        "request=%s method=%s route=%s status=%s duration_ms=%d",
        request_id,
        request.method,
        route,
        response.status_code,
        (time.monotonic() - started) * 1000,
    )
    if request.url.path.startswith("/api/") or request.url.path in (
        "/sw.js",
        "/manifest.webmanifest",
    ):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(ValidationError)
async def schema_error(request, exc):
    return JSONResponse(
        {"detail": "Dati non validi. Controlla importi, quote e campi richiesti."}, status_code=422
    )


@app.exception_handler(RequestValidationError)
async def request_error(request, exc):
    return JSONResponse(
        {"detail": "Dati non validi. Controlla i campi richiesti e usa centesimi interi."},
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(
        {"detail": "Operazione in conflitto con dati esistenti. Ricarica e riprova."},
        status_code=409,
    )


@app.exception_handler(OperationalError)
def database_error(request, exc):
    import sqlite3

    code = getattr(exc.orig, "sqlite_errorcode", None)
    if code is not None and (code & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return JSONResponse(
            {"detail": "Database occupato. Ricarica prima di riprovare."},
            status_code=503,
            headers={"Retry-After": "3"},
        )
    return JSONResponse(
        {"detail": "Database non disponibile. Contatta l’amministratore."}, status_code=503
    )


@app.get("/api/ready")
def readiness():
    try:
        valid = operations.ready(db.engine)
    except Exception:
        valid = False
    return JSONResponse(
        {"status": "ready" if valid else "unavailable"}, status_code=200 if valid else 503
    )


@app.get("/api/meta")
def metadata(s: DB):
    return {
        "server_version": SERVER_VERSION,
        "api_version": API_VERSION,
        "compatibility": {"min_api_version": 1, "max_api_version": 1},
        "source_available": bool(get_settings().source_archive and Path(get_settings().source_archive).is_file()),
        "capabilities": ["setup", "avatars", "statistics", "pagination", "subscription_credits"],
        "setup_required": setup_required(s),
    }


@app.get("/api/source")
def corresponding_source():
    archive = get_settings().source_archive
    if not archive or not Path(archive).is_file():
        return JSONResponse({"detail": "Sorgente non disponibile su questa istanza."}, status_code=404)
    return FileResponse(archive, media_type="application/gzip", filename="splitcompanion-source.tar.gz")


@app.get("/api/admin/status")
def admin_status(admin: Admin, s: DB):
    from sqlalchemy import func
    from sqlmodel import select
    from app.push_models import PushOutbox

    push_queue = dict(s.exec(select(PushOutbox.status, func.count()).group_by(PushOutbox.status)).all())
    return {
        "server_version": SERVER_VERSION,
        "api_version": API_VERSION,
        "scheduler_enabled": get_settings().scheduler,
        "backups_enabled": get_settings().backups_enabled,
        "push_enabled": get_settings().push_enabled,
        "operations": operations.status(),
        "push_queue": push_queue,
    }


@app.get("/api/health")
def health():
    with Session(db.engine) as s:
        s.execute(text("SELECT 1"))
    return {"status": "ok"}


for router in (
    auth_users.router,
    auth_mfa.router,
    groups.router,
    expenses.router,
    settlements.router,
    subscriptions.router,
    dashboard.router,
):
    app.include_router(router)

app.include_router(imports_router)
app.include_router(categories_router)
app.include_router(push_router)
app.include_router(avatars_router)
app.include_router(setup_router)


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "Endpoint non trovato.")
    root = Path(get_settings().frontend_dir).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(404, "File non trovato.")
    if target.is_file():
        return FileResponse(target)
    if Path(path).suffix:
        raise HTTPException(404, "File non trovato.")
    index = root / "index.html"
    if not index.is_file():
        raise HTTPException(
            503, "Interfaccia non compilata. Esegui npm run build nella directory frontend."
        )
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
