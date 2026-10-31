from flask import Blueprint

from cookbook.common.web.session import get_session
from cookbook.units import service
from cookbook.units.schemas import UnitList

bp = Blueprint("units", __name__)


@bp.get("/units")
def list_units():
    return UnitList(items=service.list_units(get_session())).model_dump(mode="json")
