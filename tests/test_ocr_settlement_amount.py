"""Tests for settlement receipt amount yen-symbol OCR correction."""
from decimal import Decimal

import pytest

from src.services.ocr.parsers.settlement_amount import sanitize_settlement_amount


@pytest.mark.parametrize(
    ("raw", "expected", "corrected_from"),
    [
        ("5,880", Decimal("5880"), None),
        ("15,880", Decimal("5880"), "15,880"),
        ("15880", Decimal("5880"), "15880"),
        ("8,820", Decimal("8820"), None),
        ("18,820", Decimal("8820"), "18,820"),
        ("0", Decimal("0"), None),
        ("1,480", Decimal("1480"), None),
    ],
)
def test_sanitize_settlement_amount_corrects_yen_misread(raw, expected, corrected_from):
    amount, source = sanitize_settlement_amount(raw)
    assert amount == expected
    assert source == corrected_from
