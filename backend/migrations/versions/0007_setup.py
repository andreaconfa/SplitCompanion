"""Durable first-run gate, closed for every existing installation with users."""

from alembic import op
import sqlalchemy as sa

revision = "0007_setup"
down_revision = "0006_user_avatars"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "setupstate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("attempt_window_expires_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("id = 1"),
    )
    op.execute(
        sa.text(
            'INSERT INTO setupstate (id, completed, attempts) VALUES (1, EXISTS(SELECT 1 FROM "user"), 0)'
        )
    )


def downgrade():
    op.drop_table("setupstate")
