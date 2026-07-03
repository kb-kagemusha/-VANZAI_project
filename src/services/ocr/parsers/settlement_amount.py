"""Settlement receipt amount parsing with yen-symbol OCR correction."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.services.ocr.parsers.paygate_amount import normalize_amount_text
from src.services.ocr.unit_breakdown import solve_unit_combinations

_YEN_MARKERS = "¥￥円YＹyｙ"
_YEN_MISREAD_COMMA_RE = re.compile(r"^1(\d{1,2}[,/]\d{3}(?:[,/]\d{3})*)$")
_YEN_MISREAD_PLAIN_RE = re.compile(r"^1(\d{3,})$")


def _normalize_amount_fragment(raw: str) -> str:
    fragment = normalize_amount_text(raw.strip())
    fragment = re.sub(rf"^[{_YEN_MARKERS}]\s*", "", fragment)
    # OCR がカンマをスラッシュに誤認（15/880）
    return fragment.replace("/", ",")


def _parse_digits(value: str) -> Decimal | None:
    try:
        return Decimal(_normalize_amount_fragment(value).replace(",", ""))
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _is_settlement_amount_plausible(amount: Decimal) -> bool:
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
    if amount <= 0:
        return amount, None

    fragment = _normalize_amount_fragment(raw_fragment or str(int(amount)))

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
    if not raw:
        return None, None
    amount = _parse_digits(raw)
    if amount is None:
        return None, None
    corrected, source = correct_settlement_yen_misread_amount(amount, raw_fragment=raw)
    return corrected, source
