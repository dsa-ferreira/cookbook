from flask import Blueprint

from cookbook.common.web.session import get_session
from cookbook.common.web.validation import parse_query
from cookbook.ingredients import service
from cookbook.ingredients.schemas import IngredientList, IngredientListParams

bp = Blueprint("ingredients", __name__)


@bp.get("/ingredients")
def list_ingredients():
    params = parse_query(IngredientListParams)
    items = service.search(get_session(), params)
    return IngredientList(items=items, limit=params.limit, offset=params.offset).model_dump(
        mode="json"
    )
