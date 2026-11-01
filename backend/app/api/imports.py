import hashlib
import json
from pathlib import PurePath
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from sqlmodel import select
from app.auth import DB, Admin
from app.models import ImportBatch, User
from app.schemas import MappingInput
from app.services.access import get_or_404, group_access
from app.services import import_service as service
from app.importers.splitwise_csv import parse_csv
from app.importers.splitwise_json import parse_json

router = APIRouter(prefix="/api")


def batch_access(s, admin, id):
    batch = get_or_404(s, ImportBatch, id)
    if batch.uploaded_by_user_id != admin.id:
        raise HTTPException(403, "Questo import appartiene a un altro amministratore.")
    for target in service.mapping_for(batch).get("groups", {}).values():
        if type(target) is int:
            group_access(s, admin, target)
    return batch


@router.post("/imports/splitwise/analyze")
def analyze(admin: Admin, s: DB, file: UploadFile = File(...)):
    content = file.file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Il file supera il limite di 10 MB.")
    if not content.strip():
        raise ValueError("Il file è vuoto.")
    filename = PurePath((file.filename or "import").replace("\\", "/")).name[:200]
    file_hash = hashlib.sha256(content).hexdigest()
    if s.exec(
        select(ImportBatch).where(
            ImportBatch.file_hash == file_hash, ImportBatch.status == "COMPLETED"
        )
    ).first():
        raise HTTPException(409, "Questo file Splitwise risulta già importato.")
    sample = content.lstrip(b"\xef\xbb\xbf \t\r\n")
    fmt = "JSON" if sample.startswith((b"{", b"[")) else "CSV"
    data = (
        parse_json(content)
        if fmt == "JSON"
        else parse_csv(content, PurePath(filename).stem or "Splitwise")
    )
    mapping = {"users": {}, "groups": {}}
    users = s.exec(select(User).where(User.is_active == True)).all()
    for person in data["people"]:
        name = person.split(" [#")[0]
        matches = [
            u.id
            for u in users
            if " ".join(u.display_name.casefold().split()) == " ".join(name.casefold().split())
        ]
        if len(matches) == 1:
            mapping["users"][person] = matches[0]
    batch = ImportBatch(
        format=fmt,
        original_filename=filename,
        file_hash=file_hash,
        uploaded_by_user_id=admin.id,
        records_total=len(data["records"]),
        records_failed=len(data["errors"]),
        data_json=json.dumps(data, ensure_ascii=False),
        mapping_json=json.dumps(mapping),
    )
    s.add(batch)
    s.flush()
    return service.batch_response(batch)


@router.get("/imports")
def list_imports(
    admin: Admin,
    s: DB,
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    result = []
    for batch in s.exec(
        select(ImportBatch)
        .where(ImportBatch.uploaded_by_user_id == admin.id)
        .order_by(ImportBatch.id.desc())
    ).all():
        try:
            batch_access(s, admin, batch.id)
        except HTTPException:
            continue
        result.append(service.batch_response(batch))
    return result[offset:] if limit is None else result[offset : offset + limit]


@router.get("/imports/{id}")
def get_import(id: int, admin: Admin, s: DB):
    return service.batch_response(batch_access(s, admin, id))


@router.post("/imports/splitwise/{id}/mapping")
def mapping(id: int, data: MappingInput, admin: Admin, s: DB):
    batch = batch_access(s, admin, id)
    service.save_mapping(s, batch, data.model_dump(), admin)
    return service.preview(s, batch, admin)


@router.get("/imports/splitwise/{id}/preview")
def preview(id: int, admin: Admin, s: DB):
    batch = batch_access(s, admin, id)
    result = service.preview(s, batch, admin)
    if batch.status == "MAPPED":
        batch.previewed = True
        s.add(batch)
    return result


@router.post("/imports/splitwise/{id}/commit")
def commit(id: int, admin: Admin, s: DB):
    batch = batch_access(s, admin, id)
    if len(service.data_for(batch)["records"]) > 10000:
        raise HTTPException(413, "Il file supera il limite di 10000 record.")
    return service.commit(s, batch, admin)


@router.delete("/imports/{id}")
def rollback(id: int, admin: Admin, s: DB, confirm: bool = False):
    if not confirm:
        raise ValueError("Conferma esplicitamente l’annullamento dell’import.")
    return service.rollback(s, batch_access(s, admin, id), admin)
