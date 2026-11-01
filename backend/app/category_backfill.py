"""Review category metadata with a rollback-only report unless --apply is supplied."""

import argparse
import json
import re
from sqlalchemy import text
from sqlmodel import Session, select
from app import db
from app.models import Category, Expense, Subscription, LegacyTransaction, ImportBatch
from app.services.category_service import seed, classified_metadata


def original_metadata(s, row):
    if isinstance(row, LegacyTransaction):
        return json.loads(row.raw_metadata_json)
    if isinstance(row, Expense) and row.import_batch_id:
        batch = s.get(ImportBatch, row.import_batch_id)
        matches = [
            r
            for r in json.loads(batch.data_json).get("records", [])
            if r.get("kind") == "EXPENSE"
            and r.get("description") == row.description
            and r.get("date") == row.expense_date.isoformat()
            and r.get("amount_cents") == row.amount_cents
        ]
        if len(matches) == 1:
            return matches[0].get("raw", {})
    return {}


def backfill(s, pet_group_ids=(), review_auto=False, align_icons=False):
    seed(s)
    report = []
    fields = ("category_id", "icon_key", "category_source")
    for model in (Subscription, LegacyTransaction, Expense):
        for row in s.exec(select(model)).all():
            before = {key: getattr(row, key) for key in fields}
            description = row.name if model is Subscription else row.description
            # Preserve the user's former ChatGPT icon when moving to category-owned icons.
            carry_chatgpt = (
                align_icons
                and model is Subscription
                and row.category_source == "manual"
                and row.category_id is None
                and row.icon_key == "chatgpt"
                and re.search(r"\b(chatgpt|openai)\b", description, re.IGNORECASE)
            )
            if carry_chatgpt:
                category = s.exec(select(Category).where(Category.slug == "chatgpt")).one()
                row.category_id = category.id
            elif row.category_source != "manual" and (
                (row.category_id is None and (row.icon_key is None or align_icons))
                or (review_auto and (row.category_source or "").startswith("auto:"))
            ):
                metadata = classified_metadata(
                    s, description, original_metadata(s, row), row.group_id in pet_group_ids
                )
                if model is Expense and row.subscription_id:
                    sub = s.get(Subscription, row.subscription_id)
                    if sub and sub.category_id is not None:
                        metadata = {
                            "category_id": sub.category_id,
                            "icon_key": None,
                            "category_source": "auto:subscription",
                        }
                # Lack of a confident match never erases an existing category.
                if metadata["category_id"] is not None:
                    for key, value in metadata.items():
                        setattr(row, key, value)
            if align_icons:
                row.icon_key = None
            after = {key: getattr(row, key) for key in fields}
            if before != after:
                s.add(row)
                report.append(
                    {"type": model.__name__, "id": row.id, "description": description, **after}
                )
    s.flush()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--review-auto",
        action="store_true",
        help="Recheck automatic categories; keep manual choices",
    )
    parser.add_argument(
        "--align-icons", action="store_true", help="Remove obsolete per-record icon overrides"
    )
    parser.add_argument(
        "--pet-group-id",
        type=int,
        action="append",
        default=[],
        help="Explicitly confirmed animal-care group; repeatable",
    )
    args = parser.parse_args()
    with Session(db.engine) as s:
        s.execute(text("BEGIN IMMEDIATE"))
        result = backfill(s, args.pet_group_id, args.review_auto, args.align_icons)
        if args.apply:
            s.commit()
        else:
            s.rollback()
    print(
        json.dumps(
            {"applied": args.apply, "count": len(result), "changes": result},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
