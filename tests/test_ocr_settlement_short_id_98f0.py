import pytest

from src.services.ocr.parsers.settlement_terminal_id import normalize_settlement_terminal_short_id


@pytest.mark.parametrize(
    "value,expected",
    [
        ("981e", "98f0"),
        ("9810", "98f0"),
        ("980", "98f0"),
    ],
)
def test_normalize_short_id_repairs_98f0_family(value, expected):
    assert normalize_settlement_terminal_short_id(value, from_ocr=True) == expected
