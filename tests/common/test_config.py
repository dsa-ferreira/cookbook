import hashlib
import json

import pytest

from cookbook.common.config import ConfigError, load_settings

HASH_A = hashlib.sha256(b"key-a").hexdigest()
HASH_B = hashlib.sha256(b"key-b").hexdigest()
DB = "postgresql://cookbook:cookbook@localhost:5432/cookbook"


def env(api_keys: str) -> dict[str, str]:
    return {"COOKBOOK_DATABASE_URL": DB, "COOKBOOK_API_KEYS": api_keys}


def test_valid_config() -> None:
    settings = load_settings(env(json.dumps({"diogo": HASH_A, "partner": HASH_B.upper()})))
    assert settings.api_keys == {"diogo": HASH_A, "partner": HASH_B}
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_empty_api_keys_rejected() -> None:
    with pytest.raises(ConfigError) as exc:
        load_settings(env("{}"))
    assert any("COOKBOOK_API_KEYS" in p and "no API keys" in p for p in exc.value.problems)


def test_missing_api_keys_rejected() -> None:
    with pytest.raises(ConfigError) as exc:
        load_settings({"COOKBOOK_DATABASE_URL": DB})
    assert "COOKBOOK_API_KEYS is required but not set" in exc.value.problems


@pytest.mark.parametrize(
    "digest",
    ["abc", "z" * 64, HASH_A + "0", "not-a-key-at-all"],
)
def test_malformed_hash_rejected(digest: str) -> None:
    with pytest.raises(ConfigError) as exc:
        load_settings(env(json.dumps({"diogo": digest})))
    message = str(exc.value)
    assert "'diogo'" in message
    assert digest not in message


def test_non_json_rejected() -> None:
    with pytest.raises(ConfigError) as exc:
        load_settings(env("diogo=abc"))
    assert any("JSON object" in p for p in exc.value.problems)
