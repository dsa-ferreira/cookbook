"""Startup configuration from ``COOKBOOK_*`` environment variables.

Everything is validated once at startup. Errors are collected into a
``ConfigError`` whose messages name the offending variable or key name but
never include a key hash or the database password.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "COOKBOOK_"

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class ConfigError(Exception):
    """Invalid configuration. ``problems`` are safe to print."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("invalid configuration:\n" + "\n".join(f"  - {p}" for p in problems))


class DatabaseSettings(BaseSettings):
    """Only what migrations need, so ``cookbook migrate`` runs without API keys."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    database_url: str = Field(min_length=1)

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, value: str) -> str:
        # Accept the libpq-style scheme and point SQLAlchemy at psycopg 3.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


class Settings(DatabaseSettings):
    """All cookbook settings. Read with :func:`load_settings`."""

    # Key name -> SHA-256 hex digest of the key. Never the key itself.
    api_keys: dict[str, str]

    @field_validator("api_keys", mode="before")
    @classmethod
    def _decode_json(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError('must be a JSON object like {"name": "<sha256 hex>"}') from None
        return value

    @field_validator("api_keys")
    @classmethod
    def _valid_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("no API keys configured; the service refuses to start open")
        problems: list[str] = []
        normalized: dict[str, str] = {}
        for name, digest in value.items():
            if not name.strip():
                problems.append("a key has an empty name")
                continue
            digest = digest.strip().lower()
            if not _SHA256_HEX.fullmatch(digest):
                problems.append(f"key {name!r} is not a 64-character hex SHA-256 digest")
                continue
            normalized[name] = digest
        if problems:
            raise ValueError("; ".join(problems))
        return normalized


def _describe(error: Mapping[str, object]) -> str:
    """Turn one pydantic error into a message without its input value."""
    loc = error.get("loc") or ()
    field = str(loc[0]) if isinstance(loc, tuple) and loc else ""
    var = f"{ENV_PREFIX}{field.upper()}" if field else "configuration"
    if error.get("type") == "missing":
        return f"{var} is required but not set"
    msg = str(error.get("msg", "invalid value")).removeprefix("Value error, ")
    return f"{var}: {msg}" if field else msg


def load_settings[S: DatabaseSettings](
    env: Mapping[str, str] | None = None, model: type[S] = Settings
) -> S:
    """Load and validate ``model`` from ``env`` (default: the process environment).

    Raises :class:`ConfigError` with secret-free messages on any problem.
    """
    source = os.environ if env is None else env
    values = {
        k[len(ENV_PREFIX) :].lower(): v
        for k, v in source.items()
        if k.upper().startswith(ENV_PREFIX)
    }
    try:
        # model_validate skips pydantic-settings' own sources, so the result
        # depends only on ``source``.
        return model.model_validate(values)
    except ValidationError as exc:
        problems = [_describe(e) for e in exc.errors(include_input=False, include_url=False)]
        raise ConfigError(problems) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded on first use."""
    return load_settings()
