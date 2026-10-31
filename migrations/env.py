"""Alembic environment.

The database comes from, in order: a connection passed by the caller in
``config.attributes["connection"]`` (tests), ``sqlalchemy.url`` set on the
config, or ``COOKBOOK_DATABASE_URL``.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.engine import create_engine

# The domain model imports register every table on Base.metadata, so
# autogenerate and `alembic check` see the whole schema. Add new domains here.
import cookbook.ingredients.models  # noqa: F401
import cookbook.recipes.models  # noqa: F401
import cookbook.units.models  # noqa: F401
from cookbook.common.config import DatabaseSettings, load_settings
from cookbook.common.db import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return load_settings(model=DatabaseSettings).database_url


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        _run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
