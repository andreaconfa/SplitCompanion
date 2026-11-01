"""Encrypted TOTP, recovery codes, temporary challenges and durable throttling."""

from alembic import op
import sqlalchemy as sa

revision = "0005_mfa"
down_revision = "0004_push"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("mfa_secret", sa.String(), nullable=True))
    op.add_column(
        "user", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "user", sa.Column("mfa_last_counter", sa.Integer(), nullable=False, server_default="-1")
    )
    op.add_column(
        "authsession",
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "mfachallenge",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("secret", sa.String(), nullable=True),
    )
    op.create_index("ix_mfachallenge_user_id", "mfachallenge", ["user_id"])
    op.create_table(
        "mfarecovery",
        sa.Column("code_hash", sa.String(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
    )
    op.create_index("ix_mfarecovery_user_id", "mfarecovery", ["user_id"])
    op.create_table(
        "auththrottle",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("auththrottle")
    op.drop_table("mfarecovery")
    op.drop_table("mfachallenge")
    op.drop_column("authsession", "mfa_verified")
    op.drop_column("user", "mfa_last_counter")
    op.drop_column("user", "mfa_enabled")
    op.drop_column("user", "mfa_secret")
