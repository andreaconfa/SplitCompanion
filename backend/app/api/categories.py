import io
import warnings
from fastapi import APIRouter, File, UploadFile, HTTPException, Response
from PIL import Image, UnidentifiedImageError
from sqlmodel import select
from app.auth import DB, CurrentUser, Admin
from app.models import Category, CustomIcon, Expense, Subscription, LegacyTransaction
from app.schemas import Input, Name, CategoryInput
from app.services.access import get_or_404, group_access
from app.services.category_service import validate_icon, validate_metadata, ICONS

router = APIRouter(prefix="/api")


class CategoryWrite(Input):
    name: Name
    icon_key: str


@router.get("/categories")
def categories(user: CurrentUser, s: DB):
    return s.exec(select(Category).order_by(Category.name)).all()


@router.post("/categories", status_code=201)
def create_category(data: CategoryWrite, user: Admin, s: DB):
    validate_icon(s, data.icon_key)
    row = Category(**data.model_dump(), created_by_user_id=user.id)
    s.add(row)
    s.flush()
    return row


@router.patch("/categories/{id}")
def update_category(id: int, data: CategoryWrite, user: Admin, s: DB):
    row = get_or_404(s, Category, id)
    validate_icon(s, data.icon_key)
    row.name, row.icon_key = data.name, data.icon_key
    s.add(row)
    return row


@router.delete("/categories/{id}")
def delete_category(id: int, user: Admin, s: DB):
    row = get_or_404(s, Category, id)
    if row.slug is not None:
        raise HTTPException(409, "Le categorie predefinite non possono essere eliminate.")
    if any(
        s.exec(select(model.id).where(model.category_id == id)).first()
        for model in (Expense, Subscription, LegacyTransaction)
    ):
        raise HTTPException(409, "Categoria in uso: riassegna prima i movimenti.")
    s.delete(row)
    return {"ok": True}


@router.get("/icons")
def icons(user: CurrentUser, s: DB):
    return {
        "builtin": sorted(ICONS),
        "custom": [
            {
                "id": i.id,
                "name": i.name,
                "icon_key": f"upload:{i.id}",
                "created_by_user_id": i.created_by_user_id,
            }
            for i in s.exec(select(CustomIcon)).all()
        ],
    }


@router.post("/icons", status_code=201)
def upload_icon(user: Admin, s: DB, file: UploadFile = File(...)):
    content = file.file.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise HTTPException(413, "L’icona supera 1 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if (
                    source.format not in ("PNG", "JPEG", "WEBP")
                    or source.width > 2048
                    or source.height > 2048
                ):
                    raise ValueError("Usa PNG, JPEG o WebP fino a 2048 × 2048 pixel.")
                source.load()
                normalized = source.convert("RGBA")
                normalized.info.clear()
                normalized.thumbnail((128, 128))
                output = io.BytesIO()
                normalized.save(output, format="PNG")
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValueError("Immagine non valida. Usa PNG, JPEG o WebP.")
    row = CustomIcon(
        name=(file.filename or "Icona")[:200], created_by_user_id=user.id, png=output.getvalue()
    )
    s.add(row)
    s.flush()
    return {
        "id": row.id,
        "name": row.name,
        "icon_key": f"upload:{row.id}",
        "created_by_user_id": user.id,
    }


@router.get("/icons/{id}/image")
def icon_image(id: int, user: CurrentUser, s: DB):
    return Response(get_or_404(s, CustomIcon, id).png, media_type="image/png")


@router.delete("/icons/{id}")
def delete_icon(id: int, user: Admin, s: DB):
    icon = get_or_404(s, CustomIcon, id)
    key = f"upload:{id}"
    if s.exec(select(Category.id).where(Category.icon_key == key)).first():
        raise HTTPException(409, "Icona in uso: rimuovila prima dalle categorie.")
    s.delete(icon)
    return {"ok": True}


@router.patch("/legacy/{id}/category")
def legacy_category(id: int, data: CategoryInput, user: CurrentUser, s: DB):
    from app.api.expenses import legacy_response

    row = get_or_404(s, LegacyTransaction, id)
    group_access(s, user, row.group_id, True)
    apply_metadata(s, row, data)
    return legacy_response(s, row)


@router.patch("/expenses/{id}/category")
def expense_category(id: int, data: CategoryInput, user: CurrentUser, s: DB):
    from app.services.records import expense_response

    row = get_or_404(s, Expense, id)
    group_access(s, user, row.group_id, True)
    apply_metadata(s, row, data)
    return expense_response(s, row)


def apply_metadata(s, row, data):
    values = data.model_dump(exclude_unset=True)
    validate_metadata(s, values.get("category_id", row.category_id))
    if "category_id" in values:
        row.category_id = values["category_id"]
        row.category_source = "manual"
    row.icon_key = None
    s.add(row)
    s.flush()
