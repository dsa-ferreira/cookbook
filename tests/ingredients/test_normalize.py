import pytest

from cookbook.ingredients.normalize import normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Chickpeas", "chickpeas"),
        ("  chickpeas ", "chickpeas"),
        ("Chickpea   Flour", "chickpea flour"),
        ("\tsmoked\n paprika  ", "smoked paprika"),
        ("ZA'ATAR", "za'atar"),
        ("garlic", "garlic"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_normalizes_to_empty(raw: str) -> None:
    assert normalize_name(raw) == ""
