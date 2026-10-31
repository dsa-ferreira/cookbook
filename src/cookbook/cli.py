"""``cookbook`` command line: ``apikey NAME`` and ``migrate``."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from collections.abc import Sequence

from cookbook.common.auth import hash_key
from cookbook.common.config import ConfigError, DatabaseSettings, load_settings


def cmd_apikey(name: str) -> int:
    name = name.strip()
    if not name:
        print("cookbook: key name must not be empty", file=sys.stderr)
        return 2
    key = secrets.token_urlsafe(32)
    print(f"API key for {name!r} (shown once; store it now):")
    print(key)
    print()
    print("Add this entry to the COOKBOOK_API_KEYS JSON object:")
    print(f"{json.dumps(name)}: {json.dumps(hash_key(key))}")
    return 0


def cmd_migrate() -> int:
    from cookbook.common import migrate

    try:
        settings = load_settings(model=DatabaseSettings)
    except ConfigError as exc:
        print(f"cookbook: {exc}", file=sys.stderr)
        return 2
    migrate.upgrade(url=settings.database_url)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookbook")
    sub = parser.add_subparsers(dest="command", required=True)
    apikey = sub.add_parser("apikey", help="generate a new API key and its config entry")
    apikey.add_argument("name", help="key name, e.g. the person who will use it")
    sub.add_parser("migrate", help="apply database migrations (alembic upgrade head)")
    args = parser.parse_args(argv)

    if args.command == "apikey":
        return cmd_apikey(args.name)
    return cmd_migrate()


def run() -> None:
    """Console-script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    run()
