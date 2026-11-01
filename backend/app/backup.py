"""Complete portable snapshots. Restore is offline and accepts only known regular files."""

from contextlib import closing
import hashlib
import json
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from app.runtime import instance_lock, resolve_secret
from app.version import SERVER_VERSION

CONFIG_KEYS = (
    "timezone",
    "mfa_required",
    "session_hours",
    "public_origin",
    "secure_cookie",
    "push_vapid_subject",
)


def file_sha256(path):
    with Path(path).open("rb") as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def revision(path):
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='alembic_version'").fetchone()
        return (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0] if exists else None
        )


def backup_full(cfg, output_dir=None, kind="manual"):
    if kind not in ("manual", "daily", "migration"):
        raise ValueError("Tipo di backup non valido.")
    resolve_secret(cfg)
    source = Path(cfg.db)
    if not source.is_file():
        raise ValueError("Database non trovato.")
    directory = Path(output_dir or cfg.backup_dir or source.parent / "backups")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"split-{kind}-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory(dir=directory) as scratch:
        work = Path(scratch)
        with (
            closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as src,
            closing(sqlite3.connect(work / "database.db")) as dst,
        ):
            src.backup(dst)
            dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dst.execute("PRAGMA journal_mode=DELETE")
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Integrità database non valida.")
        (work / "secret.key").write_text(cfg.secret_key)
        vapid = Path(cfg.push_vapid_path or source.parent / "push-vapid.pem")
        if vapid.exists():
            (work / "push-vapid.pem").write_bytes(vapid.read_bytes())
        files = {p.name: file_sha256(p) for p in work.iterdir()}
        manifest = dict(
            format=1,
            server_version=SERVER_VERSION,
            schema=revision(work / "database.db"),
            created_at=stamp,
            kind=kind,
            files=files,
            config={key: getattr(cfg, key) for key in CONFIG_KEYS},
        )
        (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
        temporary = work / "archive.tmp"
        with tarfile.open(temporary, "w:gz") as archive:
            for name in [*files, "manifest.json"]:
                archive.add(work / name, arcname=name, recursive=False)
        temporary.chmod(0o600)
        with temporary.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(temporary, target)
    if kind == "daily":
        for old in sorted(directory.glob("split-daily-*.tar.gz"), reverse=True)[
            cfg.backup_retention :
        ]:
            old.unlink()
    return target


def restore_full(cfg, archive_path, known_revisions):
    directory = Path(cfg.db).parent
    with (
        instance_lock(directory / ".instance.lock"),
        tempfile.TemporaryDirectory(dir=directory) as scratch,
    ):
        work = Path(scratch)
        allowed = {"database.db", "secret.key", "push-vapid.pem", "manifest.json"}
        seen = set()
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive:
                if (
                    member.name not in allowed
                    or not member.isfile()
                    or member.name in seen
                    or member.size > (4 * 1024**3 if member.name == "database.db" else 64 * 1024)
                ):
                    raise ValueError("Archivio di backup non valido.")
                seen.add(member.name)
                with archive.extractfile(member) as src, (work / member.name).open("wb") as dst:
                    import shutil

                    shutil.copyfileobj(src, dst)
                (work / member.name).chmod(0o600)
        if not {"database.db", "secret.key", "manifest.json"} <= seen:
            raise ValueError("Backup incompleto.")
        manifest = json.loads((work / "manifest.json").read_text())
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("format")) is not int
            or manifest["format"] != 1
            or not isinstance(manifest.get("files"), dict)
            or not isinstance(manifest.get("config", {}), dict)
            or set(manifest["files"]) != seen - {"manifest.json"}
        ):
            raise ValueError("Manifest del backup non valido.")
        for name, digest in manifest["files"].items():
            if file_sha256(work / name) != digest:
                raise ValueError("Checksum del backup non valido.")
        secret = (work / "secret.key").read_text().strip()
        if len(secret) < 32 or secret.startswith("replace-with-"):
            raise ValueError("Segreto nel backup non valido.")
        if cfg.secret_key and cfg.secret_key != secret:
            raise ValueError("Il segreto configurato non corrisponde al backup.")
        if cfg.secret_key_file and Path(cfg.secret_key_file).read_text().strip() != secret:
            raise ValueError("Il file del segreto configurato non corrisponde al backup.")
        if revision(work / "database.db") not in known_revisions or manifest.get(
            "schema"
        ) != revision(work / "database.db"):
            raise ValueError("Schema del backup non compatibile.")
        with closing(sqlite3.connect(work / "database.db")) as db:
            if (
                db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or db.execute("PRAGMA foreign_key_check").fetchone()
            ):
                raise ValueError("Database nel backup non integro.")
        # Restore to a new volume only. An interrupted copy never replaces an existing installation.
        # A fresh-volume restore is also the rollback procedure: keep the old volume intact.
        if Path(cfg.db).exists() and Path(cfg.db).stat().st_size:
            raise ValueError(
                "Ripristina su un volume nuovo e vuoto; il database esistente è conservato."
            )
        vapid_target = Path(cfg.push_vapid_path or directory / "push-vapid.pem")
        # "New volume" includes credentials and configuration, not just the database.
        # In particular a custom VAPID path may belong to another live installation.
        for destination in (
            vapid_target,
            directory / "secret.key",
            directory / "restored-config.json",
        ):
            if destination.exists() or destination.is_symlink():
                raise ValueError(
                    "Ripristina su un volume nuovo: credenziali o configurazione già presenti."
                )
        # A snapshot can contain sessions/challenges revoked since it was taken.
        # Require fresh authentication while preserving the original MFA credentials.
        # Older supported schemas may not yet contain the MFA challenge table.
        with closing(sqlite3.connect(work / "database.db")) as db:
            with db:
                for table in ("authsession", "mfachallenge"):
                    if db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone():
                        db.execute(f"DELETE FROM {table}")
        if "push-vapid.pem" in seen:
            vapid_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(work / "push-vapid.pem", vapid_target)
        os.replace(work / "secret.key", directory / "secret.key")
        (directory / "restored-config.json").write_text(
            json.dumps(manifest.get("config", {}), indent=2)
        )
        (directory / "restored-config.json").chmod(0o600)
        os.replace(work / "database.db", cfg.db)
    return manifest
