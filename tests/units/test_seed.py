from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cookbook.units.models import Unit

EXPECTED = {
    "g": ("mass", 1),
    "kg": ("mass", 1000),
    "ml": ("volume", 1),
    "l": ("volume", 1000),
    "tsp": ("volume", 5),
    "tbsp": ("volume", 15),
    "cup": ("volume", 240),
    "piece": ("count", 1),
    "clove": ("count", 1),
    "can": ("count", 1),
    "pinch": ("count", 1),
}


def test_seeded_units(db_session: Session) -> None:
    rows = db_session.scalars(select(Unit)).all()
    assert {u.code: (u.dimension, u.to_base) for u in rows} == {
        code: (dim, Decimal(factor)) for code, (dim, factor) in EXPECTED.items()
    }
