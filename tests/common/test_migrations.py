"""Round-trip the migrations on a scratch database in the shared container."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url

from cookbook.common import migrate

TABLES = {"units", "ingredients", "recipes", "recipe_steps", "recipe_ingredients"}


@pytest.fixture
def scratch_url(engine: Engine) -> Iterator[str]:
    name = "cookbook_migrations_test"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    url = make_url(engine.url).set(database=name)
    yield url.render_as_string(hide_password=False)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))


def test_upgrade_and_downgrade(scratch_url: str) -> None:
    migrate.upgrade(url=scratch_url)
    scratch = create_engine(scratch_url)
    try:
        assert set(inspect(scratch).get_table_names()) >= TABLES
        migrate.downgrade("base", url=scratch_url)
        assert not TABLES & set(inspect(scratch).get_table_names())
        migrate.upgrade(url=scratch_url)
        assert set(inspect(scratch).get_table_names()) >= TABLES
    finally:
        scratch.dispose()
