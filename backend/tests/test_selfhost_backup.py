import sqlite3
import tarfile
from pathlib import Path
import pytest
from app.config import Settings
from app.backup import backup_full, restore_full
from app.runtime import instance_lock


def instance(tmp_path):
    path = tmp_path / "source" / "db.sqlite"
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute("CREATE TABLE alembic_version(version_num TEXT)")
        db.execute("INSERT INTO alembic_version VALUES ('test')")
        db.execute("CREATE TABLE example(value TEXT)")
        db.execute("INSERT INTO example VALUES ('preserved')")
    cfg = Settings(db=str(path), secret_key="test-durable-backup-secret-1234567890", _env_file=None)
    (path.parent / "push-vapid.pem").write_text("private-key-fixture")
    return cfg


def test_complete_backup_restore_and_refuse_overwrite(tmp_path):
    cfg = instance(tmp_path)
    archive = backup_full(cfg, tmp_path / "backups")
    with tarfile.open(archive) as f:
        assert set(f.getnames()) == {"manifest.json", "database.db", "secret.key", "push-vapid.pem"}
    target = Settings(db=str(tmp_path / "restored" / "db.sqlite"), secret_key="", _env_file=None)
    restore_full(target, archive, {"test"})
    with sqlite3.connect(target.db) as db:
        assert db.execute("SELECT value FROM example").fetchone()[0] == "preserved"
    assert (Path(target.db).parent / "secret.key").read_text() == cfg.secret_key
    assert (Path(target.db).parent / "push-vapid.pem").read_text() == "private-key-fixture"
    with pytest.raises(ValueError, match="volume nuovo"):
        restore_full(target, archive, {"test"})


def test_restore_refuses_running_server_and_unknown_schema(tmp_path):
    cfg = instance(tmp_path)
    archive = backup_full(cfg, tmp_path / "backups")
    target = Settings(db=str(tmp_path / "restored" / "db.sqlite"), secret_key="", _env_file=None)
    with instance_lock(Path(target.db).parent / ".instance.lock"):
        with pytest.raises(RuntimeError):
            restore_full(target, archive, {"test"})
    with pytest.raises(ValueError, match="Schema"):
        restore_full(target, archive, {"future"})
    assert not Path(target.db).exists()


def test_retention_only_removes_daily(tmp_path):
    cfg = instance(tmp_path)
    cfg.backup_retention = 1
    folder = tmp_path / "backups"
    manual = backup_full(cfg, folder)
    first = backup_full(cfg, folder, "daily")
    latest = backup_full(cfg, folder, "daily")
    assert manual.exists() and latest.exists() and not first.exists()
