"""Ingredient name normalization.

Two names that normalize to the same string are the same ingredient. The
database CHECK ``ck_ingredients_name_normalized`` mirrors this rule.
"""


def normalize_name(name: str) -> str:
    """Trim, collapse inner whitespace to single spaces and lowercase.

    Returns ``""`` for blank input; callers reject that.
    """
    return " ".join(name.split()).lower()
