"""Opt-in device subscriptions and transactional push outbox."""

from alembic import op
import sqlalchemy as sa

revision = "0004_push"
down_revision = "0003_categories"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pushdevice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("session_hash", sa.String(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_pushdevice_user_id", "pushdevice", ["user_id"])
    op.create_table(
        "pushoutbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.UniqueConstraint("event_key", "device_id"),
    )
    for field in ["device_id", "next_attempt", "status"]:
        op.create_index("ix_pushoutbox_" + field, "pushoutbox", [field])


def downgrade():
    op.drop_table("pushoutbox")
    op.drop_table("pushdevice")
