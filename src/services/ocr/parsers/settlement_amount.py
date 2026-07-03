"""Settlement receipt amount parsing with yen-symbol OCR correction.

精算レシートの金額は必ず「￥」付きで印字される。OCR が「￥」を先頭の「1」と誤認するため
「￥5,880」→「15,880」になる典型パターンを補正する。
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.services.ocr.parsers.paygate_amount import normalize_amount_text
from src.services.ocr.unit_breakdown import solve_unit_combinations

_YEN_MARKERS = "¥￥円YＹyｙ"
# ￥5,880 → 15,880 / ￥8,820 → 18,820 等（先頭1桁 + カンマ区切り）
_YEN_MISREAD_COMMA_RE = re.compile(r"^1(\d{1,2},\d{3}(?:,\d{3})*)$")
# ラベル直後に ￥ が OCR されず 15880 のように連結されたケース
_YEN_MISREAD_PLAIN_RE = re.compile(r"^1(\d{3,})$")


def _parse_digits(value: str) -> Decimal | None:
    try:
        return Decimal(normalize_amount_text(value).replace(",", ""))
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _is_settlement_amount_plausible(amount: Decimal) -> bool:
    """精算レシート金額は単価(980/1480/2980)の組合せで表現できる。"""
    if amount <= 0:
        return False
    if int(amount) % 10 != 0:
        return False
    return bool(solve_unit_combinations(int(amount)))


def correct_settlement_yen_misread_amount(
    amount: Decimal,
    *,
    raw_fragment: str | None = None,
) -> tuple[Decimal, str | None]:
    """Fix OCR reading ￥ as a leading digit on settlement receipt amounts."""
    if amount <= 0:
        return amount, None

    fragment = normalize_amount_text((raw_fragment or "").strip())
    fragment = re.sub(rf"^[{_YEN_MARKERS}]\s*", "", fragment)

    comma_match = _YEN_MISREAD_COMMA_RE.match(fragment)
    if comma_match:
        corrected = _parse_digits(comma_match.group(1))
        if corrected is not None and _is_settlement_amount_plausible(corrected):
            return corrected, fragment

    digits = str(int(amount))
    if digits.startswith("1") and len(digits) >= 4:
        plain_match = _YEN_MISREAD_PLAIN_RE.match(digits)
        if plain_match:
            corrected = _parse_digits(plain_match.group(1))
            if corrected is not None and _is_settlement_amount_plausible(corrected):
                if not _is_settlement_amount_plausible(amount) or corrected < amount:
                    return corrected, digits

    return amount, None


def sanitize_settlement_amount(raw: str | None) -> tuple[Decimal | None, str | None]:
    """Parse a settlement amount OCR fragment and apply yen misread correction."""
    if not raw:
        return None, None
    amount = _parse_digits(raw)
    if amount is None:
        return None, None
    corrected, source = correct_settlement_yen_misread_amount(amount, raw_fragment=raw)
    return corrected, source
