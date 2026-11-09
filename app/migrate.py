"""Programmatic Alembic upgrade (used at startup when AUTO_MIGRATE=true and by scripts/migrate.py)."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import BASE_DIR, settings


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BASE_DIR) / "migrations"))
    cfg.attributes["database_url"] = database_url or settings.database_url
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")
