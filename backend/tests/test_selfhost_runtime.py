from pathlib import Path
import pytest
from app.config import Settings


def test_settings_validate_timezone_and_placeholder():
    with pytest.raises(ValueError):
        Settings(timezone="Not/AZone", _env_file=None)
    with pytest.raises(ValueError):
        Settings(secret_key="replace-with-at-least-32-random-characters", _env_file=None)


def test_durable_secret_and_missing_existing_secret(tmp_path):
    from app.runtime import resolve_secret

    cfg = Settings(db=str(tmp_path / "instance.db"), secret_key="", _env_file=None)
    resolve_secret(cfg)
    assert len(cfg.secret_key) >= 32
    assert (tmp_path / "secret.key").stat().st_mode & 0o777 == 0o600
    second = Settings(db=cfg.db, secret_key="", _env_file=None)
    resolve_secret(second)
    assert second.secret_key == cfg.secret_key
    (tmp_path / "secret.key").unlink()
    Path(cfg.db).write_bytes(b"existing database")
    with pytest.raises(RuntimeError, match="segreto"):
        resolve_secret(Settings(db=cfg.db, secret_key="", _env_file=None))


def test_exclusive_lock(tmp_path):
    from app.runtime import instance_lock

    with instance_lock(tmp_path / "lock"):
        with pytest.raises(RuntimeError):
            with instance_lock(tmp_path / "lock"):
                pass


def test_meta_ready_admin_and_bounded_json(client):
    assert client.get("/api/meta").json()["api_version"] == 1
    assert client.get("/api/meta").json()["setup_required"] is False
    assert client.get("/api/health").json() == {"status": "ok"}
    # Fixture has create_all tables but no migration marker; never report ready.
    assert client.get("/api/ready").status_code == 503
    assert client.get("/api/admin/status").status_code == 200
    result = client.post(
        "/api/auth/login",
        content=b"{" + b"x" * (1024 * 1024),
        headers={"Content-Type": "application/json"},
    )
    assert result.status_code == 413
    client.post("/api/auth/logout")
    assert client.get("/api/admin/status").status_code == 401


def test_prepare_existing_missing_secret_and_unknown_schema(tmp_path, monkeypatch):
    from app.container import prepare
    import sqlite3

    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("test")
    path = tmp_path / "instance.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE alembic_version(version_num TEXT)")
        conn.execute("INSERT INTO alembic_version VALUES ('future')")
    cfg = Settings(
        db=str(path), frontend_dir=str(web), allow_http=True, secret_key="", _env_file=None
    )
    with pytest.raises(RuntimeError, match="segreto"):
        prepare(cfg)
    cfg.secret_key = "test-only-stable-secret-for-schema-123456"
    with pytest.raises(RuntimeError, match="Schema"):
        prepare(cfg)


def test_offline_restore_requires_matching_supplied_secret(tmp_path):
    from app.backup import restore_full, backup_full
    import sqlite3

    source = tmp_path / "source.db"
    with sqlite3.connect(source) as c:
        c.execute("CREATE TABLE alembic_version(version_num TEXT)")
        c.execute("INSERT INTO alembic_version VALUES ('test')")
    cfg = Settings(
        db=str(source), secret_key="source-secret-for-test-123456789012345", _env_file=None
    )
    archive = backup_full(cfg, tmp_path / "backups")
    other = Settings(
        db=str(tmp_path / "new" / "target.db"),
        secret_key="different-secret-for-test-123456789012",
        _env_file=None,
    )
    with pytest.raises(ValueError, match="segreto"):
        restore_full(other, archive, {"test"})
    assert not Path(other.db).exists()


def test_directory_probe_detects_flush_failure(tmp_path, monkeypatch):
    import errno
    from app.runtime import writable_directory

    def full_disk(fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("app.runtime.os.fsync", full_disk)
    with pytest.raises(OSError) as failure:
        writable_directory(tmp_path)
    assert failure.value.errno == errno.ENOSPC
    assert list(tmp_path.iterdir()) == []
