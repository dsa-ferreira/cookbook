"""One SQLAlchemy session per request.

Opened lazily on ``flask.g`` and closed at app-context teardown; a session
that was not committed is rolled back. Services receive the plain
``Session`` and never import Flask.
"""

from __future__ import annotations

from flask import Flask, current_app, g
from sqlalchemy.orm import Session, sessionmaker

SESSION_FACTORY_KEY = "cookbook.session_factory"


def init_sessions(app: Flask, factory: sessionmaker[Session]) -> None:
    app.extensions[SESSION_FACTORY_KEY] = factory
    app.teardown_appcontext(close_session)


def get_session() -> Session:
    """The current request's session, opened on first use."""
    if "db_session" not in g:
        factory: sessionmaker[Session] = current_app.extensions[SESSION_FACTORY_KEY]
        g.db_session = factory()
    return g.db_session


def close_session(_exc: BaseException | None = None) -> None:
    session: Session | None = g.pop("db_session", None)
    if session is not None:
        session.close()
