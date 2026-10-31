"""Bearer API-key check and per-request access logging.

Keys are configured as ``{name: sha256_hex(key)}``. The presented key is
hashed and compared against every configured hash in constant time. Only
the key name is ever stored or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from flask import Flask, Response, g, request

from cookbook.common.config import Settings
from cookbook.common.web.errors import error_response

access_log = logging.getLogger("cookbook.access")

EXEMPT_ENDPOINTS = frozenset({"health.healthz"})


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def match_key(token: str, api_keys: dict[str, str]) -> str | None:
    """Return the name of the key whose hash matches ``token``, if any."""
    digest = hash_key(token)
    matched: str | None = None
    # No early exit, so timing doesn't reveal which entry matched.
    for name, expected in api_keys.items():
        if hmac.compare_digest(digest, expected):
            matched = name
    return matched


def init_auth(app: Flask, settings: Settings) -> None:
    @app.before_request
    def _require_key():
        g.api_key_name = None
        if request.endpoint in EXEMPT_ENDPOINTS:
            return None
        token = _bearer_token()
        name = match_key(token, settings.api_keys) if token else None
        if name is None:
            return error_response(401, "unauthorized", "a valid API key is required")
        g.api_key_name = name
        return None

    @app.after_request
    def _log_request(response: Response) -> Response:
        if request.endpoint not in EXEMPT_ENDPOINTS:
            access_log.info(
                "%s %s %s key=%s",
                request.method,
                request.full_path.rstrip("?"),
                response.status_code,
                g.get("api_key_name") or "-",
            )
        return response
