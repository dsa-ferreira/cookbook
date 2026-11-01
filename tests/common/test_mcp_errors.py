import json
import logging

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from cookbook.common.errors import InvalidInputError, NotFoundError
from cookbook.common.mcp.errors import tool_errors
from cookbook.recipes import service as recipes
from cookbook.recipes.schemas import RecipeIn
from tests.conftest import Call
from tests.recipes.factories import line, recipe_doc

pytestmark = pytest.mark.anyio


class Echo(BaseModel):
    servings: int = Field(gt=0)


def raising(exc: Exception):
    @tool_errors
    async def tool() -> str:
        raise exc

    return tool


async def body_of(tool) -> dict:
    result = await tool()
    assert result.is_error is True
    (text,) = result.content
    assert json.loads(text.text) == result.structured_content
    return result.structured_content


async def test_success_passes_through() -> None:
    @tool_errors
    async def tool(x: int) -> int:
        return x + 1

    assert await tool(1) == 2


async def test_pydantic_validation_error() -> None:
    try:
        Echo.model_validate({"servings": 0})
    except Exception as exc:
        body = await body_of(raising(exc))
    assert body["error"] == "validation_error"
    assert [d["loc"] for d in body["details"]] == [["servings"]]
    assert "input" not in body["details"][0]


async def test_invalid_input_error() -> None:
    details = [{"loc": ["ingredients", 1, "unit"], "msg": "unknown unit 'handful'"}]
    body = await body_of(raising(InvalidInputError("unknown unit code: handful", details)))
    assert body == {
        "error": "validation_error",
        "message": "unknown unit code: handful",
        "details": details,
    }


async def test_not_found_error() -> None:
    body = await body_of(raising(NotFoundError("recipe 7 not found")))
    assert body == {"error": "not_found", "message": "recipe 7 not found"}


async def test_unexpected_error_hides_internals(caplog: pytest.LogCaptureFixture) -> None:
    secret = "connection to postgres://admin:hunter2@db failed: SELECT * FROM recipes"
    tool = raising(RuntimeError(secret))
    result = await tool()
    assert result.structured_content == {
        "error": "internal_error",
        "message": "internal server error",
    }
    assert secret not in result.content[0].text
    assert "Traceback" not in result.content[0].text
    # The details go to the server log instead.
    assert secret in caplog.text


async def test_signature_is_kept() -> None:
    import inspect

    @tool_errors
    async def tool(recipe_id: int, limit: int = 50) -> dict:
        """Docs."""
        return {}

    assert list(inspect.signature(tool).parameters) == ["recipe_id", "limit"]
    assert tool.__doc__ == "Docs."


# --- through the server: unknown arguments and logging -----------------------------


async def test_unknown_argument_is_rejected(call: Call) -> None:
    is_error, body = await call("list_recipes", min_kcal=100)
    assert is_error is True
    assert body == {
        "error": "validation_error",
        "message": "unknown argument: min_kcal",
        "details": [
            {
                "type": "extra_forbidden",
                "loc": ["min_kcal"],
                "msg": "Extra inputs are not permitted",
            }
        ],
    }


async def test_every_unknown_argument_is_named(call: Call) -> None:
    is_error, body = await call("get_recipe", recipe_id=1, verbose=True, fields=["name"])
    assert is_error is True
    assert body["error"] == "validation_error"
    assert [d["loc"] for d in body["details"]] == [["verbose"], ["fields"]]
    assert {d["type"] for d in body["details"]} == {"extra_forbidden"}


async def test_unknown_argument_stops_the_tool(call: Call, db_session: Session) -> None:
    rid = recipes.create(db_session, RecipeIn.model_validate(recipe_doc())).id
    is_error, _ = await call("delete_recipe", recipe_id=rid, force=True)
    assert is_error is True
    assert recipes.get(db_session, rid).id == rid


@pytest.fixture
def warnings(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.WARNING, logger="cookbook.mcp")
    return caplog


def rejection(caplog: pytest.LogCaptureFixture) -> str:
    (record,) = [r for r in caplog.records if r.name == "cookbook.mcp"]
    assert record.levelno == logging.WARNING
    return record.getMessage()


async def test_argument_error_is_logged(call: Call, warnings: pytest.LogCaptureFixture) -> None:
    await call("list_recipes", all_ingredients={"chicken": "all"}, sort="name")
    message = rejection(warnings)
    assert message.startswith("tool list_recipes rejected: args=['all_ingredients', 'sort']")
    assert "'loc': ['all_ingredients']" in message
    assert "list_type" in message


async def test_unknown_argument_is_logged(call: Call, warnings: pytest.LogCaptureFixture) -> None:
    await call("list_recipes", ingredients=["chicken"])
    message = rejection(warnings)
    assert "tool list_recipes rejected: args=['ingredients']" in message
    assert "extra_forbidden" in message


async def test_error_from_the_tool_body_is_logged(
    call: Call, warnings: pytest.LogCaptureFixture
) -> None:
    doc = recipe_doc(ingredients=[line("spinach", 1, "handful")])
    await call("create_recipe", recipe=doc)
    message = rejection(warnings)
    assert "tool create_recipe rejected: args=['recipe']" in message
    assert "unknown_unit" in message


async def test_logged_rejection_has_no_values(
    call: Call, warnings: pytest.LogCaptureFixture
) -> None:
    doc = recipe_doc(name="Grandma's secret stew", servings=0, steps=["Simmer for hours."])
    await call("create_recipe", recipe=doc)
    message = rejection(warnings)
    assert "'loc': ['recipe', 'servings']" in message
    for value in ("Grandma's secret stew", "Simmer for hours.", "chickpeas", "drained"):
        assert value not in message


async def test_successful_call_is_not_logged(
    call: Call, warnings: pytest.LogCaptureFixture
) -> None:
    await call("list_recipes")
    assert [r for r in warnings.records if r.name == "cookbook.mcp"] == []
