"""Recipe tables.

Per-serving macros and total time are stored generated columns, read-only
from the ORM's point of view.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cookbook.common.db import Base
from cookbook.ingredients.models import Ingredient
from cookbook.units.models import Unit

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")


def _per_serving(column: str) -> Mapped[Decimal]:
    # NULLIF: generated columns are computed before CHECKs run, so servings = 0
    # must not divide by zero; ck_recipes_servings_positive rejects the row.
    # Nullable for the same reason; it is never null for a stored row.
    return mapped_column(
        Numeric,
        Computed(f"round({column} / NULLIF(servings, 0), 1)", persisted=True),
        nullable=True,
    )


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("name <> ''", name="name_not_empty"),
        CheckConstraint("servings > 0", name="servings_positive"),
        CheckConstraint("prep_time_min >= 0", name="prep_time_non_negative"),
        CheckConstraint("cook_time_min >= 0", name="cook_time_non_negative"),
        *(CheckConstraint(f"{m} >= 0", name=f"{m}_non_negative") for m in MACROS),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    servings: Mapped[int] = mapped_column(Integer)
    prep_time_min: Mapped[int | None] = mapped_column(Integer)
    cook_time_min: Mapped[int | None] = mapped_column(Integer)

    kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1))
    protein_g: Mapped[Decimal] = mapped_column(Numeric(7, 1))
    carbs_g: Mapped[Decimal] = mapped_column(Numeric(7, 1))
    fat_g: Mapped[Decimal] = mapped_column(Numeric(7, 1))

    kcal_per_serving: Mapped[Decimal] = _per_serving("kcal")
    protein_g_per_serving: Mapped[Decimal] = _per_serving("protein_g")
    carbs_g_per_serving: Mapped[Decimal] = _per_serving("carbs_g")
    fat_g_per_serving: Mapped[Decimal] = _per_serving("fat_g")

    # Missing times count as zero; null only when both are missing.
    total_time_min: Mapped[int | None] = mapped_column(
        Integer,
        Computed(
            "CASE WHEN prep_time_min IS NULL AND cook_time_min IS NULL THEN NULL "
            "ELSE coalesce(prep_time_min, 0) + coalesce(cook_time_min, 0) END",
            persisted=True,
        ),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list[RecipeStep]] = relationship(
        order_by="RecipeStep.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    lines: Mapped[list[RecipeIngredient]] = relationship(
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    __table_args__ = (CheckConstraint("text <> ''", name="text_not_empty"),)

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)


class RecipeIngredient(Base):
    """One ingredient line of a recipe."""

    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "position"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("(quantity IS NULL) = (unit IS NULL)", name="quantity_unit_together"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey(Ingredient.id), index=True)
    position: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(ForeignKey(Unit.code))
    prep_note: Mapped[str | None] = mapped_column(Text)
    optional: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
