import hashlib
import json

import pytest
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from cookbook.app import create_app
from cookbook.cli import main
from cookbook.common.config import load_settings
from tests.conftest import rpc


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

    with TestClient(app) as client:
        good = rpc(client, "tools/list", headers={"Authorization": f"Bearer {key}"})
        assert good.status_code == 200
        bad = rpc(client, "tools/list", headers={"Authorization": "Bearer nope"})
        assert bad.status_code == 401
