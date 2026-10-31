"""Declarative base, engine and session factory. Framework-free.

Each domain defines its tables in its own ``models`` module on top of
:class:`Base`. This module knows nothing about the domains; whoever needs the
full metadata (Alembic's ``migrations/env.py``) imports their models.
"""

from __future__ import annotations

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Deterministic constraint names, so migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False so objects stay readable after the service commits.
    return sessionmaker(bind=engine, expire_on_commit=False)
