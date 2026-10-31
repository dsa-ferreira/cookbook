import pytest
from sqlalchemy.orm import Session

from cookbook.ingredients import service
from tests.conftest import Call

pytestmark = pytest.mark.anyio


@pytest.fixture
def catalogue(db_session: Session) -> None:
    service.get_or_create(db_session, ["spinach", "chickpeas", "Chickpea flour", "apple"])
    db_session.commit()


def names(result: dict) -> list[str]:
    return [i["name"] for i in result["items"]]


@pytest.mark.usefixtures("catalogue")
async def test_substring_search(call: Call) -> None:
    is_error, result = await call("search_ingredients", q="Chick")
    assert is_error is False
    assert names(result) == ["chickpea flour", "chickpeas"]
    assert all(isinstance(i["id"], int) for i in result["items"])


@pytest.mark.usefixtures("catalogue")
async def test_name_order_without_query(call: Call) -> None:
    is_error, result = await call("search_ingredients")
    assert is_error is False
    assert names(result) == ["apple", "chickpea flour", "chickpeas", "spinach"]
    assert (result["limit"], result["offset"]) == (50, 0)


@pytest.mark.usefixtures("catalogue")
async def test_pagination(call: Call) -> None:
    _, result = await call("search_ingredients", limit=2, offset=1)
    assert names(result) == ["chickpea flour", "chickpeas"]


async def test_default_limit_is_50(call: Call, db_session: Session) -> None:
    created = [f"ingredient {i:02d}" for i in range(55)]
    service.get_or_create(db_session, reversed(created))
    db_session.commit()
    _, result = await call("search_ingredients")
    assert names(result) == created[:50]


async def test_like_wildcards_are_literal(call: Call, db_session: Session) -> None:
    service.get_or_create(db_session, ["100% rye flour", "rye"])
    db_session.commit()
    assert names((await call("search_ingredients", q="%"))[1]) == ["100% rye flour"]
    assert names((await call("search_ingredients", q="_"))[1]) == []


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"limit": 201}, "limit"),
        ({"limit": 0}, "limit"),
        ({"limit": "abc"}, "limit"),
        ({"offset": -1}, "offset"),
    ],
)
async def test_invalid_paging_is_a_validation_error(
    call: Call, arguments: dict, field: str
) -> None:
    is_error, body = await call("search_ingredients", **arguments)
    assert is_error is True
    assert body["error"] == "validation_error"
    assert [d["loc"] for d in body["details"]] == [[field]]
