"""Flask application factory: shared web glue plus each domain's blueprint."""

from __future__ import annotations

import logging

from flask import Flask
from sqlalchemy.orm import Session, sessionmaker

from cookbook.common import db
from cookbook.common.auth import init_auth
from cookbook.common.config import Settings, get_settings
from cookbook.common.web.errors import register_error_handlers
from cookbook.common.web.health import bp as health_bp
from cookbook.common.web.session import init_sessions
from cookbook.ingredients.api import bp as ingredients_bp
from cookbook.recipes.api import bp as recipes_bp
from cookbook.units.api import bp as units_bp

SETTINGS_KEY = "cookbook.settings"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> Flask:
    """Build the app. Raises ``ConfigError`` if the environment is invalid."""
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    app = Flask(__name__)
    app.json.sort_keys = False  # type: ignore[attr-defined]
    app.extensions[SETTINGS_KEY] = settings

    if session_factory is None:
        session_factory = db.make_session_factory(db.make_engine(settings.database_url))
    init_sessions(app, session_factory)

    register_error_handlers(app)
    init_auth(app, settings)
    for bp in (health_bp, units_bp, ingredients_bp, recipes_bp):
        app.register_blueprint(bp)
    return app
