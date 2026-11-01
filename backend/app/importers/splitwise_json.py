from fastapi import HTTPException
import json
from decimal import Decimal
from app.importers.common import cents, parse_date, currency, empty, finalize


def person_key(user):
    name = " ".join(
        str(user.get(k) or "").strip() for k in ("first_name", "last_name")
    ).strip() or str(user.get("name") or user.get("email") or "")
    if not name:
        raise ValueError("Nome partecipante mancante.")
    return f"{name} [#{user['id']}]" if user.get("id") is not None else name


def parse_json(content: bytes):
    data = empty()
    try:
        root = json.loads(content.decode("utf-8-sig"), parse_float=Decimal)
        if isinstance(root, list):
            root = {"expenses": root}
        if not isinstance(root, dict):
            raise ValueError("Struttura JSON non supportata.")
        groups = {
            str(g["id"]): f"{g['name']} [#{g['id']}]"
            for g in root.get("groups", [])
            if isinstance(g, dict) and "id" in g and "name" in g
        }
        expenses = root.get("expenses")
        if expenses is None:
            expenses = [
                {**e, "group_id": g.get("id")}
                for g in root.get("groups", [])
                for e in g.get("expenses", [])
            ]
        if not isinstance(expenses, list):
            raise ValueError("Il JSON deve contenere una lista expenses.")
        if len(expenses) > 10000:
            raise HTTPException(413, "Il file supera il limite di 10000 record.")
        for index, item in enumerate(expenses, 1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("Transazione non valida.")
                if item.get("deleted_at"):
                    data["warnings"].append(f"Record {index}: transazione eliminata esclusa.")
                    continue
                day = parse_date(item.get("date", ""))
                cur = currency(item.get("currency_code", item.get("currency", "")))
                cost = cents(item.get("cost", ""))
                participants = item.get("users", [])
                if not participants:
                    raise ValueError("Partecipanti assenti.")
                paid = {}
                owed = {}
                for participant in participants:
                    key = person_key(participant.get("user", participant))
                    paid[key] = paid.get(key, 0) + cents(participant.get("paid_share", "0"))
                    owed[key] = owed.get(key, 0) + cents(participant.get("owed_share", "0"))
                deltas = {p: paid[p] - owed[p] for p in paid}
                if (
                    sum(deltas.values()) != 0
                    or sum(paid.values()) != cost
                    or sum(owed.values()) != cost
                ):
                    raise ValueError("Costi, quote e delta non coerenti.")
                if not item.get("description"):
                    raise ValueError("Descrizione mancante.")
                gid = item.get("group_id")
                group = groups.get(str(gid), f"Gruppo Splitwise {gid}" if gid else "Senza gruppo")
                record = {
                    "date": day,
                    "description": str(item["description"]),
                    "currency": cur,
                    "amount_cents": cost,
                    "group": group,
                    "deltas": deltas,
                    "kind": "LEGACY",
                    "external_id": str(item["id"]) if item.get("id") is not None else None,
                    "raw": json.loads(json.dumps(item, default=str)),
                }
                payers = [p for p, v in paid.items() if v > 0]
                pos = [p for p, v in deltas.items() if v > 0]
                neg = [p for p, v in deltas.items() if v < 0]
                if (
                    item.get("payment") is True
                    and len(pos) == len(neg) == 1
                    and cost > 0
                    and deltas[pos[0]] == cost
                ):
                    record.update(kind="SETTLEMENT", payer=pos[0], payee=neg[0])
                elif (
                    not item.get("payment")
                    and len(payers) == 1
                    and cost > 0
                    and min(paid.values()) >= 0
                    and min(owed.values()) >= 0
                ):
                    record.update(kind="EXPENSE", payer=payers[0], shares=owed)
                data["records"].append(record)
            except (ValueError, TypeError, KeyError) as exc:
                data["errors"].append(f"Record {index}: {exc}")
    except (ValueError, UnicodeError, TypeError, KeyError, AttributeError) as exc:
        data["errors"].append("JSON non valido: " + str(exc))
    return finalize(data)
