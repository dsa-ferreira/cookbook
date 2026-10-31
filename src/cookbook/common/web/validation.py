"""Parse request bodies and query strings into pydantic models."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, get_args, get_origin

from flask import request
from pydantic import BaseModel

from cookbook.common.errors import InvalidInputError

type View = Callable[..., Any]


def validate_body(model: type[BaseModel]) -> Callable[[View], View]:
    """Parse the JSON body into ``model`` and pass it to the view as ``body``.

    A ``pydantic.ValidationError`` propagates to the app's 422 handler.
    """

    def decorator(view: View) -> View:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                raise InvalidInputError(
                    "request body must be a JSON object",
                    [{"loc": ["body"], "msg": "expected a JSON object", "type": "body_type"}],
                )
            return view(*args, body=model.model_validate(data), **kwargs)

        return wrapper

    return decorator


def _is_list_field(model: type[BaseModel], name: str) -> bool:
    field = model.model_fields.get(name)
    if field is None:
        return False
    annotation = field.annotation
    return get_origin(annotation) is list or any(
        get_origin(arg) is list for arg in get_args(annotation)
    )


def parse_query[M: BaseModel](model: type[M]) -> M:
    """Parse ``request.args`` into ``model``.

    Fields typed as lists collect repeated parameters (``?a=1&a=2``); other
    fields take the first value. A ``pydantic.ValidationError`` propagates to
    the app's 422 handler.
    """
    data: dict[str, Any] = {}
    for key in request.args:
        values = request.args.getlist(key)
        data[key] = values if _is_list_field(model, key) else values[0]
    return model.model_validate(data)
