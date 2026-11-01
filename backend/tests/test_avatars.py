import io

import pytest
from PIL import Image, PngImagePlugin
from sqlmodel import Session

from app import db
from app.models import UserAvatar
from test_category_icons import login_as


def photo(color="red", size=(512, 300), fmt="PNG"):
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "location and private camera information")
    Image.new("RGB", size, color).save(output, fmt, pnginfo=metadata)
    return output.getvalue()


def upload(client, user=1, data=None):
    return client.post(
        f"/api/users/{user}/avatar",
        files={"file": ("photo.png", photo() if data is None else data, "image/png")},
    )


def test_photo_normalization_replacement_deletion_and_session_persistence(client):
    original_session = client.cookies.get("split_session")
    first = upload(client)
    assert first.status_code == 200, first.text
    version = first.json()["avatar_version"]
    assert version
    image = client.get(f"/api/users/1/avatar?v={version}")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(image.content)) as normalized:
        assert normalized.size == (256, 150)
        assert not normalized.info
        assert normalized.mode == "RGBA"
    with Session(db.engine) as s:
        assert s.get(UserAvatar, 1).png == image.content
    assert client.get("/api/auth/me").json()["user"]["avatar_version"] == version
    assert client.cookies.get("split_session") == original_session
    changed = upload(client, data=photo("blue", fmt="JPEG"))
    assert changed.status_code == 200
    assert changed.json()["avatar_version"] != version
    assert client.get("/api/users/1/avatar").content != image.content
    assert client.cookies.get("split_session") == original_session
    assert client.delete("/api/users/1/avatar").json()["avatar_version"] is None
    assert client.get("/api/users/1/avatar").status_code == 404
    assert client.get("/api/auth/me").status_code == 200
    assert client.delete("/api/users/1/avatar").status_code == 200
    assert all(u["avatar_version"] is None for u in client.get("/api/users").json())


def test_owner_admin_and_authenticated_reads(client):
    assert upload(client, user=2).status_code == 200
    login_as(client, "laura")
    assert client.get("/api/users/2/avatar").status_code == 200
    assert upload(client, user=2).status_code == 200
    assert upload(client, user=1).status_code == 403
    assert client.delete("/api/users/1/avatar").status_code == 403
    login_as(client, "outsider")
    assert client.get("/api/users/2/avatar").status_code == 200
    assert client.delete("/api/users/2/avatar").status_code == 403
    login_as(client, "alex")
    assert client.delete("/api/users/2/avatar").status_code == 200
    assert upload(client, user=999).status_code == 404
    client.post("/api/auth/logout")
    assert client.get("/api/users/1/avatar").status_code == 401
    assert upload(client).status_code == 401
    assert client.delete("/api/users/1/avatar").status_code == 401


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not an image",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        photo(size=(2049, 1)),
        photo()[:30],
        photo(fmt="GIF"),
    ],
)
def test_invalid_photo_does_not_replace_existing(client, content):
    version = upload(client).json()["avatar_version"]
    before = client.get("/api/users/1/avatar").content
    result = upload(client, data=content)
    assert result.status_code == 422, result.text
    assert client.get("/api/users/1/avatar").content == before
    assert client.get("/api/auth/me").json()["user"]["avatar_version"] == version


def test_avatar_size_limit_and_csrf(client):
    assert upload(client, data=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert upload(client, data=b"x" * (3 * 1024 * 1024)).status_code == 413
    csrf = client.headers.pop("X-CSRF-Token")
    assert upload(client).status_code == 403
    assert client.delete("/api/users/1/avatar").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.get("/api/auth/me").json()["user"]["avatar_version"] is None


def test_decompression_warning_is_rejected(client, monkeypatch):
    content = photo(size=(20, 20))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 250)
    assert upload(client, data=content).status_code == 422


def test_jpeg_orientation_applied_and_exif_removed(client):
    image = Image.new("RGB", (100, 200))
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private description"
    raw = io.BytesIO()
    image.save(raw, "JPEG", exif=exif)
    assert upload(client, data=raw.getvalue()).status_code == 200
    with Image.open(io.BytesIO(client.get("/api/users/1/avatar").content)) as normalized:
        assert normalized.size == (200, 100)
        assert not normalized.getexif()
        assert not normalized.info


@pytest.mark.parametrize("identifier", ["1", "+1", "-1", "invalid"])
def test_avatar_body_limit_covers_every_route_parameter(client, identifier):
    # A small valid file and oversized declared body distinguish the middleware
    # guard from the later per-file check inside the authenticated endpoint.
    result = client.post(
        f"/api/users/{identifier}/avatar",
        headers={"Content-Length": str(3 * 1024 * 1024)},
        files={"file": ("photo.png", photo(), "image/png")},
    )
    assert result.status_code == 413


@pytest.mark.parametrize("path", ["/api/users/1/avatar", "/api/users/+1/avatar", "/api/users/1/avatar/"])
def test_avatar_chunked_limit_rejects_before_multipart_parser(path):
    import asyncio

    from app.upload_limit import ImportBodyLimit

    sent = []

    async def downstream(scope, receive, send):
        pytest.fail("Oversized body must never reach multipart parsing")

    async def receive():
        return {"type": "http.request", "body": b"x" * (3 * 1024 * 1024), "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(ImportBodyLimit(downstream)({"type": "http", "path": path, "headers": []}, receive, send))
    assert sent[0]["status"] == 413
