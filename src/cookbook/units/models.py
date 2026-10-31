from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from cookbook.common.db import Base


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        CheckConstraint("dimension IN ('mass', 'volume', 'count')", name="dimension"),
        CheckConstraint("to_base > 0", name="to_base_positive"),
    )

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    dimension: Mapped[str] = mapped_column(Text)
    to_base: Mapped[Decimal] = mapped_column(Numeric)
