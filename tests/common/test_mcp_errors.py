import json

import pytest
from pydantic import BaseModel, Field

from cookbook.common.errors import InvalidInputError, NotFoundError
from cookbook.common.mcp.errors import tool_errors

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
