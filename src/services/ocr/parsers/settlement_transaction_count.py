"""Settlement receipt 通常取引数 extraction.

レシート中盤は左に項目名・右に金額/数字が並ぶ。
「精算現金」行の右欄は必ず空欄で、その直前の行の右側数字が通常取引数。
"""
from __future__ import annotations

import re

_CASH_SECTION_BLANK_RE = re.compile(r"^精算\s*現金\s*$")
_CASH_BREAKDOWN_START_RE = re.compile(
    r"[-－]?\s*(?:\d+)?万円(?:札)?|"
    r"[-－]?\s*(?:\d+)?千円(?:札)?|"
    r"[-－]?\s*(?:\d+)?百円|"
    r"円玉|円札"
)
_TXN_COUNT_LABEL_RE = re.compile(r"通常\s*取引数\s*[：:]?\s*(\d+)")
_SKIP_LINE_KEYWORDS = (
    "売上",
    "消費税",
    "内税",
    "外税",
    "PAYGATE",
    "万円",
    "円玉",
    "円札",
    "千円",
    "返品",
    "取消",
)


def _compact(line: str) -> str:
    return line.replace("　", "").replace(" ", "")


def _line_has_yen_amount(line: str) -> bool:
    return "¥" in line or "￥" in line or bool(re.search(r"\d{1,3}(?:,\d{3})+", line))


def _is_cash_section_blank_row(line: str) -> bool:
    """精算現金ヘッダー行（右欄が空欄）。"""
    return _CASH_SECTION_BLANK_RE.fullmatch(_compact(line)) is not None


def _is_cash_breakdown_start(line: str) -> bool:
    """精算現金が OCR 欠落時の代替: 金種内訳の先頭行。"""
    return _CASH_BREAKDOWN_START_RE.search(line) is not None


def _find_blank_row_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _is_cash_section_blank_row(line):
            return index
    for index, line in enumerate(lines):
        if _is_cash_breakdown_start(line):
            return index
    return None


def _parse_count_from_line(line: str) -> int | None:
    if any(keyword in line for keyword in _SKIP_LINE_KEYWORDS):
        if "通常取引数" not in line.replace(" ", "").replace("　", ""):
            return None

    compact = _compact(line)
    label_match = _TXN_COUNT_LABEL_RE.search(compact)
    if label_match:
        return int(label_match.group(1))

    if _line_has_yen_amount(line):
        return None

    if re.fullmatch(r"\d+", compact):
        value = int(compact)
        if 0 <= value <= 999:
            return value

    if "," not in line:
        tail_match = re.search(r"(\d+)\s*$", line.strip())
        if tail_match:
            value = int(tail_match.group(1))
            if 0 <= value <= 999:
                return value
    return None


def extract_transaction_count_before_cash_blank(text: str) -> int | None:
    """中盤の空欄行（精算現金）の直前行から通常取引数を取得する。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blank_index = _find_blank_row_index(lines)
    if blank_index is None or blank_index == 0:
        return None

    for index in range(blank_index - 1, max(blank_index - 5, -1), -1):
        count = _parse_count_from_line(lines[index])
        if count is not None:
            return count
    return None
