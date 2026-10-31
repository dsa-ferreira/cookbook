"""Liveness endpoint. Unauthenticated, and never touches recipe data."""

from flask import Blueprint

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
