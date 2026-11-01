"""Fail-closed single-process entrypoint for the self-hosted distribution."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic import command
from app.config import get_settings
from app.runtime import instance_lock, resolve_secret, writable_directory


def migration_config():
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return cfg


def schema_versions():
    script = ScriptDirectory.from_config(migration_config())
    return script.get_current_head(), {x.revision for x in script.walk_revisions()}


def prepare(cfg):
    from app.backup import revision, backup_full

    if not cfg.public_origin and not cfg.allow_http:
        raise RuntimeError(
            "Configura PUBLIC_ORIGIN HTTPS oppure abilita esplicitamente ALLOW_HTTP per la LAN."
        )
    if not (Path(cfg.frontend_dir) / "index.html").is_file():
        raise RuntimeError("Asset web mancanti nell’immagine.")
    writable_directory(Path(cfg.db).parent)
    if cfg.backups_enabled:
        writable_directory(cfg.backup_dir or Path(cfg.db).parent / "backups")
    resolve_secret(cfg)
    head, versions = schema_versions()
    path = Path(cfg.db)
    if path.exists() and path.stat().st_size:
        current = revision(path)
        if current not in versions:
            raise RuntimeError("Schema database sconosciuto o più recente del server.")
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Integrità database non valida.")
        if current != head:
            backup_full(cfg, kind="migration")
    command.upgrade(migration_config(), "head")
    path.chmod(0o600)


def main():
    os.umask(0o077)
    cfg = get_settings()
    with instance_lock(Path(cfg.db).parent / ".instance.lock"):
        prepare(cfg)
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host=cfg.host,
            port=cfg.port,
            workers=1,
            proxy_headers=True,
            forwarded_allow_ips=cfg.trusted_proxy_ips,
            access_log=False,
        )


if __name__ == "__main__":
    main()
