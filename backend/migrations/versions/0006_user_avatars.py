"""Profile photo pixels and cache version, without changing authentication state."""

from alembic import op
import sqlalchemy as sa

revision = "0006_user_avatars"
down_revision = "0005_mfa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("avatar_version", sa.String(), nullable=True))
    op.create_table(
        "useravatar",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("png", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("useravatar")
    op.drop_column("user", "avatar_version")
