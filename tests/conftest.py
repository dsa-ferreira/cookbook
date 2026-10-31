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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cookbook.common import migrate
from cookbook.common.config import load_settings

if TYPE_CHECKING:
    from starlette.testclient import TestClient

# Ryuk (the reaper container) needs a privileged socket that rootless podman
# doesn't give it; containers are stopped by the fixture instead.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

TEST_KEY_NAME = "tester"
TEST_KEY = "test-key-0123456789abcdefghijklmnopqrstuv"
TEST_KEY_HASH = hashlib.sha256(TEST_KEY.encode()).hexdigest()
AUTH = {"Authorization": f"Bearer {TEST_KEY}"}


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


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
def app(settings, session_factory: sessionmaker[Session]):
    """The ASGI app, auth middleware included, on the rollback-per-test database."""
    # Imported here so database-only tests don't load every domain's tools.
    from cookbook.app import create_app

    return create_app(settings, session_factory=session_factory)


def _test_client(app, headers: dict[str, str]) -> Iterator[TestClient]:
    from starlette.testclient import TestClient

    # As a context manager, so the app's lifespan (the MCP session manager) runs.
    with TestClient(app, headers=headers) as client:
        yield client


@pytest.fixture
def http(app) -> Iterator[TestClient]:
    """HTTP client that sends the test key on every request."""
    yield from _test_client(app, AUTH)


@pytest.fixture
def anon_http(app) -> Iterator[TestClient]:
    yield from _test_client(app, {})


MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def rpc(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
):
    """POST one JSON-RPC request to ``/mcp``."""
    message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", json=message, headers=MCP_HEADERS | (headers or {}), **kwargs)


def initialize_params() -> dict[str, Any]:
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "tests", "version": "0"},
    }


@pytest.fixture
async def mcp_client(session_factory: sessionmaker[Session]) -> AsyncIterator[Client]:
    """An MCP client connected in-process to the cookbook server.

    It skips HTTP and so the auth middleware; auth is tested through ``http``.
    """
    from cookbook.app import build_server

    async with Client(build_server(session_factory)) as client:
        yield client


type Call = Callable[..., Awaitable[tuple[bool, Any]]]


@pytest.fixture
def call(mcp_client: Client) -> Call:
    """``await call(name, **args)`` -> ``(is_error, structured_content)``."""

    async def _call(name: str, **arguments: Any) -> tuple[bool, Any]:
        result = await mcp_client.call_tool(name, arguments)
        return result.is_error, result.structured_content

    return _call
