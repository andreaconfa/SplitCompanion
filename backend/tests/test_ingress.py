"""Ingress must remain a separately authenticated, Supervisor-only surface."""

from fastapi.testclient import TestClient
import pytest

from app.main import app

PREFIX = "/api/hassio_ingress/test_token-123"
HEADERS = {
    "X-Ingress-Path": PREFIX,
    "X-Forwarded-Host": "ha.example:8123",
    "X-Forwarded-Proto": "http",
}


def ingress_client():
    from app.ingress import IngressApp

    return TestClient(
        IngressApp(app),
        client=("172.30.32.2", 1234),
        base_url="http://ha.example:8123",
        headers=HEADERS,
    )


def test_ingress_rejects_other_peers_even_with_spoofed_forwarding(client):
    from app.ingress import IngressApp

    c = TestClient(
        IngressApp(app),
        client=("172.30.32.9", 1234),
        headers={**HEADERS, "X-Forwarded-For": "172.30.32.2"},
    )
    assert c.get("/api/meta").status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "//evil.test",
        "/api/hassio_ingress/a/../b",
        "/api/hassio_ingress/a%22",
        "/api/hassio_ingress/a?x",
    ],
)
def test_ingress_rejects_invalid_or_missing_prefix(client, path):
    c = ingress_client()
    assert c.get("/api/meta", headers={"X-Ingress-Path": path}).status_code == 400


def test_ingress_keeps_accounts_csrf_and_scopes_session_cookies(client):
    c = ingress_client()
    assert c.get("/api/auth/me", headers={"X-Remote-User-Id": "alex"}).status_code == 401
    login = c.post(
        "/api/auth/login",
        json={"username": "alex", "password": "password12345"},
        headers={"Origin": "http://ha.example:8123"},
    )
    assert login.status_code == 200
    cookie = login.headers["set-cookie"]
    assert "split_ingress_session=" in cookie and f"Path={PREFIX}/" in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    token = login.cookies["split_ingress_session"]
    # Supervisor strips the prefix before forwarding; the browser still scopes the cookie.
    c.headers["Cookie"] = f"split_ingress_session={token}"
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 403
    c.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert c.post("/api/auth/logout", headers={"Origin": "https://evil.test"}).status_code == 403
    logout = c.post("/api/auth/logout", headers={"Origin": "http://ha.example:8123"})
    assert logout.status_code == 200 and f"Path={PREFIX}/" in logout.headers["set-cookie"]
    assert c.get("/api/auth/me").status_code == 401


def test_ingress_does_not_accept_direct_session_cookie(client):
    c = ingress_client()
    c.headers["Cookie"] = f"split_session={client.cookies['split_session']}"
    assert c.get("/api/auth/me").status_code == 401


def test_direct_headers_cannot_enable_ingress_or_relax_security(client, tmp_path, monkeypatch):
    from app.config import get_settings

    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text('<html><head><base href="/" /></head><body></body></html>')
    monkeypatch.setattr(get_settings(), "frontend_dir", str(root))
    response = client.get("/", headers=HEADERS)
    assert "split-ingress" not in response.text
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_ingress_html_routes_and_external_https_config_are_independent(
    client, tmp_path, monkeypatch
):
    from app.config import get_settings

    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text('<html><head><base href="/" /></head><body></body></html>')
    monkeypatch.setattr(get_settings(), "frontend_dir", str(root))
    monkeypatch.setattr(get_settings(), "public_origin", "https://split.example")
    monkeypatch.setattr(get_settings(), "secure_cookie", True)
    c = ingress_client()
    for path in ("/", "/groups/1", "/index.html"):
        response = c.get(path)
        assert response.status_code == 200
        assert f'<base href="{PREFIX}/"' in response.text
        assert '<meta name="split-ingress" content="true">' in response.text
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert "frame-ancestors 'self'" in response.headers["Content-Security-Policy"]
        assert response.headers["Cache-Control"] == "no-store"
    login = c.post(
        "/api/auth/login",
        json={"username": "alex", "password": "password12345"},
        headers={"Origin": "http://ha.example:8123"},
    )
    assert login.status_code == 200 and "Secure" not in login.headers["set-cookie"]
    assert client.get("/", headers=HEADERS).status_code == 403


def test_ingress_https_cookie_and_bad_forwarded_headers(client):
    c = ingress_client()
    login = c.post(
        "/api/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        json={"username": "alex", "password": "password12345"},
    )
    assert login.status_code == 200 and "; Secure" in login.headers["set-cookie"]
    for headers in (
        {"X-Forwarded-Host": "evil.test/path"},
        {"X-Forwarded-Host": "a,b"},
        {"X-Forwarded-Proto": "https,http"},
    ):
        assert c.get("/api/meta", headers=headers).status_code == 400
    assert (
        c.get(
            "/api/meta", headers=[("X-Ingress-Path", PREFIX), ("X-Ingress-Path", PREFIX)]
        ).status_code
        == 400
    )


def test_listener_dispatch_checks_socket_before_forwarded_client(client):
    import asyncio
    from app.ingress import HomeAssistantApp

    seen = []

    async def endpoint(scope, receive, send):
        seen.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def invoke(port):
        messages = []

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "server": ("0.0.0.0", port),
            "client": ("172.30.32.9", 123),
            "scheme": "http",
            "headers": [(b"x-forwarded-for", b"172.30.32.2")],
        }
        await HomeAssistantApp(endpoint, "*")(scope, receive, send)
        return messages

    assert asyncio.run(invoke(8099))[0]["status"] == 403
    assert not seen
    assert asyncio.run(invoke(8000))[0]["status"] == 200
    assert not seen[-1].get("split_ingress")


def test_ingress_mfa_enrollment_finishes_with_scoped_authenticated_cookie(client, monkeypatch):
    import pyotp
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "mfa_required", True)
    c = ingress_client()
    login = c.post("/api/auth/login", json={"username": "alex", "password": "password12345"})
    challenge = login.json()["challenge_token"]
    assert c.get("/api/auth/me").status_code == 401
    setup = c.post("/api/auth/mfa/setup", json={"challenge_token": challenge})
    confirmation = c.post(
        "/api/auth/mfa/confirm",
        json={"challenge_token": challenge, "code": pyotp.TOTP(setup.json()["secret"]).now()},
    )
    assert confirmation.status_code == 200
    assert f"Path={PREFIX}/" in confirmation.headers["set-cookie"]
    c.headers["Cookie"] = f"split_ingress_session={confirmation.cookies['split_ingress_session']}"
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 403
    c.headers["X-CSRF-Token"] = confirmation.json()["session"]["csrf_token"]
    assert c.post("/api/auth/logout").status_code == 200
