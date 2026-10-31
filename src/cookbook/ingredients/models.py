from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Identity, Text
from sqlalchemy.orm import Mapped, mapped_column

from cookbook.common.db import Base


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        CheckConstraint("name <> ''", name="name_not_empty"),
        # Names are normalized by the app; this catches writes that bypass it.
        CheckConstraint(
            r"name = lower(name) AND name = btrim(regexp_replace(name, '\s+', ' ', 'g'))",
            name="name_normalized",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
