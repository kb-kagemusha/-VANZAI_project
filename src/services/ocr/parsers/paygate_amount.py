"""Paygate screenshot amount extraction and yen-symbol OCR correction."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from src.services.ocr.models import OcrTextLine

_DIGIT_TRANS = str.maketrans("０１２３４５６７８９，", "0123456789,")
_YEN_MARKERS = "¥￥円YＹyｙ"
_AMOUNT_WITH_YEN_RE = re.compile(rf"[{_YEN_MARKERS}]\s*([\d,０-９]+)")
_STANDALONE_AMOUNT_RE = re.compile(r"(?:^|\n)\s*([0-9０-９,]{2,6})\s*(?:\n|$)", re.MULTILINE)
_EXPLICIT_980_RE = re.compile(r"(?:^|\n)\s*980\s*(?:\n|$)", re.MULTILINE)
_DATETIME_INLINE_AMOUNT_RE = re.compile(
    rf"\d{{4}}/\d{{2}}/\d{{2}}[\s\n]+(\d{{2}}:\d{{2}}:\d{{2}})\s+(.+)$",
    re.MULTILINE,
)
_PAYGATE_DEFAULT_AMOUNT = Decimal("980")
# 実際に発生しうる金額（￥980 以外）。1980 は ￥誤読補正の対象外。
_KNOWN_PAYGATE_AMOUNTS = frozenset(
    {
        Decimal("980"),
        Decimal("1480"),
        Decimal("1980"),
    }
)
# ¥980 が先頭1桁余分に読まれた典型パターン（1980 は実金額のため含めない）
_YEN_MISREAD_PREFIXES = frozenset("23456789")


def normalize_amount_text(value: str) -> str:
    return value.translate(_DIGIT_TRANS)


def parse_amount_digits(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(normalize_amount_text(value).replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def correct_yen_misread_amount(amount: Decimal) -> tuple[Decimal, str | None]:
    """Fix OCR reading ￥ as a leading digit (e.g. 2980 / 7980 / 1980 -> 980).

    1480 は実金額として保持。1980 は ¥980 誤読の典型のため 980 へ補正する。
    """
    if amount == Decimal("1480"):
        return amount, None

    digits = str(int(amount))
    if amount == Decimal("1980"):
        return _PAYGATE_DEFAULT_AMOUNT, "1980"

    if amount == _PAYGATE_DEFAULT_AMOUNT:
        return amount, None

    if len(digits) == 4 and digits.endswith("980") and digits[0] in _YEN_MISREAD_PREFIXES:
        return _PAYGATE_DEFAULT_AMOUNT, digits

    if len(digits) == 5 and digits.endswith("980") and digits[0] in _YEN_MISREAD_PREFIXES:
        return _PAYGATE_DEFAULT_AMOUNT, digits

    return amount, None


def sanitize_paygate_amount(value: str | None) -> tuple[Decimal | None, str | None]:
    amount = parse_amount_digits(value)
    if amount is None:
        return None, None
    corrected, source = correct_yen_misread_amount(amount)
    return corrected, source


def _line_x_center(line: OcrTextLine) -> float:
    if not line.box:
        return 0.0
    xs = [point[0] for point in line.box]
    return sum(xs) / len(xs)


def _line_y_center(line: OcrTextLine) -> float:
    if not line.box:
        return 0.0
    ys = [point[1] for point in line.box]
    return sum(ys) / len(ys)


def _is_amount_candidate_text(text: str) -> bool:
    normalized = normalize_amount_text(text.strip()).replace(",", "")
    if not normalized.isdigit():
        return False
    return 2 <= len(normalized) <= 6


def _lines_in_block(lines: list[OcrTextLine], block: str) -> list[OcrTextLine]:
    return [line for line in lines if line.text.strip() and line.text.strip() in block]


def _is_paygate_amount_plausible(amount: Decimal) -> bool:
    if amount in _KNOWN_PAYGATE_AMOUNTS:
        return True
    val = int(amount)
    return 100 <= val <= 9999


def _amount_from_text_fragment(text: str) -> tuple[Decimal | None, str | None]:
    yen_match = _AMOUNT_WITH_YEN_RE.search(text)
    if yen_match:
        amount, source = sanitize_paygate_amount(yen_match.group(1))
        if amount is not None and amount > 0:
            return amount, source

    normalized = normalize_amount_text(text)
    if "980" in normalized:
        digits = re.findall(r"\d+", normalized)
        for digits_value in digits:
            amount, source = sanitize_paygate_amount(digits_value)
            if amount is not None and amount > 0:
                return amount, source

    for digits_value in re.findall(r"\d+", normalized):
        amount, source = sanitize_paygate_amount(digits_value)
        if amount is not None and amount > 0 and _is_paygate_amount_plausible(amount):
            return amount, source
    return None, None


def _find_right_row_amount_line(lines: list[OcrTextLine], record_time: str) -> OcrTextLine | None:
    time_lines = [line for line in lines if record_time in line.text]
    if not time_lines:
        return None

    ref_line = time_lines[0]
    ref_y = _line_y_center(ref_line)
    ref_x = _line_x_center(ref_line)
    candidates: list[OcrTextLine] = []

    for line in lines:
        text = line.text.strip()
        if not text or line is ref_line:
            continue
        if text == record_time or re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
            continue
        if abs(_line_y_center(line) - ref_y) > 35:
            continue
        if _line_x_center(line) <= ref_x + 80:
            continue
        candidates.append(line)

    if not candidates:
        return None
    return max(candidates, key=_line_x_center)


def _amount_region_lines(lines: list[OcrTextLine], block: str, record_time: str) -> list[OcrTextLine]:
    before_txn = block.split("取引番号", 1)[0]
    region_lines: list[OcrTextLine] = []
    for line in lines:
        text = line.text.strip()
        if not text or text not in before_txn:
            continue
        if text == record_time:
            continue
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
            continue
        if _is_amount_candidate_text(text) or _AMOUNT_WITH_YEN_RE.search(text):
            region_lines.append(line)
    return region_lines


def _finalize_amount_meta(
    meta: dict[str, str],
    *,
    corrected_from: str | None = None,
    fallback: bool = False,
) -> dict[str, str]:
    if fallback:
        meta["amount_source"] = "fallback_default"
        meta.setdefault("amount_inferred", "paygate_default_980")
    elif corrected_from:
        meta["amount_corrected_from"] = corrected_from
        meta["amount_source"] = "corrected_ocr"
    else:
        meta["amount_source"] = "ocr"
    return meta


def _return_amount(
    amount: Decimal,
    meta: dict[str, str],
    *,
    corrected_from: str | None = None,
    fallback: bool = False,
) -> tuple[Decimal, dict[str, str]]:
    return amount, _finalize_amount_meta(meta, corrected_from=corrected_from, fallback=fallback)


def extract_paygate_amount(
    block: str,
    record_time: str,
    lines: list[OcrTextLine] | None = None,
    *,
    has_transaction: bool = False,
) -> tuple[Decimal | None, dict[str, str]]:
    """Extract amount from OCR block; infer 980 when Paygate header row is present but OCR missed blue text."""
    meta: dict[str, str] = {}
    before_txn = block.split("取引番号", 1)[0]
    block_lines = _lines_in_block(lines or [], block)

    if record_time:
        for inline in _DATETIME_INLINE_AMOUNT_RE.finditer(before_txn):
            if inline.group(1) != record_time:
                continue
            amount, source = _amount_from_text_fragment(inline.group(2))
            if amount is not None:
                return _return_amount(amount, meta, corrected_from=source)

        for line in block_lines:
            if record_time not in line.text:
                continue
            tail = line.text.split(record_time, 1)[-1].strip()
            if not tail:
                continue
            amount, source = _amount_from_text_fragment(tail)
            if amount is not None:
                return _return_amount(amount, meta, corrected_from=source)

    yen_match = _AMOUNT_WITH_YEN_RE.search(before_txn)
    if yen_match:
        amount, source = sanitize_paygate_amount(yen_match.group(1))
        if amount is not None:
            return _return_amount(amount, meta, corrected_from=source)

    right_row = _find_right_row_amount_line(block_lines, record_time) if record_time else None
    if right_row is not None:
        amount, source = _amount_from_text_fragment(right_row.text)
        if amount is not None and _is_paygate_amount_plausible(amount):
            return _return_amount(amount, meta, corrected_from=source)
        meta["amount_ocr_garbage"] = right_row.text.strip()
        return _return_amount(_PAYGATE_DEFAULT_AMOUNT, meta, fallback=True)

    if block_lines:
        region_lines = _amount_region_lines(block_lines, block, record_time) if record_time else []
        for line in sorted(
            region_lines,
            key=lambda item: (-_line_x_center(item), _line_y_center(item)),
        ):
            amount, source = _amount_from_text_fragment(line.text)
            if amount is not None and _is_paygate_amount_plausible(amount):
                return _return_amount(amount, meta, corrected_from=source)

    if record_time:
        after_time = re.search(
            rf"{re.escape(record_time)}[\s\n]+([0-9０-９,]{{2,6}})(?:[\s\n]|$)",
            before_txn,
        )
        if after_time:
            amount, source = sanitize_paygate_amount(after_time.group(1))
            if amount is not None and _is_paygate_amount_plausible(amount):
                return _return_amount(amount, meta, corrected_from=source)

    for match in _STANDALONE_AMOUNT_RE.finditer(before_txn):
        amount, source = sanitize_paygate_amount(match.group(1))
        if amount is not None and _is_paygate_amount_plausible(amount):
            return _return_amount(amount, meta, corrected_from=source)

    if _EXPLICIT_980_RE.search(before_txn):
        return _return_amount(_PAYGATE_DEFAULT_AMOUNT, meta, fallback=True)

    if has_transaction:
        return _return_amount(_PAYGATE_DEFAULT_AMOUNT, meta, fallback=True)

    return None, meta
