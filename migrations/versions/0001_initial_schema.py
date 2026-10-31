"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-31 17:26:27.558294

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create units, ingredients, recipes and their child tables."""
    op.create_table(
        "ingredients",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("name <> ''", name=op.f("ck_ingredients_name_not_empty")),
        sa.CheckConstraint(
            "name = lower(name) AND name = btrim(regexp_replace(name, '\\s+', ' ', 'g'))",
            name=op.f("ck_ingredients_name_normalized"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingredients")),
        sa.UniqueConstraint("name", name=op.f("uq_ingredients_name")),
    )
    op.create_table(
        "recipes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("prep_time_min", sa.Integer(), nullable=True),
        sa.Column("cook_time_min", sa.Integer(), nullable=True),
        sa.Column("kcal", sa.Numeric(precision=7, scale=1), nullable=False),
        sa.Column("protein_g", sa.Numeric(precision=7, scale=1), nullable=False),
        sa.Column("carbs_g", sa.Numeric(precision=7, scale=1), nullable=False),
        sa.Column("fat_g", sa.Numeric(precision=7, scale=1), nullable=False),
        sa.Column(
            "kcal_per_serving",
            sa.Numeric(),
            sa.Computed("round(kcal / NULLIF(servings, 0), 1)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "protein_g_per_serving",
            sa.Numeric(),
            sa.Computed("round(protein_g / NULLIF(servings, 0), 1)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "carbs_g_per_serving",
            sa.Numeric(),
            sa.Computed("round(carbs_g / NULLIF(servings, 0), 1)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "fat_g_per_serving",
            sa.Numeric(),
            sa.Computed("round(fat_g / NULLIF(servings, 0), 1)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "total_time_min",
            sa.Integer(),
            sa.Computed(
                "CASE WHEN prep_time_min IS NULL AND cook_time_min IS NULL THEN NULL "
                "ELSE coalesce(prep_time_min, 0) + coalesce(cook_time_min, 0) END",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("name <> ''", name=op.f("ck_recipes_name_not_empty")),
        sa.CheckConstraint("carbs_g >= 0", name=op.f("ck_recipes_carbs_g_non_negative")),
        sa.CheckConstraint("cook_time_min >= 0", name=op.f("ck_recipes_cook_time_non_negative")),
        sa.CheckConstraint("fat_g >= 0", name=op.f("ck_recipes_fat_g_non_negative")),
        sa.CheckConstraint("kcal >= 0", name=op.f("ck_recipes_kcal_non_negative")),
        sa.CheckConstraint("prep_time_min >= 0", name=op.f("ck_recipes_prep_time_non_negative")),
        sa.CheckConstraint("protein_g >= 0", name=op.f("ck_recipes_protein_g_non_negative")),
        sa.CheckConstraint("servings > 0", name=op.f("ck_recipes_servings_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipes")),
    )
    op.create_table(
        "units",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("to_base", sa.Numeric(), nullable=False),
        sa.CheckConstraint(
            "dimension IN ('mass', 'volume', 'count')", name=op.f("ck_units_dimension")
        ),
        sa.CheckConstraint("to_base > 0", name=op.f("ck_units_to_base_positive")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_units")),
    )
    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("recipe_id", sa.BigInteger(), nullable=False),
        sa.Column("ingredient_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("prep_note", sa.Text(), nullable=True),
        sa.Column("optional", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "(quantity IS NULL) = (unit IS NULL)",
            name=op.f("ck_recipe_ingredients_quantity_unit_together"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_recipe_ingredients_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["ingredient_id"],
            ["ingredients.id"],
            name=op.f("fk_recipe_ingredients_ingredient_id_ingredients"),
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_recipe_ingredients_recipe_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["unit"], ["units.code"], name=op.f("fk_recipe_ingredients_unit_units")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_ingredients")),
        sa.UniqueConstraint("recipe_id", "position", name=op.f("uq_recipe_ingredients_recipe_id")),
    )
    op.create_index(
        op.f("ix_recipe_ingredients_ingredient_id"),
        "recipe_ingredients",
        ["ingredient_id"],
        unique=False,
    )
    op.create_table(
        "recipe_steps",
        sa.Column("recipe_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint("text <> ''", name=op.f("ck_recipe_steps_text_not_empty")),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_recipe_steps_recipe_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("recipe_id", "position", name=op.f("pk_recipe_steps")),
    )


def downgrade() -> None:
    """Drop every table created by upgrade."""
    op.drop_table("recipe_steps")
    op.drop_index(op.f("ix_recipe_ingredients_ingredient_id"), table_name="recipe_ingredients")
    op.drop_table("recipe_ingredients")
    op.drop_table("units")
    op.drop_table("recipes")
    op.drop_table("ingredients")
