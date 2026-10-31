"""The tool catalogue as clients see it in ``tools/list``."""

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio

READ_TOOLS = {"list_units", "search_ingredients", "list_recipes", "get_recipe"}
WRITE_TOOLS = {"create_recipe", "update_recipe", "delete_recipe"}


@pytest.fixture
async def tools(mcp_client: Client) -> dict:
    return {t.name: t for t in (await mcp_client.list_tools()).tools}


async def test_exactly_seven_tools(tools: dict) -> None:
    assert set(tools) == READ_TOOLS | WRITE_TOOLS
    for tool in tools.values():
        assert tool.description, tool.name
        assert tool.input_schema["type"] == "object", tool.name
        assert tool.output_schema, tool.name


async def test_no_resources_or_prompts(mcp_client: Client) -> None:
    assert (await mcp_client.list_resources()).resources == []
    assert (await mcp_client.list_prompts()).prompts == []


async def test_annotations(tools: dict) -> None:
    for name in READ_TOOLS:
        assert tools[name].annotations.read_only_hint is True, name

    create = tools["create_recipe"].annotations
    assert (create.read_only_hint, create.idempotent_hint) == (False, False)

    update = tools["update_recipe"].annotations
    assert (update.read_only_hint, update.idempotent_hint, update.destructive_hint) == (
        False,
        True,
        False,
    )

    delete = tools["delete_recipe"].annotations
    assert (delete.destructive_hint, delete.idempotent_hint) == (True, True)


async def test_decimal_inputs_are_numbers(tools: dict) -> None:
    create = tools["create_recipe"].input_schema
    recipe = create["$defs"]["RecipeIn"]["properties"]
    assert recipe["protein_g"]["type"] == "number"

    listing = tools["list_recipes"].input_schema["properties"]
    branches = listing["min_protein_per_serving"]["anyOf"]
    assert {"type": "number"} in branches


async def test_descriptions_carry_the_domain_rules(tools: dict) -> None:
    for name in ("create_recipe", "update_recipe"):
        assert "whole-recipe totals" in tools[name].description, name
    update = tools["update_recipe"].description
    assert "replace the whole list" in update
    assert "null clears" in update


@pytest.mark.parametrize("tool", ["create_recipe", "update_recipe"])
async def test_every_recipe_field_is_described(tools: dict, tool: str) -> None:
    defs = tools[tool].input_schema["$defs"]
    undescribed = [
        f"{model}.{field}"
        for model, schema in defs.items()
        for field, prop in schema.get("properties", {}).items()
        if not prop.get("description")
    ]
    assert undescribed == []


async def test_ambiguous_outputs_are_described(tools: dict) -> None:
    unit = tools["list_units"].output_schema["$defs"]["UnitOut"]["properties"]
    assert "base unit" in unit["to_base"]["description"]
    line = tools["get_recipe"].output_schema["$defs"]["IngredientLineOut"]["properties"]
    assert "garnish" in line["optional"]["description"]
