from flask import Blueprint, url_for

from cookbook.common.web.session import get_session
from cookbook.common.web.validation import parse_query, validate_body
from cookbook.recipes import listing, service
from cookbook.recipes.schemas import RecipeIn, RecipeListParams

bp = Blueprint("recipes", __name__)


@bp.get("/recipes")
def list_recipes():
    params = parse_query(RecipeListParams)
    return listing.list_recipes(get_session(), params).model_dump(mode="json")


@bp.post("/recipes")
@validate_body(RecipeIn)
def create_recipe(body: RecipeIn):
    recipe = service.create(get_session(), body)
    location = url_for("recipes.get_recipe", recipe_id=recipe.id)
    return recipe.model_dump(mode="json"), 201, {"Location": location}


@bp.get("/recipes/<int:recipe_id>")
def get_recipe(recipe_id: int):
    return service.get(get_session(), recipe_id).model_dump(mode="json")


@bp.delete("/recipes/<int:recipe_id>")
def delete_recipe(recipe_id: int):
    service.delete(get_session(), recipe_id)
    return "", 204


@bp.put("/recipes/<int:recipe_id>")
@validate_body(RecipeIn)
def replace_recipe(recipe_id: int, body: RecipeIn):
    return service.replace(get_session(), recipe_id, body).model_dump(mode="json")
