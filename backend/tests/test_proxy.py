import pytest
from app.config import Settings, get_settings


def test_proxy_settings_reject_wildcard_and_non_https_origin():
    with pytest.raises(ValueError):
        Settings(trusted_proxy_ips="*", _env_file=None)
    with pytest.raises(ValueError):
        Settings(public_origin="http://split.example.org", _env_file=None)
    with pytest.raises(ValueError):
        Settings(public_origin="https://split.example.org/path", _env_file=None)
    cfg = Settings(
        public_origin="https://split.example.org", trusted_proxy_ips="192.0.2.10", _env_file=None
    )
    assert cfg.secure_cookie is True


def test_external_proxy_requires_https_and_public_host(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_origin", "https://split.example.org")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/me").status_code == 403
    assert client.get("/api/auth/me", headers={"X-Forwarded-Proto": "https"}).status_code == 403
    assert client.get("https://evil.example.org/api/auth/me").status_code == 400
    assert client.get("https://split.example.org/api/auth/me").status_code == 401
    result = client.post(
        "https://split.example.org/api/auth/login",
        json={"username": "alex", "password": "password12345"},
        headers={"Origin": "http://split.example.org"},
    )
    assert result.status_code == 403


def test_managed_https_endpoints_removed(client):
    assert client.get("/api/admin/https").status_code == 404
    assert client.post("/api/admin/https/issue", json={"terms_accepted": True}).status_code in (
        404,
        405,
    )


def test_https_login_cookie_uses_request_scheme(client):
    result = client.post(
        "https://testserver/api/auth/login",
        json={"username": "alex", "password": "password12345"},
    )
    assert "; Secure" in result.headers["set-cookie"]
    client.cookies.clear()
    result = client.post(
        "/api/auth/login",
        json={"username": "alex", "password": "password12345"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert "; Secure" not in result.headers["set-cookie"]
