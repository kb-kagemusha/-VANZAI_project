"""Normalize Paygate screenshot payment method (決済方法)."""
from __future__ import annotations

import re

from src.services.ocr.parsers.paygate_datetime import normalize_paygate_ocr_text

ALLOWED_PAYGATE_PAYMENT_METHODS = frozenset({"現金", "QRコード", "クレジット"})

PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE = (
    "正しいPaygateの画像ではありません。"
    "決済方法の記載があるスクリーンショットの画像をアップロードし直してください。"
)

_PAYMENT_METHOD_LABEL_RE = re.compile(r"決\s*済\s*方\s*法")
_PAYMENT_METHOD_LABEL_OCR_RE = re.compile(r"決[済消湾湾]方\s*法")

_PAYMENT_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^現金$"), "現金"),
    (re.compile(r"^qr\s*コード$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qr$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^qrcode$", re.IGNORECASE), "QRコード"),
    (re.compile(r"^クレジット(?:カード)?$"), "クレジット"),
    (re.compile(r"^クレヂット(?:カード)?$"), "クレジット"),
)


def paygate_screenshot_has_payment_method_label(text: str) -> bool:
    """Return True when OCR text includes the Paygate screenshot 決済方法 label."""
    if not text or not text.strip():
        return False
    normalized = normalize_paygate_ocr_text(text)
    compact = re.sub(r"\s+", "", normalized)
    if "決済方法" in compact:
        return True
    if _PAYMENT_METHOD_LABEL_RE.search(normalized):
        return True
    return bool(_PAYMENT_METHOD_LABEL_OCR_RE.search(normalized))


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
