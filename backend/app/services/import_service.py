import hashlib
import json
import secrets
from collections import defaultdict
from datetime import date
from fastapi import HTTPException
from sqlmodel import select, delete
from app.models import (
    ImportBatch,
    ImportedRecord,
    User,
    Group,
    GroupMember,
    Expense,
    ExpenseSplit,
    Settlement,
    LegacyTransaction,
    LegacyTransactionEntry,
    now,
)
from app.auth import hasher
from app.schemas import UserCreate
from app.services.access import group_access
from app.services.records import delete_expense


def data_for(batch):
    return json.loads(batch.data_json)


def mapping_for(batch):
    return json.loads(batch.mapping_json)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def fingerprint(record, fmt, ordinal):
    if record["external_id"]:
        return f"SPLITWISE:ID:{record['external_id']}"
    return (
        "SPLITWISE:"
        + digest({k: v for k, v in record.items() if k not in ("raw", "external_id")})
        + f":{ordinal}"
    )


def record_keys(batch):
    data = data_for(batch)
    mapping = mapping_for(batch)
    seen = defaultdict(int)
    for record in data["records"]:
        # Once mapped, identities refer to local accounts/groups, never filenames.
        # Preserve multiplicity for indistinguishable CSV rows without external IDs.
        deltas = defaultdict(int)
        for person, delta in record["deltas"].items():
            target = mapping.get("users", {}).get(person, {"external": person})
            if target is None:
                continue
            if isinstance(target, dict):
                target = {k: v for k, v in target.items() if k != "password_hash"}
            deltas[json.dumps(target, sort_keys=True)] += delta
        normalized = {
            "external_id": record["external_id"],
            "group": mapping.get("groups", {}).get(record["group"], {"external": record["group"]}),
            "date": record["date"],
            "description": " ".join(record["description"].split()),
            "currency": record["currency"],
            "amount_cents": record["amount_cents"],
            "deltas": {key: value for key, value in deltas.items() if value},
        }
        base = digest(normalized)
        seen[base] += 1
        yield record, fingerprint(normalized, batch.format, seen[base])


def batch_response(batch):
    data = data_for(batch)
    mapping = mapping_for(batch)
    safe_users = {
        k: (
            {ik: iv for ik, iv in v.items() if ik not in ("password", "password_hash")}
            if isinstance(v, dict)
            else v
        )
        for k, v in mapping.get("users", {}).items()
    }
    return {
        **{
            k: getattr(batch, k)
            for k in (
                "id",
                "source",
                "format",
                "original_filename",
                "status",
                "records_total",
                "records_imported",
                "records_skipped",
                "records_failed",
                "created_at",
                "completed_at",
            )
        },
        "people": data.get("people", []),
        "groups": data.get("groups", []),
        "errors": data.get("errors", []),
        "warnings": data.get("warnings", []),
        "mapping": {"users": safe_users, "groups": mapping.get("groups", {})},
    }


def save_mapping(s, batch, values, actor):
    if batch.status not in ("ANALYZED", "MAPPED"):
        raise ValueError("Questo import non è più modificabile.")
    users = values["users"]
    groups = values["groups"]
    data = data_for(batch)
    if set(users) != set(data["people"]) or set(groups) != set(data["groups"]):
        raise ValueError("Completa il mapping di tutte le persone e i gruppi.")
    normalized_users = {}
    new_usernames = set()
    for external, value in users.items():
        if value is None:
            normalized_users[external] = None
            continue
        if type(value) is int:
            u = s.get(User, value)
            if not u or not u.is_active:
                raise ValueError("Utente mappato inesistente o disabilitato.")
            normalized_users[external] = value
        elif isinstance(value, dict):
            validated = UserCreate(
                username=value.get("username", ""),
                display_name=value.get("display_name", external),
                password=value.get("password") or secrets.token_urlsafe(32),
            )
            existing = s.exec(select(User).where(User.username == validated.username)).first()
            if existing:
                raise ValueError("Username già presente: associalo all’utente esistente.")
            canonical = " ".join(validated.display_name.casefold().split())
            if any(
                " ".join(u.display_name.casefold().split()) == canonical
                for u in s.exec(select(User)).all()
            ):
                raise ValueError("Esiste già un utente con questo nome: usa il mapping esistente.")
            if validated.username in new_usernames:
                raise ValueError("Username duplicato nel mapping.")
            new_usernames.add(validated.username)
            normalized_users[external] = {
                "username": validated.username,
                "display_name": validated.display_name,
                "password_hash": hasher.hash(validated.password),
            }
        else:
            raise ValueError("Mapping utente non valido.")
    for external, value in groups.items():
        if type(value) is int:
            group_access(s, actor, value, True)
        elif (
            not isinstance(value, dict)
            or not isinstance(value.get("name"), str)
            or not value["name"].strip()
            or len(value["name"]) > 200
        ):
            raise ValueError("Mapping gruppo non valido.")
    batch.mapping_json = json.dumps({"users": normalized_users, "groups": groups})
    batch.status = "MAPPED"
    batch.previewed = False
    s.add(batch)
    s.flush()


def preview(s, batch, actor):
    data = data_for(batch)
    mapping = mapping_for(batch)
    errors = list(data["errors"])
    warnings = list(data["warnings"])
    records = []
    deltas = defaultdict(int)
    duplicates = 0
    seen = set()
    users = mapping.get("users", {})
    groups = mapping.get("groups", {})
    if set(users) != set(data["people"]) or set(groups) != set(data["groups"]):
        errors.append("Completa il mapping prima di importare.")
    for record, key in record_keys(batch):
        duplicate = (
            key in seen
            or s.exec(select(ImportedRecord).where(ImportedRecord.fingerprint == key)).first()
            is not None
        )
        seen.add(key)
        if duplicate:
            duplicates += 1
        for person, delta in record["deltas"].items():
            if person not in users:
                continue
            if users[person] is None:
                has_share = record.get("shares", {}).get(person, 0) != 0
                if delta or has_share or person in (record.get("payer"), record.get("payee")):
                    errors.append(f"{record['description']}: {person} non può essere ignorato.")
            if not duplicate:
                deltas[record["group"], person, record["currency"]] += delta
        gid = groups.get(record["group"])
        if type(gid) is int:
            group_access(s, actor, gid, True)
            for person, value in users.items():
                if person not in record["deltas"] or type(value) is not int:
                    continue
                m = s.exec(
                    select(GroupMember).where(
                        GroupMember.group_id == gid, GroupMember.user_id == value
                    )
                ).first()
                if m and not m.active:
                    errors.append(
                        f"{person}: membro disattivato nel gruppo; riattivalo prima dell’import."
                    )
        if (
            record["kind"] == "SETTLEMENT"
            and users.get(record.get("payer")) is not None
            and users.get(record.get("payer")) == users.get(record.get("payee"))
        ):
            errors.append(
                f"{record['description']}: mittente e destinatario devono essere diversi."
            )
        records.append({k: v for k, v in record.items() if k != "raw"} | {"duplicate": duplicate})
    errors = list(dict.fromkeys(errors))
    return {
        "records_total": len(records),
        "importable": len(records) - duplicates if not errors else 0,
        "duplicates": duplicates,
        "errors": errors,
        "warnings": warnings,
        "records": records,
        "balance_deltas": [
            {"group": g, "user": u, "currency": c, "amount_cents": v}
            for (g, u, c), v in sorted(deltas.items())
        ],
    }


def commit(s, batch, actor):
    if batch.status != "MAPPED" or not batch.previewed:
        raise ValueError("Visualizza e conferma l’anteprima prima di importare.")
    result = preview(s, batch, actor)
    if result["errors"]:
        raise ValueError("L’anteprima contiene errori: correggi il file o il mapping.")
    if s.exec(
        select(ImportBatch).where(
            ImportBatch.file_hash == batch.file_hash, ImportBatch.status == "COMPLETED"
        )
    ).first():
        raise HTTPException(409, "Questo file Splitwise risulta già importato.")
    mapping = mapping_for(batch)
    users = {}
    groups = {}
    for external, value in mapping["users"].items():
        if value is None:
            users[external] = None
        elif type(value) is int:
            u = s.get(User, value)
            if not u or not u.is_active:
                raise ValueError("Utente non più disponibile.")
            users[external] = value
        else:
            u = User(**value, is_active=True, is_admin=False)
            s.add(u)
            s.flush()
            users[external] = u.id
    for external, value in mapping["groups"].items():
        if type(value) is int:
            group_access(s, actor, value, True)
            groups[external] = value
        else:
            g = Group(name=value["name"].strip(), created_by_user_id=actor.id)
            s.add(g)
            s.flush()
            groups[external] = g.id
            s.add(GroupMember(group_id=g.id, user_id=actor.id))
            s.flush()
    batch.mapping_json = json.dumps({"users": users, "groups": groups})
    from app.services.category_service import seed, classified_metadata

    seed(s)
    imported = skipped = 0
    for record, key in record_keys(batch):
        if s.exec(select(ImportedRecord).where(ImportedRecord.fingerprint == key)).first():
            skipped += 1
            continue
        gid = groups[record["group"]]
        for person in record["deltas"]:
            uid = users[person]
            if uid is None:
                continue
            m = s.exec(
                select(GroupMember).where(GroupMember.group_id == gid, GroupMember.user_id == uid)
            ).first()
            if m and not m.active:
                raise ValueError("Membro disabilitato durante l’import.")
            if not m:
                s.add(GroupMember(group_id=gid, user_id=uid))
                s.flush()
        common = {
            "group_id": gid,
            "currency": record["currency"],
            "import_batch_id": batch.id,
            "external_id": record["external_id"],
            "source": "SPLITWISE",
        }
        if record["kind"] == "EXPENSE":
            e = Expense(
                **common,
                description=record["description"],
                **classified_metadata(s, record["description"], record.get("raw", {})),
                amount_cents=record["amount_cents"],
                paid_by_user_id=users[record["payer"]],
                expense_date=date.fromisoformat(record["date"]),
                created_by_user_id=actor.id,
                notes="Importato da Splitwise",
            )
            s.add(e)
            s.flush()
            shares = defaultdict(int)
            for p, value in record["shares"].items():
                if users[p] is not None:
                    shares[users[p]] += value
            if sum(shares.values()) != e.amount_cents:
                raise ValueError("Quote importate incoerenti.")
            for uid, value in shares.items():
                s.add(ExpenseSplit(expense_id=e.id, user_id=uid, amount_cents=value))
        elif record["kind"] == "SETTLEMENT":
            t = Settlement(
                **common,
                paid_by_user_id=users[record["payer"]],
                paid_to_user_id=users[record["payee"]],
                amount_cents=record["amount_cents"],
                settlement_date=date.fromisoformat(record["date"]),
                created_by_user_id=actor.id,
                notes=record["description"],
            )
            s.add(t)
        else:
            t = LegacyTransaction(
                **common,
                date=date.fromisoformat(record["date"]),
                description=record["description"],
                **classified_metadata(s, record["description"], record.get("raw", {})),
                cost_cents=record["amount_cents"],
                raw_metadata_json=json.dumps(record["raw"], ensure_ascii=False),
            )
            s.add(t)
            s.flush()
            entries = defaultdict(int)
            for person, delta in record["deltas"].items():
                if users[person] is not None:
                    entries[users[person]] += delta
            if sum(entries.values()) != 0:
                raise ValueError("I delta importati non sommano a zero.")
            for uid, value in entries.items():
                s.add(
                    LegacyTransactionEntry(
                        legacy_transaction_id=t.id, user_id=uid, balance_delta_cents=value
                    )
                )
        s.add(ImportedRecord(fingerprint=key, import_batch_id=batch.id))
        s.flush()
        imported += 1
    batch.records_imported = imported
    batch.records_skipped = skipped
    batch.records_failed = 0
    batch.status = "COMPLETED"
    batch.completed_at = now()
    # Erase bootstrap password hashes once new accounts have been created.
    batch.mapping_json = json.dumps({"users": users, "groups": groups})
    s.add(batch)
    s.flush()
    return batch_response(batch)


def rollback(s, batch, actor):
    if batch.status != "COMPLETED":
        raise ValueError("Solo un import completato può essere annullato.")
    for model in (Expense, Settlement, LegacyTransaction):
        for row in s.exec(select(model).where(model.import_batch_id == batch.id)).all():
            group_access(s, actor, row.group_id)
            if model is Expense:
                delete_expense(s, row)
            elif model is LegacyTransaction:
                s.exec(
                    delete(LegacyTransactionEntry).where(
                        LegacyTransactionEntry.legacy_transaction_id == row.id
                    )
                )
                s.delete(row)
            else:
                s.delete(row)
    s.exec(delete(ImportedRecord).where(ImportedRecord.import_batch_id == batch.id))
    batch.status = "ROLLED_BACK"
    s.add(batch)
    s.flush()
    return batch_response(batch)
