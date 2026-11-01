"""Category and custom icon display metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0003_categories"
down_revision = "957ebab70c5c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), unique=True),
        sa.Column("icon_key", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id")),
    )
    op.create_table(
        "customicon",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("png", sa.LargeBinary(), nullable=False),
    )
    for table in ("expense", "subscription", "legacytransaction"):
        # SQLite supports nullable REFERENCES columns without rebuilding live accounting tables.
        op.execute(f"ALTER TABLE {table} ADD COLUMN category_id INTEGER REFERENCES category(id)")
        op.add_column(table, sa.Column("icon_key", sa.String(), nullable=True))
        op.add_column(table, sa.Column("category_source", sa.String(), nullable=True))
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
    ]
    from datetime import datetime, timezone

    category = sa.table(
        "category",
        sa.column("name"),
        sa.column("slug"),
        sa.column("icon_key"),
        sa.column("created_at"),
    )
    op.bulk_insert(
        category,
        [
            dict(slug=slug, name=name, icon_key=icon, created_at=datetime.now(timezone.utc))
            for slug, name, icon in PREDEFINED
        ],
    )


def downgrade():
    for table in ("expense", "subscription", "legacytransaction"):
        for column in ("category_id", "icon_key", "category_source"):
            op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    op.drop_table("customicon")
    op.drop_table("category")
