"""Tests for settlement terminal id / short id format rules."""
from __future__ import annotations

from src.services.ocr.parsers.settlement_terminal_id import (
    is_valid_settlement_terminal_short_id,
    normalize_settlement_terminal_short_id,
)


def test_normalize_terminal_short_id_requires_exactly_four_hex_chars_for_manual_input():
    assert normalize_settlement_terminal_short_id("f353") == "f353"
    assert normalize_settlement_terminal_short_id("0ED7") == "0ed7"
    assert normalize_settlement_terminal_short_id("f35") is None
    assert normalize_settlement_terminal_short_id("f3533") is None
    assert normalize_settlement_terminal_short_id("3000") is None


def test_normalize_terminal_short_id_allows_ocr_extraction_from_longer_fragment():
    assert normalize_settlement_terminal_short_id("e9cO", from_ocr=True) == "e9c0"
    assert normalize_settlement_terminal_short_id("端末識別番号2C0e", from_ocr=True) == "2c0e"


def test_is_valid_settlement_terminal_short_id():
    assert is_valid_settlement_terminal_short_id("84e2")
    assert not is_valid_settlement_terminal_short_id("1234")
