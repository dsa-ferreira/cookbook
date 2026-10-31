"""Bearer API-key check and per-request access logging, as ASGI middleware.

Keys are configured as ``{name: sha256_hex(key)}``. The presented key is
hashed and compared against every configured hash in constant time. Only
the key name is ever stored or logged.

Pure ASGI rather than Starlette's ``BaseHTTPMiddleware``, which has known
problems with streaming responses and background tasks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from collections.abc import Mapping

from starlette.types import ASGIApp, Message, Receive, Scope, Send

access_log = logging.getLogger("cookbook.access")

EXEMPT_PATHS = frozenset({"/healthz"})

# Bodies are read to find the tool name; past this size (the SDK's own
# request limit) they are passed on unparsed.
MAX_PEEK_BYTES = 4 * 1024 * 1024
# The tool name comes from the client; only log it if it looks like one.
_TOOL_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")

_UNAUTHORIZED = json.dumps(
    {"error": "unauthorized", "message": "a valid API key is required"}
).encode()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def match_key(token: str, api_keys: dict[str, str]) -> str | None:
    """Return the name of the key whose hash matches ``token``, if any."""
    digest = hash_key(token)
    matched: str | None = None
    # No early exit, so timing doesn't reveal which entry matched.
    for name, expected in api_keys.items():
        if hmac.compare_digest(digest, expected):
            matched = name
    return matched


class ApiKeyMiddleware:
    """Require a configured bearer key on every HTTP path except ``/healthz``.

    On success the key name is put in ``scope["state"]["api_key_name"]``.
    One ``cookbook.access`` line is logged per request, with the tool name
    for ``tools/call`` requests.
    """

    def __init__(self, app: ASGIApp, api_keys: dict[str, str]) -> None:
        self.app = app
        self.api_keys = api_keys

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan" or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        token = _bearer_token(scope)
        name = match_key(token, self.api_keys) if token else None
        if name is None:
            await self._unauthorized(scope, send)
            return
        scope.setdefault("state", {})["api_key_name"] = name

        tools: list[str] = []
        if scope["type"] == "http" and scope.get("method") == "POST":
            body, complete, receive = await _peek_body(receive)
            if complete:
                tools = _tool_names(body)

        status = 0

        async def send_and_record(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_record)
        finally:
            self._log(scope, status or 500, name, tools)

    async def _unauthorized(self, scope: Scope, send: Send) -> None:
        if scope["type"] == "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(_UNAUTHORIZED)).encode()),
                        (b"www-authenticate", b"Bearer"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": _UNAUTHORIZED})
        else:
            await send({"type": "websocket.close", "code": 1008})
        self._log(scope, 401, None, [])

    @staticmethod
    def _log(scope: Scope, status: int, key_name: str | None, tools: list[str]) -> None:
        path = scope.get("path", "")
        query = scope.get("query_string", b"").decode("latin-1")
        suffix = "".join(f" tool={t}" for t in tools)
        access_log.info(
            "%s %s %s key=%s%s",
            scope.get("method", "WS"),
            f"{path}?{query}" if query else path,
            status,
            key_name or "-",
            suffix,
        )


def _bearer_token(scope: Scope) -> str | None:
    header = ""
    for key, value in scope.get("headers", ()):
        if key == b"authorization":
            header = value.decode("latin-1")
            break
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _tool_names(body: bytes) -> list[str]:
    """Names of the tools called by a JSON-RPC message (or batch) in ``body``."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    messages = data if isinstance(data, list) else [data]
    names = []
    for msg in messages:
        if not isinstance(msg, Mapping) or msg.get("method") != "tools/call":
            continue
        params = msg.get("params")
        name = params.get("name") if isinstance(params, Mapping) else None
        names.append(name if isinstance(name, str) and _TOOL_NAME.fullmatch(name) else "?")
    return names


async def _peek_body(receive: Receive) -> tuple[bytes, bool, Receive]:
    """Read the body up to ``MAX_PEEK_BYTES``; return it and a ``receive`` that replays it.

    The flag says whether the whole body was read and is small enough to parse.
    """
    chunks: list[bytes] = []
    size = 0
    more = True
    pending: Message | None = None  # a non-body message (disconnect) to pass on
    while more and size <= MAX_PEEK_BYTES:
        message = await receive()
        if message["type"] != "http.request":
            pending = message
            break
        chunk = message.get("body", b"")
        chunks.append(chunk)
        size += len(chunk)
        more = message.get("more_body", False)
    body = b"".join(chunks)
    replayed = False

    async def replay() -> Message:
        nonlocal replayed, pending
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": body, "more_body": more}
        if pending is not None:
            message, pending = pending, None
            return message
        return await receive()

    return body, not more and pending is None and size <= MAX_PEEK_BYTES, replay
