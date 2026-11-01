"""Real HTTP process, migrations and trusted reverse proxy headers."""

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_clean_migrations_and_http_backend_with_trusted_proxy(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "SPLIT_COMPANION_DB": str(tmp_path / "fresh.db"),
        "SPLIT_COMPANION_SECRET_KEY": secrets.token_urlsafe(48),
        "SPLIT_COMPANION_HOST": "127.0.0.1",
        "SPLIT_COMPANION_PORT": str(port),
        "SPLIT_COMPANION_SCHEDULER": "false",
        "SPLIT_COMPANION_PUBLIC_ORIGIN": "https://split.example.org",
        "SPLIT_COMPANION_TRUSTED_PROXY_IPS": "127.0.0.1",
        "SPLIT_COMPANION_SECURE_COOKIE": "true",
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ROOT / "backend/alembic.ini"),
            "upgrade",
            "head",
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "backend/alembic.ini"), "check"],
        env=env,
        check=True,
        capture_output=True,
    )
    log = tmp_path / "server.log"
    with log.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.run"],
            cwd=ROOT / "backend",
            env=env,
            stdout=output,
            stderr=output,
        )
        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                for _ in range(60):
                    if process.poll() is not None:
                        pytest.fail(log.read_text())
                    try:
                        response = client.get(f"http://127.0.0.1:{port}/api/health")
                        break
                    except httpx.ConnectError:
                        time.sleep(0.1)
                else:
                    pytest.fail("Server startup timed out: " + log.read_text())
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                assert response.headers["cache-control"] == "no-store"
                assert client.get(f"http://127.0.0.1:{port}/api/auth/me").status_code == 403
                headers = {
                    "Host": "split.example.org",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "203.0.113.12",
                }
                assert (
                    client.get(f"http://127.0.0.1:{port}/api/auth/me", headers=headers).status_code
                    == 401
                )
                # A TCP peer outside the trusted list cannot forge HTTPS.
                transport = httpx.HTTPTransport(local_address="127.0.0.2")
                with httpx.Client(transport=transport, timeout=1) as outsider:
                    assert (
                        outsider.get(
                            f"http://127.0.0.1:{port}/api/auth/me", headers=headers
                        ).status_code
                        == 403
                    )
        finally:
            process.terminate()
            process.wait(timeout=10)
