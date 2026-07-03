"""Settlement receipt terminal_id (端末番号) format rules.

- 英数字のみ
- 8桁-4桁-4桁-4桁-12桁（ハイフン区切り）
- アルファベットは小文字 a～f のみ（16進）
- 数字は 0～9 のみ

端末識別番号 (terminal_short_id):
- 必ず4桁（16進小文字 0-9a-f）
"""
from __future__ import annotations

import re

_SETTLEMENT_TERMINAL_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
_SETTLEMENT_TERMINAL_SHORT_ID_RE = re.compile(r"^[0-9a-f]{4}$")
_REGISTRATION_SEGMENT_RE = re.compile(r"^\d{4}$")
_OCR_SHORT_ID_FIXES = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Ｏ": "0",
        "ｏ": "0",
        "Ｉ": "1",
        "ｌ": "1",
        "l": "1",
        "G": "0",
        "g": "0",
    }
)


def format_terminal_id_from_hex32(hex_only: str) -> str:
    return (
        f"{hex_only[:8]}-{hex_only[8:12]}-{hex_only[12:16]}-"
        f"{hex_only[16:20]}-{hex_only[20:32]}"
    )


def is_valid_settlement_terminal_id(value: str | None) -> bool:
    if not value:
        return False
    return _SETTLEMENT_TERMINAL_ID_RE.fullmatch(value.strip().lower()) is not None


def normalize_settlement_terminal_id(value: str | None) -> str | None:
    """Return canonical terminal_id or None if the value does not match the rules."""
    if not value:
        return None
    cleaned = value.strip().lower().replace(" ", "")
    if _SETTLEMENT_TERMINAL_ID_RE.fullmatch(cleaned):
        return cleaned
    hex_only = re.sub(r"[^0-9a-f]", "", cleaned)
    if len(hex_only) == 32 and _HEX32_RE.fullmatch(hex_only):
        return format_terminal_id_from_hex32(hex_only)
    return None


def normalize_settlement_terminal_short_id(
    value: str | None,
    *,
    from_ocr: bool = False,
) -> str | None:
    """端末識別番号を正規化する。必ず4桁16進（0-9a-f）。"""
    if not value:
        return None
    translated = value.strip().translate(_OCR_SHORT_ID_FIXES)
    candidate = re.sub(r"[^0-9a-fA-F]", "", translated).lower()
    if from_ocr:
        if len(candidate) < 4:
            return None
        if len(candidate) > 4:
            candidate = candidate[:4]
    elif len(candidate) != 4:
        return None
    if _REGISTRATION_SEGMENT_RE.fullmatch(candidate):
        return None
    if candidate.isdigit():
        return None
    if _SETTLEMENT_TERMINAL_SHORT_ID_RE.fullmatch(candidate):
        return candidate
    return None


def is_valid_settlement_terminal_short_id(value: str | None) -> bool:
    return normalize_settlement_terminal_short_id(value) is not None
