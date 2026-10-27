"""Alembic environment. Uses the application's engine settings and model metadata.

Run from the backend folder, for example: ``alembic -c alembic.ini revision --autogenerate -m "add column"``.
At start-up the app applies migrations itself (see ``mdos/migrations_runner.py``).
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from mdos import models  # noqa: F401  (register every table on the metadata)
from mdos.db import Base

config = context.config
target_metadata = Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite needs batch mode to alter tables
        compare_type=True,
    )


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # provided by the app at start-up
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        _configure(conn)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
