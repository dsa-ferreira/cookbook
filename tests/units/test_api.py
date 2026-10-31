from flask.testing import FlaskClient

from tests.units.test_seed import EXPECTED


def test_list_units(client: FlaskClient) -> None:
    resp = client.get("/units")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    by_code = {u["code"]: (u["dimension"], u["to_base"]) for u in items}
    assert by_code == {code: (dim, factor) for code, (dim, factor) in EXPECTED.items()}
    assert by_code["g"] == ("mass", 1)
    assert by_code["ml"] == ("volume", 1)
    assert by_code["clove"] == ("count", 1)
    assert by_code["kg"] == ("mass", 1000)
    assert by_code["tbsp"] == ("volume", 15)


def test_units_need_a_key(anon_client: FlaskClient) -> None:
    assert anon_client.get("/units").status_code == 401
