from pathlib import Path
from fastapi import Request
from sqlalchemy import event, text
from sqlmodel import Session, create_engine
from .config import get_settings


def make_engine(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        "sqlite:///" + path, connect_args={"check_same_thread": False, "timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def configure(dbapi, _):
        cursor = dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


engine = make_engine(get_settings().db)


def get_session(request: Request):
    with Session(engine) as session:
        # Preview records acknowledgment; serialize it with mapping/commit too.
        records_preview = request.url.path.startswith(
            "/api/imports/splitwise/"
        ) and request.url.path.endswith("/preview")
        if request.method not in ("GET", "HEAD", "OPTIONS") or records_preview:
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            # Python SQLite legacy mode does not BEGIN on SELECT by itself.
            # A balance spans several queries and must see one WAL snapshot.
            session.execute(text("BEGIN"))
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
