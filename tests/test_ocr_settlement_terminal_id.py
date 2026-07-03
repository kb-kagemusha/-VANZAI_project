"""Tests for settlement terminal_id (端末番号) format validation."""
import pytest

from src.services.ocr.parsers.settlement_terminal_id import (
    is_valid_settlement_terminal_id,
    normalize_settlement_terminal_id,
)


@pytest.mark.parametrize(
    "value",
    [
        "0ed777ad-eba8-46df-babd-d131c08d6e76",
        "1c0e8213-6cd5-4f9a-bc6a-e0b50bfe1671",
        "98f0ec2f-fc54-4e00-a503-2ecb6659c7be",
    ],
)
def test_normalize_accepts_valid_uuid(value):
    assert normalize_settlement_terminal_id(value) == value.lower()
    assert is_valid_settlement_terminal_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "babd-d131c08d6e76",
        "0ed777ad-eba8-46df-babd",
        "GGGGGGGG-GGGG-GGGG-GGGG-GGGGGGGGGGGG",
        "0ed777ad-eba8-46df-babd-d131c08d6e76-extra",
        "",
    ],
)
def test_normalize_rejects_invalid_uuid(value):
    assert normalize_settlement_terminal_id(value) is None
    assert not is_valid_settlement_terminal_id(value)


def test_normalize_uppercase_to_lowercase():
    assert (
        normalize_settlement_terminal_id("0ED777AD-EBA8-46DF-BABD-D131C08D6E76")
        == "0ed777ad-eba8-46df-babd-d131c08d6e76"
    )
