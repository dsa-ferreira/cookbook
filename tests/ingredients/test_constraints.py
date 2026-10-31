"""The database-level guard on normalized ingredient names."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient


@pytest.mark.parametrize("name", ["Chickpeas", " chickpeas", "chickpea  flour", ""])
def test_ingredient_name_must_be_normalized(db_session: Session, name: str) -> None:
    db_session.add(Ingredient(name=name))
    with pytest.raises(IntegrityError, match="ck_ingredients_name"):
        db_session.flush()


def test_normalized_ingredient_name_is_accepted(db_session: Session) -> None:
    db_session.add(Ingredient(name="chickpea flour"))
    db_session.flush()
