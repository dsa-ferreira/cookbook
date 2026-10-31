import pytest
from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.ingredients.service import get_or_create


def names(resp) -> list[str]:
    return [i["name"] for i in resp.get_json()["items"]]


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


# --- GET /ingredients ----------------------------------------------------------


def test_substring_search(client: FlaskClient, db_session: Session) -> None:
    get_or_create(db_session, ["chickpeas", "chickpea flour", "spinach"])
    db_session.commit()
    resp = client.get("/ingredients?q=Chick")
    assert resp.status_code == 200
    assert names(resp) == ["chickpea flour", "chickpeas"]


def test_search_treats_like_wildcards_literally(client: FlaskClient, db_session: Session):
    get_or_create(db_session, ["100% rye flour", "rye"])
    db_session.commit()
    assert names(client.get("/ingredients?q=%25")) == ["100% rye flour"]
    assert names(client.get("/ingredients?q=_")) == []


def test_list_without_query_is_name_ordered_up_to_default_limit(
    client: FlaskClient, db_session: Session
) -> None:
    created = [f"ingredient {i:02d}" for i in range(55)]
    get_or_create(db_session, reversed(created))
    db_session.commit()
    resp = client.get("/ingredients")
    assert resp.status_code == 200
    assert names(resp) == created[:50]


def test_pagination(client: FlaskClient, db_session: Session) -> None:
    get_or_create(db_session, ["a", "b", "c", "d"])
    db_session.commit()
    assert names(client.get("/ingredients?limit=2&offset=1")) == ["b", "c"]


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc", "bogus=1"])
def test_invalid_params_are_422(client: FlaskClient, query: str) -> None:
    resp = client.get(f"/ingredients?{query}")
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "validation_error"
