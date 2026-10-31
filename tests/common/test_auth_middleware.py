import hashlib
import json
import logging

import pytest
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from cookbook.common.auth import MAX_PEEK_BYTES, ApiKeyMiddleware

KEY = "diogo-key-abcdefghijklmnopqrstuvwxyz012345"
KEY_HASH = hashlib.sha256(KEY.encode()).hexdigest()
OTHER_KEY = "other-key-zyxwvutsrqponmlkjihgfedcba98765"
OTHER_HASH = hashlib.sha256(OTHER_KEY.encode()).hexdigest()


async def echo_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Answers with the key name it saw and the request body it received."""
    body = b""
    more = True
    while more:
        message = await receive()
        body += message.get("body", b"")
        more = message.get("more_body", False)
    payload = json.dumps(
        {"key": scope.get("state", {}).get("api_key_name"), "body": body.decode()}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": payload})


def client(keys: dict[str, str] | None = None) -> TestClient:
    return TestClient(ApiKeyMiddleware(echo_app, keys or {"diogo": KEY_HASH}))


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def access_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "cookbook.access"]


def test_valid_key_passes_with_key_name() -> None:
    resp = client().post("/mcp", headers=bearer(KEY), content=b'{"a": 1}')
    assert resp.status_code == 200
    assert resp.json() == {"key": "diogo", "body": '{"a": 1}'}


def test_scheme_is_case_insensitive() -> None:
    assert client().get("/x", headers={"Authorization": f"bearer {KEY}"}).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": f"Basic {KEY}"},
        {"Authorization": KEY},
        bearer("not-a-configured-key"),
        bearer(KEY_HASH),
    ],
    ids=["missing", "empty", "no-token", "wrong-scheme", "no-scheme", "unknown", "hash-as-key"],
)
def test_missing_malformed_or_unknown_key(headers: dict[str, str]) -> None:
    resp = client().post("/mcp", headers=headers, content=b"{}")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json() == {"error": "unauthorized", "message": "a valid API key is required"}


def test_healthz_is_exempt() -> None:
    c = client()
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz", headers=bearer("garbage")).status_code == 200


def test_revoking_one_key() -> None:
    before = client({"diogo": KEY_HASH, "other": OTHER_HASH})
    assert before.get("/x", headers=bearer(OTHER_KEY)).status_code == 200
    # "Restart" with the other entry removed.
    after = client({"diogo": KEY_HASH})
    assert after.get("/x", headers=bearer(OTHER_KEY)).status_code == 401
    assert after.get("/x", headers=bearer(KEY)).status_code == 200


def test_log_has_key_name_but_never_the_key(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        client().get("/x?limit=2", headers=bearer(KEY))
        client().get("/x", headers=bearer("wrong-key-value"))
        client().get("/healthz")

    lines = access_lines(caplog)
    assert lines == ["GET /x?limit=2 200 key=diogo", "GET /x 401 key=-"]
    everything = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
    for secret in (KEY, KEY_HASH, "wrong-key-value"):
        assert secret not in everything


def test_tool_call_is_logged_with_tool_and_key(caplog: pytest.LogCaptureFixture) -> None:
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete_recipe"}}
    with caplog.at_level(logging.INFO):
        resp = client({"openwebui": KEY_HASH}).post("/mcp", headers=bearer(KEY), json=call)
    # The app still receives the body the middleware read.
    assert json.loads(resp.json()["body"]) == call
    assert access_lines(caplog) == ["POST /mcp 200 key=openwebui tool=delete_recipe"]
    assert KEY not in caplog.text


@pytest.mark.parametrize(
    ("body", "suffix"),
    [
        (b'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}', ""),
        (b"not json", ""),
        (b'{"method": "tools/call", "params": {"name": "evil\\nkey=admin"}}', " tool=?"),
        (b'{"method": "tools/call", "params": "nope"}', " tool=?"),
    ],
    ids=["not-a-call", "not-json", "injection", "bad-params"],
)
def test_tool_name_is_only_logged_when_safe(
    caplog: pytest.LogCaptureFixture, body: bytes, suffix: str
) -> None:
    with caplog.at_level(logging.INFO):
        client().post("/mcp", headers=bearer(KEY), content=body)
    assert access_lines(caplog) == [f"POST /mcp 200 key=diogo{suffix}"]


def test_oversized_body_is_passed_on_unparsed(caplog: pytest.LogCaptureFixture) -> None:
    big = json.dumps(
        {"method": "tools/call", "params": {"name": "x", "pad": "a" * (MAX_PEEK_BYTES + 10)}}
    )
    with caplog.at_level(logging.INFO):
        resp = client().post("/mcp", headers=bearer(KEY), content=big.encode())
    assert resp.status_code == 200
    assert resp.json()["body"] == big
    assert access_lines(caplog) == ["POST /mcp 200 key=diogo"]
