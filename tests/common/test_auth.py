import hashlib
import json
import logging

import pytest
from flask import Blueprint, Flask
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from cookbook.app import create_app
from cookbook.common.config import load_settings
from cookbook.recipes.models import Recipe
from tests.conftest import TEST_KEY, TEST_KEY_HASH, TEST_KEY_NAME

OTHER_KEY = "other-key-zyxwvutsrqponmlkjihgfedcba98765"


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def build_app(database_url: str, factory: sessionmaker[Session], keys: dict[str, str]) -> Flask:
    settings = load_settings(
        {"COOKBOOK_DATABASE_URL": database_url, "COOKBOOK_API_KEYS": json.dumps(keys)}
    )
    app = create_app(settings, session_factory=factory)

    bp = Blueprint("probe", __name__)

    @bp.get("/probe")
    def probe():
        return {"ok": True}

    app.register_blueprint(bp)
    return app


@pytest.fixture
def probe_app(database_url: str, session_factory: sessionmaker[Session]) -> Flask:
    return build_app(database_url, session_factory, {TEST_KEY_NAME: TEST_KEY_HASH})


def test_valid_key(probe_app: Flask) -> None:
    resp = probe_app.test_client().get("/probe", headers=bearer(TEST_KEY))
    assert resp.status_code == 200


def test_scheme_is_case_insensitive(probe_app: Flask) -> None:
    resp = probe_app.test_client().get("/probe", headers={"Authorization": f"bearer {TEST_KEY}"})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": f"Basic {TEST_KEY}"},
        {"Authorization": TEST_KEY},
        bearer("not-a-configured-key"),
        bearer(TEST_KEY_HASH),
    ],
    ids=["missing", "empty", "no-token", "wrong-scheme", "no-scheme", "unknown", "hash-as-key"],
)
def test_missing_malformed_or_unknown_key(probe_app: Flask, headers: dict[str, str]) -> None:
    resp = probe_app.test_client().get("/probe", headers=headers)
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "unauthorized"


def test_unknown_route_without_key_is_401(probe_app: Flask) -> None:
    assert probe_app.test_client().get("/recipes/1").status_code == 401


def test_unknown_key_creates_no_recipe(probe_app: Flask, db_session: Session) -> None:
    resp = probe_app.test_client().post(
        "/recipes", json={"name": "x"}, headers=bearer("not-a-configured-key")
    )
    assert resp.status_code == 401
    assert db_session.scalar(select(func.count()).select_from(Recipe)) == 0


def test_healthz_needs_no_key(probe_app: Flask) -> None:
    client = probe_app.test_client()
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz", headers=bearer("garbage")).status_code == 200


def test_revoking_one_key(database_url: str, session_factory: sessionmaker[Session]) -> None:
    other_hash = hashlib.sha256(OTHER_KEY.encode()).hexdigest()
    before = build_app(
        database_url, session_factory, {TEST_KEY_NAME: TEST_KEY_HASH, "other": other_hash}
    ).test_client()
    assert before.get("/probe", headers=bearer(OTHER_KEY)).status_code == 200

    # "Restart" with the other entry removed.
    after = build_app(database_url, session_factory, {TEST_KEY_NAME: TEST_KEY_HASH}).test_client()
    assert after.get("/probe", headers=bearer(OTHER_KEY)).status_code == 401
    assert after.get("/probe", headers=bearer(TEST_KEY)).status_code == 200


def test_key_name_is_logged_but_not_the_key(
    database_url: str, session_factory: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    diogo_key = "diogo-key-abcdefghijklmnopqrstuvwxyz012345"
    diogo_hash = hashlib.sha256(diogo_key.encode()).hexdigest()
    app = build_app(database_url, session_factory, {"diogo": diogo_hash})
    with caplog.at_level(logging.DEBUG):
        app.test_client().get("/probe", headers=bearer(diogo_key))
        app.test_client().get("/probe", headers=bearer("wrong-key-value"))

    access = [r.getMessage() for r in caplog.records if r.name == "cookbook.access"]
    assert any("key=diogo" in line and "200" in line for line in access)
    everything = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
    for secret in (diogo_key, diogo_hash, "wrong-key-value"):
        assert secret not in everything
