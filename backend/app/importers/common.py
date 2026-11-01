import re
from decimal import Decimal, InvalidOperation
from datetime import datetime


def cents(value):
    if isinstance(value, bool):
        raise ValueError("Importo non valido.")
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return 0
    if "," in text and "." in text:
        raise ValueError("Separatore monetario ambiguo.")
    try:
        amount = Decimal(text.replace(",", ".")) * 100
        if not amount.is_finite() or amount != amount.to_integral_value() or abs(amount) > 10**12:
            raise ValueError("Importo non valido o più di due decimali.")
        return int(amount)
    except InvalidOperation as exc:
        raise ValueError("Importo non leggibile.") from exc


def parse_date(value):
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Data non valida (usa AAAA-MM-GG oppure GG/MM/AAAA).")


def currency(value):
    v = str(value).strip().upper()
    if not re.fullmatch("[A-Z]{3}", v):
        raise ValueError("Valuta mancante o non valida.")
    return v


def empty():
    return {"people": [], "groups": [], "records": [], "errors": [], "warnings": []}


def finalize(data):
    data["people"] = sorted({p for r in data["records"] for p in r["deltas"]})
    data["groups"] = sorted({r["group"] for r in data["records"]})
    currencies = sorted({r["currency"] for r in data["records"] if r["currency"] != "EUR"})
    if currencies:
        data["warnings"].append(
            "Valute conservate separatamente, senza conversione: " + ", ".join(currencies)
        )
    if not data["records"] and not data["errors"]:
        data["errors"].append("Il file non contiene transazioni.")
    return data
