"""Normalize Paygate screenshot payment method (決済方法)."""
from __future__ import annotations

import re

ALLOWED_PAYGATE_PAYMENT_METHODS = frozenset({"現金", "QRコード", "クレジット"})

_PAYMENT_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^現金$"), "現金"),
    (re.compile(r"^qr\s*コード$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qr$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qrcode$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^クレジット(?:カード)?$"), "クレジット"),
    (re.compile(r"^クレヂット(?:カード)?$"), "クレジット"),
)


def normalize_paygate_payment_method(value: str | None) -> str | None:
    """Return canonical payment method or None if missing/invalid."""
    if not value:
        return None
    cleaned = value.strip().replace("　", " ")
    if cleaned in ALLOWED_PAYGATE_PAYMENT_METHODS:
        return cleaned
    lowered = cleaned.lower()
    for pattern, canonical in _PAYMENT_ALIASES:
        if pattern.match(cleaned) or pattern.match(lowered):
            return canonical
    return None
