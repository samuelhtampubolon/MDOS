"""Apply database migrations at start-up (desktop and cloud).

Alembic revisions live in ``mdos/migrations/versions``. If no revision exists (early development) the
schema is created directly from the models.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from .db import create_all, get_engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _alembic_config():
    from alembic.config import Config

    cfg = Config()
    # ConfigParser treats "%" as interpolation; file URLs contain it (for example "D%3A" for a Windows drive).
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR).replace("%", "%%"))
    cfg.set_main_option("sqlalchemy.url", get_engine().url.render_as_string(hide_password=False).replace("%", "%%"))
    return cfg


def upgrade_database() -> None:
    versions = MIGRATIONS_DIR / "versions"
    if not (versions.exists() and any(versions.glob("*.py"))):
        create_all()
        return

    from alembic import command

    engine = get_engine()
    tables = set(inspect(engine).get_table_names())
    cfg = _alembic_config()
    legacy = bool(tables) and "alembic_version" not in tables
    if legacy:  # database created before migrations existed: complete it, then record it as current
        create_all()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        if legacy:
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
