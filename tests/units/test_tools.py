import pytest

from tests.conftest import Call
from tests.units.test_seed import EXPECTED

pytestmark = pytest.mark.anyio


async def test_list_units(call: Call) -> None:
    is_error, result = await call("list_units")
    assert is_error is False
    by_code = {u["code"]: (u["dimension"], u["to_base"]) for u in result["items"]}
    assert by_code == {code: (dim, factor) for code, (dim, factor) in EXPECTED.items()}
    assert by_code["g"] == ("mass", 1)
    assert by_code["ml"] == ("volume", 1)
    assert by_code["clove"] == ("count", 1)
    assert by_code["kg"] == ("mass", 1000)
    assert by_code["tbsp"] == ("volume", 15)
