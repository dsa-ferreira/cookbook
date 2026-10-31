from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.ingredients.normalize import normalize_name
from cookbook.ingredients.schemas import IngredientListParams, IngredientOut


def get_or_create(session: Session, names: Iterable[str]) -> dict[str, int]:
    """Map each normalized name to its ingredient id, creating missing ones.

    Runs in the caller's transaction, so a rollback also drops any
    ingredients created here. ``ON CONFLICT DO NOTHING`` + ``SELECT`` is safe
    against concurrent writers creating the same name.
    """
    wanted = sorted({normalize_name(n) for n in names})
    if not wanted:
        return {}
    if "" in wanted:
        raise ValueError("ingredient names must not be blank")
    session.execute(
        insert(Ingredient)
        .values([{"name": n} for n in wanted])
        .on_conflict_do_nothing(index_elements=[Ingredient.name])
    )
    rows = session.execute(
        select(Ingredient.name, Ingredient.id).where(Ingredient.name.in_(wanted))
    )
    return {name: id_ for name, id_ in rows}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(session: Session, params: IngredientListParams) -> list[IngredientOut]:
    stmt = select(Ingredient).order_by(Ingredient.name)
    q = normalize_name(params.q or "")
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
    stmt = stmt.limit(params.limit).offset(params.offset)
    return [IngredientOut.model_validate(i) for i in session.scalars(stmt)]
