from starlette.testclient import TestClient

from tests.conftest import initialize_params, rpc


def test_healthz_needs_no_key(anon_http: TestClient) -> None:
    resp = anon_http.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_initialize_without_key_is_401(anon_http: TestClient) -> None:
    resp = rpc(anon_http, "initialize", initialize_params())
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json()["error"] == "unauthorized"


def test_initialize_returns_instructions(http: TestClient) -> None:
    resp = rpc(http, "initialize", initialize_params(), follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    instructions = resp.json()["result"]["instructions"]
    for phrase in ("search_ingredients", "list_units", "whole-recipe totals"):
        assert phrase in instructions


def test_tools_list_and_call_need_no_session(http: TestClient) -> None:
    listed = rpc(http, "tools/list")
    assert listed.status_code == 200
    assert "mcp-session-id" not in listed.headers
    assert len(listed.json()["result"]["tools"]) == 7

    called = rpc(http, "tools/call", {"name": "list_recipes", "arguments": {}})
    assert called.status_code == 200
    result = called.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["total"] == 0


def test_post_mcp_does_not_redirect(http: TestClient) -> None:
    resp = rpc(http, "tools/list", follow_redirects=False)
    assert resp.status_code == 200
    assert not resp.is_redirect


def test_former_rest_paths_are_gone(http: TestClient) -> None:
    for path in ("/recipes", "/recipes/1", "/ingredients", "/units"):
        assert http.get(path).status_code == 404, path
