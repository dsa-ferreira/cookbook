"""Auth on the real app; the middleware's own cases are in test_auth_middleware."""

import hashlib
import json
import logging

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from cookbook.app import create_app
from cookbook.common.config import load_settings
from cookbook.recipes.models import Recipe
from tests.conftest import initialize_params, rpc
from tests.recipes.factories import recipe_doc


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_valid_key_calls_a_tool(http: TestClient) -> None:
    resp = rpc(http, "tools/call", {"name": "list_recipes", "arguments": {}})
    assert resp.status_code == 200
    assert resp.json()["result"]["isError"] is False


def test_missing_key_is_401(anon_http: TestClient) -> None:
    assert rpc(anon_http, "initialize", initialize_params()).status_code == 401


def test_unknown_key_creates_no_recipe(anon_http: TestClient, db_session: Session) -> None:
    params = {"name": "create_recipe", "arguments": {"recipe": recipe_doc()}}
    resp = rpc(anon_http, "tools/call", params, headers=bearer("not-a-configured-key"))
    assert resp.status_code == 401
    assert db_session.scalar(select(func.count()).select_from(Recipe)) == 0


def test_unknown_path_without_key_is_401(anon_http: TestClient) -> None:
    assert anon_http.get("/recipes/1").status_code == 401


def test_tool_call_logs_tool_and_key_name_but_not_the_key(
    database_url: str, session_factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    key = "openwebui-key-abcdefghijklmnopqrstuvwxyz0123"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    settings = load_settings(
        {
            "COOKBOOK_DATABASE_URL": database_url,
            "COOKBOOK_API_KEYS": json.dumps({"openwebui": key_hash}),
        }
    )
    app = create_app(settings, session_factory=session_factory)
    with TestClient(app, headers=bearer(key)) as client, caplog.at_level(logging.INFO):
        rpc(client, "tools/call", {"name": "delete_recipe", "arguments": {"recipe_id": 1}})

    access = [r.getMessage() for r in caplog.records if r.name == "cookbook.access"]
    assert access == ["POST /mcp 200 key=openwebui tool=delete_recipe"]
    everything = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
    assert key not in everything
    assert key_hash not in everything
