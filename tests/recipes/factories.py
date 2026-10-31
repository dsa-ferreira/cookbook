"""Builders for valid recipe documents."""

from __future__ import annotations

import copy
from typing import Any

BASE_RECIPE: dict[str, Any] = {
    "name": "Smoky hummus",
    "description": "Weeknight hummus with smoked paprika.",
    "servings": 4,
    "prep_time_min": 10,
    "cook_time_min": 5,
    "steps": ["Blend everything.", "Season and serve."],
    "ingredients": [
        {"name": "chickpeas", "quantity": 400, "unit": "g", "prep_note": "drained"},
        {"name": "tahini", "quantity": 2, "unit": "tbsp"},
        {"name": "salt"},
    ],
    "kcal": 1200,
    "protein_g": 48,
    "carbs_g": 120,
    "fat_g": 56,
}


def recipe_doc(**overrides: Any) -> dict[str, Any]:
    doc = copy.deepcopy(BASE_RECIPE)
    doc.update(overrides)
    return doc


def line(name: str, quantity: float | None = None, unit: str | None = None, **extra: Any):
    out: dict[str, Any] = {"name": name, **extra}
    if quantity is not None:
        out["quantity"] = quantity
    if unit is not None:
        out["unit"] = unit
    return out
