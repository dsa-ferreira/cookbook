import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.ingredients.service import get_or_create


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Ingredient))


# --- get-or-create (service level) ---------------------------------------------


def test_get_or_create_creates_new(db_session: Session) -> None:
    ids = get_or_create(db_session, ["za'atar"])
    assert list(ids) == ["za'atar"]
    assert db_session.get(Ingredient, ids["za'atar"]).name == "za'atar"


def test_get_or_create_reuses_existing(db_session: Session) -> None:
    first = get_or_create(db_session, ["garlic"])
    before = count(db_session)
    second = get_or_create(db_session, ["Garlic"])
    assert second == first
    assert count(db_session) == before


def test_variants_resolve_to_one_ingredient(db_session: Session) -> None:
    ids = get_or_create(db_session, ["Chickpeas", "  chickpeas ", "CHICKPEAS"])
    assert ids == {"chickpeas": ids["chickpeas"]}
    assert count(db_session) == 1


def test_blank_name_is_refused(db_session: Session) -> None:
    with pytest.raises(ValueError):
        get_or_create(db_session, ["   "])
