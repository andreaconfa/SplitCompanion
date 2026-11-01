"""Process exclusion and durable instance identity, independent of the database engine."""

import fcntl
import os
import secrets
from contextlib import contextmanager
from pathlib import Path


def resolve_secret(cfg):
    if cfg.secret_key:
        return
    path = Path(cfg.secret_key_file or str(Path(cfg.db).parent / "secret.key"))
    if not path.exists():
        if cfg.secret_key_file or (Path(cfg.db).exists() and Path(cfg.db).stat().st_size):
            raise RuntimeError("Manca il segreto originale dell’istanza. Ripristinalo dal backup.")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Startup holds instance lock; exclusive creation also protects independent callers.
        with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as f:
            f.write(secrets.token_urlsafe(48))
            f.flush()
            os.fsync(f.fileno())
    value = path.read_text().strip()
    if len(value) < 32 or value.startswith("replace-with-"):
        raise RuntimeError("Il file del segreto non è valido.")
    cfg.secret_key = value


@contextmanager
def instance_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Un’altra istanza usa questo volume. Arrestala prima di procedere."
            ) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def writable_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    import tempfile

    with tempfile.TemporaryFile(dir=path) as probe:
        probe.write(b"1")
        probe.flush()
        os.fsync(probe.fileno())
