"""Shared fixtures.

One Postgres container per test session (testcontainers) with all
migrations applied. Every test runs inside an outer transaction on a single
connection that is rolled back afterwards; sessions join it through
savepoints, so service code can commit freely.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cookbook.common import migrate
from cookbook.common.config import load_settings

# Ryuk (the reaper container) needs a privileged socket that rootless podman
# doesn't give it; containers are stopped by the fixture instead.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

TEST_KEY_NAME = "tester"
TEST_KEY = "test-key-0123456789abcdefghijklmnopqrstuv"
TEST_KEY_HASH = hashlib.sha256(TEST_KEY.encode()).hexdigest()
AUTH = {"Authorization": f"Bearer {TEST_KEY}"}


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("docker.io/library/postgres:17", driver="psycopg") as pg:
        url = pg.get_connection_url()
        migrate.upgrade(url=url)
        yield url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as conn:
        outer = conn.begin()
        try:
            yield conn
        finally:
            outer.rollback()


@pytest.fixture
def session_factory(connection: Connection) -> sessionmaker[Session]:
    return sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def settings(database_url: str):
    return load_settings(
        {
            "COOKBOOK_DATABASE_URL": database_url,
            "COOKBOOK_API_KEYS": json.dumps({TEST_KEY_NAME: TEST_KEY_HASH}),
        }
    )


@pytest.fixture
def app(settings, session_factory: sessionmaker[Session]) -> Flask:
    # Imported here so database-only tests don't load every domain's API.
    from cookbook.app import create_app

    app = create_app(settings, session_factory=session_factory)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Test client that sends the test key on every request."""
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = AUTH["Authorization"]
    return client


@pytest.fixture
def anon_client(app: Flask) -> FlaskClient:
    return app.test_client()
