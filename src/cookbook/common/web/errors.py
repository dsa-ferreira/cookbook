"""JSON error responses: ``{"error": code, "message": ..., "details"?: [...]}``."""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import Flask, Response, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from cookbook.common.errors import InvalidInputError, NotFoundError

log = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str, details: list[dict[str, Any]] | None = None
) -> tuple[Response, int]:
    body: dict[str, Any] = {"error": code, "message": message}
    if details is not None:
        body["details"] = details
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def _validation(exc: ValidationError):
        # Round-trip through JSON: ctx may hold exception objects.
        details = json.loads(exc.json(include_url=False, include_input=False))
        return error_response(422, "validation_error", "request validation failed", details)

    @app.errorhandler(InvalidInputError)
    def _invalid(exc: InvalidInputError):
        return error_response(422, "validation_error", exc.message, exc.details)

    @app.errorhandler(NotFoundError)
    def _not_found(exc: NotFoundError):
        return error_response(404, "not_found", str(exc) or "not found")

    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        status = exc.code or 500
        if status == 404:
            return error_response(404, "not_found", "no such resource")
        if status == 401:
            return error_response(401, "unauthorized", "a valid API key is required")
        code = (exc.name or "error").lower().replace(" ", "_")
        return error_response(status, code, exc.description or exc.name or "error")

    @app.errorhandler(Exception)
    def _internal(exc: Exception):
        log.exception("unhandled error")
        return error_response(500, "internal_error", "internal server error")
