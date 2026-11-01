"""Shared display metadata. Never modifies accounting or import provenance."""

import re
from sqlmodel import select
from app.models import Category, CustomIcon

PREDEFINED = [
    ("groceries", "Spesa alimentare", "shopping-basket"),
    ("dining", "Ristoranti e bar", "utensils"),
    ("home", "Casa", "house"),
    ("bills", "Utenze", "zap"),
    ("transport", "Trasporti", "car"),
    ("travel", "Viaggi", "plane"),
    ("health", "Salute", "heart-pulse"),
    ("pets", "Animali", "paw-print"),
    ("entertainment", "Svago", "popcorn"),
    ("shopping", "Shopping", "shopping-bag"),
    ("software", "Software e AI", "bot"),
    ("education", "Istruzione", "graduation-cap"),
    ("gifts", "Regali", "gift"),
    ("sport", "Sport", "dumbbell"),
    ("personal-care", "Cura personale", "sparkles"),
    ("electronics", "Elettronica e accessori", "smartphone"),
    ("chatgpt", "ChatGPT", "chatgpt"),
    ("transfers", "Trasferimenti e rimborsi", "arrow-left-right"),
]
ICONS = {icon for _, _, icon in PREDEFINED} | {"tag", "chatgpt"}


def seed(s):
    for slug, name, icon in PREDEFINED:
        if not s.exec(select(Category).where(Category.slug == slug)).first():
            s.add(Category(slug=slug, name=name, icon_key=icon))
    s.flush()


def validate_icon(s, key):
    if key in ICONS:
        return
    if re.fullmatch(r"upload:[1-9][0-9]*", key) and s.get(CustomIcon, int(key[7:])):
        return
    raise ValueError("Icona non valida.")


def validate_metadata(s, category_id):
    if category_id is not None and not s.get(Category, category_id):
        raise ValueError("Categoria non trovata.")


def category_icon(s, category_id):
    category = s.get(Category, category_id) if category_id is not None else None
    return category.icon_key if category else None


ALIASES = {
    "groceries": ["groceries", "spesa alimentare", "alimentari", "generi alimentari"],
    "dining": ["dining out", "ristorante", "ristoranti", "restaurants", "bar", "ristoranti e bar"],
    "home": ["rent", "affitto", "casa", "home", "household supplies", "forniture domestiche"],
    "bills": [
        "utilities",
        "utenze",
        "electricity",
        "elettricità",
        "acqua",
        "water",
        "gas",
        "internet",
        "telefono",
    ],
    "transport": [
        "transportation",
        "trasporti",
        "carburante",
        "gas/fuel",
        "parking",
        "parcheggio",
        "taxi",
        "bus/train",
        "autobus/treno",
    ],
    "travel": ["travel", "viaggi", "hotel", "plane", "aereo"],
    "health": ["medical expenses", "spese mediche", "salute", "health", "medicine", "medicinali"],
    "pets": ["pets", "animali domestici", "animali"],
    "entertainment": [
        "entertainment",
        "svago",
        "intrattenimento",
        "movies",
        "cinema",
        "music",
        "musica",
        "games",
        "giochi",
    ],
    "shopping": ["clothing", "abbigliamento", "shopping"],
    "electronics": ["electronics", "elettronica", "elettronica e accessori"],
    "personal-care": ["personal care", "cura personale"],
    "transfers": ["transfers", "trasferimenti", "trasferimenti e rimborsi"],
    "chatgpt": ["chatgpt"],
    "software": ["software", "software e ai"],
    "education": ["education", "istruzione", "books", "libri"],
    "gifts": ["gifts", "regali"],
    "sport": ["sports", "sport"],
}


DESCRIPTION_RULES = [
    ("pets", r"\b(perlavet|veterinari[oa]|vererinario|lettiera|filaria|guinzaglio|crocchette)\b"),
    (
        "home",
        r"\b(donna\s+(?:delle\s+)?pul(?:izie|zie)|bidone\s+umido|prodotti\s+per\s+(?:la\s+)?pulizia|mensola\s+lavatrice|coperchio\s+pentola)\b",
    ),
    ("bills", r"\b(bollett[ae]\s+(?:elettricit[aà]|luce|gas|acqua)|tari)\b"),
    ("dining", r"\b(pok[eé]|caff[eè])\b"),
    ("health", r"\b(fluimucil|farmac[oi])\b"),
    ("groceries", r"\bfinocchi\b"),
    ("personal-care", r"\b(bagnoschiuma|spazzolino|capelli)\b"),
    (
        "electronics",
        r"\b(caricatore\s+(?:per\s+)?apple\s*watch|chiavetta\s+usb|cover\s+(?:telefono|iphone(?:\s+17\s*pro\s*max)?|17\s*pro\s*max))\b",
    ),
]


def classify(description, raw=None, pet_context=False):
    text = description.casefold()
    if re.search(r"\b(pareggio|rimborso|prestito|restituzione)\b", text):
        return "transfers", None, "description:transfers"
    if re.search(r"\b(chatgpt|openai)\b", text):
        return "chatgpt", None, "description:chatgpt"
    if pet_context and re.search(r"\b(cibo|pappa|farmaco|integratore|antibiotico|zaino)\b", text):
        return "pets", None, "description:pet-context"
    for slug, pattern in DESCRIPTION_RULES:
        if re.search(pattern, text):
            return slug, None, "description:" + slug
    for key, value in (raw or {}).items():
        if key.strip().casefold() in (
            "category",
            "categories",
            "categoria",
            "categorie",
        ) and isinstance(value, str):
            normalized = value.strip().casefold()
            for slug, aliases in ALIASES.items():
                if normalized in aliases:
                    return slug, None, "csv:" + value
    return None, None, None


def classified_metadata(s, description, raw=None, pet_context=False):
    slug, _, reason = classify(description, raw, pet_context)
    category = s.exec(select(Category).where(Category.slug == slug)).first() if slug else None
    return {
        "category_id": category.id if category else None,
        "icon_key": None,
        "category_source": "auto:" + reason if reason else None,
    }
