"""Reject unsafe snapshots before touching destination instance data."""

import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from app.backup import backup_full, restore_full
from app.config import Settings
from app.runtime import instance_lock


@pytest.fixture
def snapshot(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    cfg = Settings(
        db=str(source / "database.db"),
        secret_key="snapshot-secret-12345678901234567890",
        _env_file=None,
    )
    with sqlite3.connect(cfg.db) as conn:
        conn.execute("CREATE TABLE alembic_version(version_num TEXT)")
        conn.execute("INSERT INTO alembic_version VALUES ('test')")
        conn.execute("CREATE TABLE sentinel(value TEXT)")
        conn.execute("INSERT INTO sentinel VALUES ('saved')")
    (source / "push-vapid.pem").write_bytes(b"saved-vapid-key")
    archive = backup_full(cfg, tmp_path / "archives")
    target = Settings(db=str(tmp_path / "target" / "database.db"), secret_key="", _env_file=None)
    return archive, target


def rewrite_archive(source, destination, edit):
    with tarfile.open(source, "r:gz") as original, tarfile.open(destination, "w:gz") as output:
        for member in original:
            payload = original.extractfile(member).read()
            payload = edit(member.name, payload)
            member.size = len(payload)
            output.addfile(member, io.BytesIO(payload))
    return destination


@pytest.mark.parametrize("kind", ["traversal", "symlink", "duplicate", "directory"])
def test_restore_rejects_unsafe_members_without_touching_existing_data(snapshot, tmp_path, kind):
    original, cfg = snapshot
    archive = rewrite_archive(original, tmp_path / "unsafe.tar.gz", lambda _, data: data)
    # tarfile cannot append gzip; copy valid members into another archive then append attack.
    malicious = tmp_path / "attack.tar.gz"
    with tarfile.open(archive, "r:gz") as src, tarfile.open(malicious, "w:gz") as dst:
        for member in src:
            dst.addfile(member, src.extractfile(member))
        member = tarfile.TarInfo("../escaped" if kind == "traversal" else "secret.key")
        if kind == "symlink":
            member.type = tarfile.SYMTYPE
            member.linkname = "../../escaped"
        elif kind == "directory":
            member.type = tarfile.DIRTYPE
        dst.addfile(member, io.BytesIO(b""))
    target = Path(cfg.db).parent
    target.mkdir()
    (target / "secret.key").write_bytes(b"existing-secret")
    with pytest.raises(ValueError):
        restore_full(cfg, malicious, {"test"})
    assert (target / "secret.key").read_bytes() == b"existing-secret"
    assert not Path(cfg.db).exists()
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("kind", ["checksum", "schema", "missing"])
def test_restore_rejects_invalid_snapshot_before_destination_changes(snapshot, tmp_path, kind):
    original, cfg = snapshot

    def edit(name, payload):
        if name == "manifest.json":
            data = json.loads(payload)
            if kind == "checksum":
                data["files"]["database.db"] = "invalid"
            elif kind == "schema":
                data["schema"] = "future"
            else:
                del data["files"]["secret.key"]
            return json.dumps(data).encode()
        return payload

    broken = rewrite_archive(original, tmp_path / "broken.tar.gz", edit)
    with pytest.raises(ValueError):
        restore_full(cfg, broken, {"test"})
    assert not Path(cfg.db).exists()
    assert not (Path(cfg.db).parent / "secret.key").exists()


def test_restore_preserves_existing_database_and_credentials(snapshot):
    archive, cfg = snapshot
    target = Path(cfg.db).parent
    target.mkdir()
    existing = {
        "database.db": b"existing-db",
        "secret.key": b"existing-secret",
        "push-vapid.pem": b"existing-vapid",
    }
    for name, value in existing.items():
        (target / name).write_bytes(value)
    with pytest.raises(ValueError, match="volume nuovo"):
        restore_full(cfg, archive, {"test"})
    for name, value in existing.items():
        assert (target / name).read_bytes() == value


def test_restore_refuses_active_instance(snapshot):
    archive, cfg = snapshot
    with instance_lock(Path(cfg.db).parent / ".instance.lock"):
        with pytest.raises(RuntimeError, match="istanza"):
            restore_full(cfg, archive, {"test"})
    assert not Path(cfg.db).exists()


def test_instance_lock_released_after_failure(tmp_path):
    path = tmp_path / "lock"
    with pytest.raises(ValueError):
        with instance_lock(path):
            raise ValueError("startup failed")
    with instance_lock(path):
        pass


def test_restore_does_not_overwrite_existing_external_vapid(snapshot, tmp_path):
    archive, cfg = snapshot
    existing = tmp_path / "shared-vapid.pem"
    existing.write_bytes(b"another-instance-key")
    cfg.push_vapid_path = str(existing)
    with pytest.raises(ValueError):
        restore_full(cfg, archive, {"test"})
    assert existing.read_bytes() == b"another-instance-key"
    assert not Path(cfg.db).exists()


@pytest.mark.parametrize("name", ["secret.key", "push-vapid.pem", "restored-config.json"])
def test_restore_preserves_existing_artifacts_with_no_database(snapshot, name):
    archive, cfg = snapshot
    directory = Path(cfg.db).parent
    directory.mkdir()
    destination = directory / name
    destination.write_bytes(b"existing-data")
    with pytest.raises(ValueError, match="volume nuovo"):
        restore_full(cfg, archive, {"test"})
    assert destination.read_bytes() == b"existing-data"
    assert not Path(cfg.db).exists()


@pytest.mark.parametrize(
    "manifest",
    [
        [],
        None,
        {"format": 1, "files": []},
        {"format": True, "files": {}},
        {"format": 1, "files": {}, "config": []},
    ],
)
def test_restore_rejects_malformed_manifest_types(snapshot, tmp_path, manifest):
    archive, cfg = snapshot
    broken = rewrite_archive(
        archive,
        tmp_path / "malformed.tar.gz",
        lambda name, payload: json.dumps(manifest).encode() if name == "manifest.json" else payload,
    )
    with pytest.raises(ValueError, match="Manifest"):
        restore_full(cfg, broken, {"test"})
    assert not Path(cfg.db).exists()


def test_restore_success_preserves_snapshot_and_permissions(snapshot):
    archive, cfg = snapshot
    restored = restore_full(cfg, archive, {"test"})
    assert restored["schema"] == "test"
    with sqlite3.connect(cfg.db) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("saved",)
    assert (Path(cfg.db).parent / "push-vapid.pem").read_bytes() == b"saved-vapid-key"
    assert (Path(cfg.db).parent / "secret.key").stat().st_mode & 0o777 == 0o600


def test_failed_startup_migration_retains_database_and_rollback_snapshot(tmp_path, monkeypatch):
    from app import container

    path = tmp_path / "instance.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE alembic_version(version_num TEXT)")
        conn.execute("INSERT INTO alembic_version VALUES ('old')")
        conn.execute("CREATE TABLE sentinel(value TEXT)")
        conn.execute("INSERT INTO sentinel VALUES ('existing')")
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("test")
    cfg = Settings(
        db=str(path),
        secret_key=__import__("secrets").token_urlsafe(32),
        frontend_dir=str(web),
        allow_http=True,
        _env_file=None,
    )
    monkeypatch.setattr(container, "schema_versions", lambda: ("new", {"old", "new"}))

    def fail_migration(*args):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(container.command, "upgrade", fail_migration)
    with pytest.raises(RuntimeError, match="migration failed"):
        container.prepare(cfg)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("existing",)
    archives = list((tmp_path / "backups").glob("split-migration-*.tar.gz"))
    assert len(archives) == 1
    restored_cfg = Settings(
        db=str(tmp_path / "rollback" / "database.db"), secret_key="", _env_file=None
    )
    restore_full(restored_cfg, archives[0], {"old"})
    with sqlite3.connect(restored_cfg.db) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("existing",)
