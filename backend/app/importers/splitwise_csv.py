from fastapi import HTTPException
import csv
import io
from app.importers.common import cents, parse_date, currency, empty, finalize

ALIASES = {
    "date": {"date", "data"},
    "description": {"description", "descrizione"},
    "category": {"category", "categories", "categoria", "categorie"},
    "cost": {"cost", "costo", "amount", "importo"},
    "currency": {"currency", "valuta"},
    "group": {"group", "gruppo"},
    "payer": {"paid by", "payer", "pagato da"},
    "id": {"id", "expense id", "transaction id"},
    "notes": {"notes", "note"},
}


def parse_csv(content: bytes, group_name: str):
    data = empty()
    try:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("cp1252")
        if not text.strip():
            raise ValueError("Il file è vuoto.")
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            raise ValueError("Separatore CSV non riconosciuto.")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        headers = reader.fieldnames or []
        normalized = [" ".join(h.strip().casefold().split()) for h in headers]
        if len(set(normalized)) != len(headers):
            raise ValueError("Colonne duplicate o nomi ambigui nel CSV.")
        fields = {
            key: headers[normalized.index(alias)]
            for key, aliases in ALIASES.items()
            for alias in aliases
            if alias in normalized
        }
        if not {"date", "description", "cost", "currency"}.issubset(fields):
            raise ValueError("Header inatteso: servono Date, Description, Cost e Currency.")
        people = [h for h in headers if h not in fields.values()]
        if not people:
            raise ValueError("Mancano le colonne dei partecipanti.")
        for line, row in enumerate(reader, 2):
            if line > 10001:
                raise HTTPException(413, "Il file supera il limite di 10000 record.")
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("Numero di colonne non valido.")
                if not any(v.strip() for v in row.values()):
                    continue
                description = row[fields["description"]].strip()
                if (
                    not row[fields["date"]].strip() or not row[fields["cost"]].strip()
                ) and description.casefold() in (
                    "total",
                    "totale",
                    "total balance",
                    "saldo totale",
                    "bilancio totale",
                    "total balance by currency",
                ):
                    data["warnings"].append(f"Riga {line}: riepilogo escluso.")
                    continue
                day = parse_date(row[fields["date"]])
                cur = currency(row[fields["currency"]])
                cost = cents(row[fields["cost"]])
                deltas = {p.strip(): cents(row[p]) for p in people}
                if sum(deltas.values()) != 0:
                    raise ValueError("I delta dei partecipanti non sommano a zero.")
                if not description:
                    raise ValueError("Descrizione mancante.")
                group = row[fields["group"]].strip() if "group" in fields else group_name
                if not group:
                    raise ValueError("Gruppo mancante.")
                record = {
                    "date": day,
                    "description": description,
                    "currency": cur,
                    "amount_cents": cost,
                    "group": group,
                    "deltas": deltas,
                    "kind": "LEGACY",
                    "external_id": row[fields["id"]].strip() if "id" in fields else None,
                    "raw": row,
                }
                category = row.get(fields.get("category", ""), "").strip().casefold()
                positive = [p for p, a in deltas.items() if a > 0]
                negative = [p for p, a in deltas.items() if a < 0]
                if (
                    category in ("payment", "pagamento", "settlement")
                    and len(positive) == len(negative) == 1
                    and cost > 0
                    and deltas[positive[0]] == cost
                ):
                    record.update(kind="SETTLEMENT", payer=positive[0], payee=negative[0])
                elif "payer" in fields and cost > 0:
                    payer = row[fields["payer"]].strip()
                    if payer not in deltas:
                        raise ValueError("Pagante non presente nelle colonne partecipanti.")
                    shares = {p: (cost if p == payer else 0) - delta for p, delta in deltas.items()}
                    if min(shares.values()) >= 0 and sum(shares.values()) == cost:
                        record.update(kind="EXPENSE", payer=payer, shares=shares)
                data["records"].append(record)
            except (ValueError, TypeError) as exc:
                data["errors"].append(f"Riga {line}: {exc}")
    except (ValueError, UnicodeError, csv.Error) as exc:
        data["errors"].append(str(exc))
    return finalize(data)
