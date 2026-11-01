"""Persist instance defaults and device notification language; preserve accounting rows."""
from alembic import op
import sqlalchemy as sa

revision = "0008_locale_currency"
down_revision = "0007_setup"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("instancesettings",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("default_currency", sa.String(), nullable=False),
                    sa.CheckConstraint("id = 1"))
    op.execute("INSERT INTO instancesettings (id, default_currency) VALUES (1, 'EUR')")
    op.add_column("pushdevice", sa.Column("language", sa.String(), nullable=False, server_default="en"))


def downgrade():
    op.drop_column("pushdevice", "language")
    op.drop_table("instancesettings")
