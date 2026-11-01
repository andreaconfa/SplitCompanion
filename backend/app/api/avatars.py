"""Authenticated profile photos; source bytes and metadata are never retained."""

import io
import warnings
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.auth import CurrentUser, DB
from app.models import User, UserAvatar
from app.schemas import UserResponse
from app.services.access import get_or_404

router = APIRouter(prefix="/api/users")
MAX_BYTES = 2 * 1024 * 1024
MAX_DIMENSION = 2048


def normalized_avatar(content: bytes) -> bytes:
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "La foto supera 2 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in ("PNG", "JPEG", "WEBP"):
                    raise ValueError("Usa una foto PNG, JPEG o WebP.")
                if max(source.size) > MAX_DIMENSION:
                    raise ValueError("La foto supera 2048 × 2048 pixel.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((256, 256), Image.Resampling.LANCZOS)
                # A new pixel-only image guarantees EXIF, ICC, comments and XMP are absent.
                pixels = oriented.convert("RGBA")
                clean = Image.new("RGBA", pixels.size)
                clean.paste(pixels)
                output = io.BytesIO()
                clean.save(output, "PNG")
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        SyntaxError,
    ) as exc:
        raise ValueError("Foto non valida. Usa PNG, JPEG o WebP.") from exc


def writable_user(s, actor, id):
    if actor.id != id and not actor.is_admin:
        raise HTTPException(403, "Puoi modificare solo la tua foto.")
    return get_or_404(s, User, id)


@router.get("/{id}/avatar")
def get_avatar(id: int, user: CurrentUser, s: DB):
    row = get_or_404(s, UserAvatar, id)
    return Response(row.png, media_type="image/png")


@router.post("/{id}/avatar", response_model=UserResponse)
def upload_avatar(id: int, user: CurrentUser, s: DB, file: UploadFile = File(...)):
    target = writable_user(s, user, id)
    png = normalized_avatar(file.file.read(MAX_BYTES + 1))
    row = s.get(UserAvatar, id)
    if row is None:
        row = UserAvatar(user_id=id, png=png)
    else:
        row.png = png
    target.avatar_version = uuid4().hex
    s.add(row)
    s.add(target)
    s.flush()
    return target


@router.delete("/{id}/avatar", response_model=UserResponse)
def delete_avatar(id: int, user: CurrentUser, s: DB):
    target = writable_user(s, user, id)
    row = s.get(UserAvatar, id)
    if row is not None:
        s.delete(row)
    target.avatar_version = None
    s.add(target)
    s.flush()
    return target
