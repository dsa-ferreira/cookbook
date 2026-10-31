import hashlib
import json

import pytest
from flask import Blueprint
from sqlalchemy.orm import Session, sessionmaker

from cookbook.app import create_app
from cookbook.cli import main
from cookbook.common.config import load_settings


def run_apikey(name: str, capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    assert main(["apikey", name]) == 0
    lines = capsys.readouterr().out.splitlines()
    key = lines[1]
    entry = json.loads("{" + lines[-1] + "}")
    assert list(entry) == [name]
    return key, entry[name]


def test_apikey_prints_key_and_its_sha256(capsys: pytest.CaptureFixture[str]) -> None:
    key, digest = run_apikey("diogo", capsys)
    assert len(key) >= 40
    assert digest == hashlib.sha256(key.encode()).hexdigest()


def test_apikey_keys_are_unique(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_apikey("a", capsys)[0] != run_apikey("a", capsys)[0]


def test_generated_key_authenticates(
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    session_factory: sessionmaker[Session],
) -> None:
    key, digest = run_apikey("diogo", capsys)
    settings = load_settings(
        {"COOKBOOK_DATABASE_URL": database_url, "COOKBOOK_API_KEYS": json.dumps({"diogo": digest})}
    )
    app = create_app(settings, session_factory=session_factory)
    bp = Blueprint("probe", __name__)
    bp.add_url_rule("/probe", view_func=lambda: {"ok": True})
    app.register_blueprint(bp)

    client = app.test_client()
    assert client.get("/probe", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert client.get("/probe", headers={"Authorization": "Bearer nope"}).status_code == 401
