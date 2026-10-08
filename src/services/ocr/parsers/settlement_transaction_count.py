"""Settlement receipt 通常取引数 extraction.

レシート中盤は左に項目名・右に金額/数字が並ぶ。
「精算現金」行の右欄は必ず空欄で、その直前（通常取引数行）の右側数字が通常取引数。
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
# OCR が 8 を - / 一 などと誤認するケース（通常取引数の値行のみ）
_OCR_COUNT_CHAR_FIXES: dict[str, int] = {
    "-": 8,
    "—": 8,
    "－": 8,
    "_": 8,
    "/": 8,
    "一": 1,
    "l": 1,
    "I": 1,
    "|": 1,
}


def _compact(line: str) -> str:
    return line.replace("　", "").replace(" ", "")


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


def _parse_transaction_value_line(line: str) -> int | None:
    """通常取引数ラベルの直後の値行を解釈する。"""
    compact = _compact(line)
    if not compact:
        return None

    label_match = _TXN_COUNT_LABEL_RE.search(compact)
    if label_match:
        return int(label_match.group(1))

    if re.fullmatch(r"\d+", compact):
        value = int(compact)
        if 0 <= value <= 999:
            return value

    if compact in _OCR_COUNT_CHAR_FIXES:
        return _OCR_COUNT_CHAR_FIXES[compact]

    if "," not in line and "¥" not in line and "￥" not in line:
        tail_match = re.search(r"(\d+)\s*$", line.strip())
        if tail_match:
            value = int(tail_match.group(1))
            if 0 <= value <= 999:
                return value
    return None


def _extract_from_transaction_count_block(lines: list[str], blank_index: int) -> int | None:
    """精算現金直前の通常取引数ブロック（最大3行）だけを見る。"""
    start = max(0, blank_index - 3)
    window = lines[start:blank_index]
    for index in range(len(window) - 1, -1, -1):
        compact = _compact(window[index])
        if "通常取引数" not in compact:
            continue
        same_line = _parse_transaction_value_line(window[index])
        if same_line is not None:
            return same_line
        if index + 1 < len(window):
            next_line = _parse_transaction_value_line(window[index + 1])
            if next_line is not None:
                return next_line
    return None


def extract_transaction_count_before_cash_blank(text: str) -> int | None:
    """中盤の空欄行（精算現金）直前の通常取引数ブロックから件数を取得する。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blank_index = _find_blank_row_index(lines)
    if blank_index is None or blank_index == 0:
        return None
    return _extract_from_transaction_count_block(lines, blank_index)
