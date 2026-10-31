from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from cookbook.units.models import Unit
from cookbook.units.schemas import UnitOut


def list_units(session: Session) -> list[UnitOut]:
    rows = session.scalars(select(Unit).order_by(Unit.dimension, Unit.to_base, Unit.code))
    return [UnitOut.model_validate(u) for u in rows]


def unknown_codes(session: Session, codes: Iterable[str]) -> list[str]:
    """The given unit codes that are not in the vocabulary, sorted."""
    wanted = set(codes)
    if not wanted:
        return []
    known = set(session.scalars(select(Unit.code).where(Unit.code.in_(wanted))))
    return sorted(wanted - known)
