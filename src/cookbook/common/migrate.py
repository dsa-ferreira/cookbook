"""Run Alembic migrations from code (``cookbook migrate`` and tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection

_REPO_ROOT = Path(__file__).resolve().parents[3]  # src/cookbook/common/migrate.py


def alembic_config(url: str | None = None, connection: Connection | None = None) -> Config:
    cfg = Config(str(_ini_path()))
    if url is not None:
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if connection is not None:
        cfg.attributes["connection"] = connection
        cfg.attributes["configure_logger"] = False
    return cfg


def upgrade(revision: str = "head", **kwargs: object) -> None:
    command.upgrade(alembic_config(**kwargs), revision)  # type: ignore[arg-type]


def downgrade(revision: str, **kwargs: object) -> None:
    command.downgrade(alembic_config(**kwargs), revision)  # type: ignore[arg-type]


def _ini_path() -> Path:
    # The image runs from /app, which holds alembic.ini and migrations/;
    # in a checkout, fall back to the repo root.
    for candidate in (Path.cwd() / "alembic.ini", _REPO_ROOT / "alembic.ini"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("alembic.ini not found in the working directory or the repo root")
