from decimal import Decimal, InvalidOperation


def calculate_splits(amount: int, mode: str, parts: list[dict]) -> dict[int, int]:
    if type(amount) is not int or amount <= 0 or amount > 10**12:
        raise ValueError("Importo non valido.")
    if not parts or len({p["user_id"] for p in parts}) != len(parts):
        raise ValueError("Scegli partecipanti distinti.")
    parts = sorted(parts, key=lambda p: p["user_id"])
    ids = [p["user_id"] for p in parts]
    if mode == "equal":
        share, remainder = divmod(amount, len(parts))
        return {uid: share + (i < remainder) for i, uid in enumerate(ids)}
    if mode == "single":
        if len(ids) != 1:
            raise ValueError("Scegli una sola persona.")
        return {ids[0]: amount}
    if mode == "exact":
        values = [p.get("amount_cents") for p in parts]
        if any(type(v) is not int or v < 0 for v in values) or sum(values) != amount:
            raise ValueError("Le quote devono totalizzare esattamente l’importo della spesa.")
        return dict(zip(ids, values))
    if mode == "percent":
        try:
            values = [Decimal(str(p.get("percentage", ""))) for p in parts]
            if any(not v.is_finite() or v < 0 or v > 100 for v in values) or sum(values) != 100:
                raise ValueError("Le percentuali devono totalizzare 100%.")
        except InvalidOperation as exc:
            raise ValueError("Percentuale non valida.") from exc
        raw = [Decimal(amount) * v / 100 for v in values]
        cents = [int(v) for v in raw]
        order = sorted(range(len(ids)), key=lambda i: (-(raw[i] - cents[i]), ids[i]))
        for i in order[: amount - sum(cents)]:
            cents[i] += 1
        return dict(zip(ids, cents))
    raise ValueError("Modalità di divisione non valida.")
