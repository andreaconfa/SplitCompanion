from alembic import context
from sqlmodel import SQLModel
from app import push_models  # noqa: F401
from app import models  # noqa: F401 -- register tables for Alembic metadata
from app.db import engine


def run_migrations():
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=SQLModel.metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
