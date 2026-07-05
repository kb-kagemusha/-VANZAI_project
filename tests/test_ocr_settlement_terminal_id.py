"""Tests for settlement terminal_id (端末番号) format validation."""
import pytest

from src.services.ocr.parsers.settlement_terminal_id import (
    TerminalIdSegments,
    assemble_terminal_segments_from_hex_tokens,
    format_terminal_id_display_lines,
    format_terminal_segments_display_lines,
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


def test_format_terminal_id_display_lines_splits_uuid():
    lines = format_terminal_id_display_lines("98f0ec2f-fc54-4e00-a503-2ecb6659c7be")
    assert lines == ("98f0ec2f-fc54-4e00", "a503-2ecb6659c7be")


def test_assemble_terminal_segments_partial():
    segments = assemble_terminal_segments_from_hex_tokens(
        ["98f0ec2f", "fc54", "4e00", "2ecb6659c7be"],
        short_id="98f0",
    )
    assert segments.is_partial()
    assert segments.eight == "98f0ec2f"
    assert segments.twelve == "2ecb6659c7be"
    assert format_terminal_segments_display_lines(segments) == ("98f0ec2f-fc54-4e00", "2ecb6659c7be")


def test_terminal_segments_complete():
    segments = TerminalIdSegments(
        eight="98f0ec2f",
        four_1="fc54",
        four_2="4e00",
        four_3="a503",
        twelve="2ecb6659c7be",
    )
    assert segments.is_complete()
    assert segments.to_canonical() == "98f0ec2f-fc54-4e00-a503-2ecb6659c7be"
