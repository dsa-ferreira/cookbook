from flask import Blueprint, Flask
from flask.testing import FlaskClient
from pydantic import BaseModel, Field

from cookbook.common.web.validation import validate_body
from tests.conftest import AUTH


class Echo(BaseModel):
    name: str = Field(min_length=1)
    servings: int = Field(gt=0)


def authed(app: Flask) -> FlaskClient:
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = AUTH["Authorization"]
    return client


def add_echo_route(app: Flask) -> None:
    bp = Blueprint("echo", __name__)

    @bp.post("/echo")
    @validate_body(Echo)
    def echo(body: Echo):
        return body.model_dump()

    @bp.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    app.register_blueprint(bp)


def test_healthz(anon_client: FlaskClient) -> None:
    resp = anon_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_valid_body_reaches_view(app: Flask) -> None:
    add_echo_route(app)
    resp = authed(app).post("/echo", json={"name": "x", "servings": 2})
    assert resp.status_code == 200
    assert resp.get_json() == {"name": "x", "servings": 2}


def test_bad_body_returns_422_shape(app: Flask) -> None:
    add_echo_route(app)
    resp = authed(app).post("/echo", json={"name": "x", "servings": 0})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["error"] == "validation_error"
    assert isinstance(body["message"], str)
    assert [d["loc"] for d in body["details"]] == [["servings"]]


def test_non_json_body_returns_422(app: Flask) -> None:
    add_echo_route(app)
    resp = authed(app).post("/echo", data="nope", content_type="text/plain")
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "validation_error"


def test_unknown_route_returns_404_shape(client: FlaskClient) -> None:
    resp = client.get("/no/such/thing")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not_found", "message": "no such resource"}


def test_unhandled_error_returns_500_without_internals(app: Flask) -> None:
    add_echo_route(app)
    resp = authed(app).get("/boom")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "internal_error", "message": "internal server error"}
