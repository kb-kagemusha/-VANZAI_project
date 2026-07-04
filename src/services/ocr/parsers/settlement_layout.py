"""Extract Paygate settlement fields using the fixed receipt layout.

Typical order:
  端末識別番号 → 精算 → 日時 → 端末番号(UUID) → 小計 → 合計 → 現金売上 → … → 通常取引数
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from src.services.ocr.parsers.settlement_amount import (
    _is_settlement_amount_plausible,
    sanitize_settlement_amount,
    sanitize_settlement_sales_amount,
)

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s*(\d{2}:\d{2}:\d{2})")
_DATE_STANDARD_RE = re.compile(r"(20\d{2})[/／](\d{2})[/／](\d{2})")
_DATE_MERGED_SLASH_RE = re.compile(r"20(\d{2})(\d{2})[/／](\d{2})")
_TIME_COLON_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})")
_SETTLEMENT_TITLE_RE = re.compile(r"精算")
_TERMINAL_LABEL_RE = re.compile(r"端末\s*番号")
_TERMINAL_SHORT_ID_ZONE_RE = re.compile(
    r"(?:端末|境末|末|携末|備末|市末)[識議護鉄証藤鉄]?[別][番]?号",
    re.IGNORECASE,
)
_SALES_BLOCK_END_RE = re.compile(r"通常\s*取引数|消[費賢][税稁]|精算現金|日本た")
_AMOUNT_TAIL_RE = re.compile(r"([\d,./]+)\s*$")

_LAYOUT_LINE_SPECS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("subtotal", re.compile(r"小[計訳訁餁]"), False),
    ("total", re.compile(r"[合今会][計訳訁]"), False),
    ("cash", re.compile(r"現[金会]売"), True),
    ("credit", re.compile(r"クレ[ジンチ][ッット]*売"), True),
    ("tax", re.compile(r"消[費賢][税稁]"), False),
)


def _is_weak_total(amount: Decimal | None) -> bool:
    if amount is None:
        return True
    if amount < Decimal("980"):
        return True
    return not _is_settlement_amount_plausible(amount)


def _amount_from_lines(line: str, next_line: str | None, *, sales_field: bool) -> tuple[Decimal | None, str | None]:
    sanitize = sanitize_settlement_sales_amount if sales_field else sanitize_settlement_amount
    inline = _AMOUNT_TAIL_RE.search(line)
    if inline:
        amount, corrected = sanitize(inline.group(1))
        if amount is not None and (not sales_field or amount == 0 or _is_settlement_amount_plausible(amount)):
            return amount, corrected
    if next_line:
        standalone = _AMOUNT_TAIL_RE.match(next_line.strip())
        if standalone:
            amount, corrected = sanitize(standalone.group(1))
            if amount is not None and (not sales_field or amount == 0 or _is_settlement_amount_plausible(amount)):
                return amount, corrected
    embedded = re.search(r"([\d,./]{3,})", line)
    if embedded:
        amount, corrected = sanitize(embedded.group(1))
        if amount is not None and (not sales_field or amount == 0 or _is_settlement_amount_plausible(amount)):
            return amount, corrected
    return None, None


def _first_settlement_sales_block(text: str) -> str | None:
    settlement = _SETTLEMENT_TITLE_RE.search(text)
    if not settlement:
        return None
    after_settlement = text[settlement.end() :]
    terminal = _TERMINAL_LABEL_RE.search(after_settlement)
    if not terminal:
        return None
    after_terminal = after_settlement[terminal.end() :]
    subtotal = re.search(r"小[計訳訁餁]", after_terminal)
    if not subtotal:
        return None
    block = after_terminal[subtotal.start() :]
    end = _SALES_BLOCK_END_RE.search(block)
    if end:
        block = block[: end.start()]
    return block


def _valid_settlement_date(year: int, month: int, day: int) -> date | None:
    if year < 2020 or year > 2035:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_settlement_date_from_text(line: str) -> date | None:
    cleaned = line.replace("O", "0").replace("o", "0").replace("　", " ").strip()
    match = _DATE_STANDARD_RE.search(cleaned)
    if match:
        return _valid_settlement_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = _DATE_MERGED_SLASH_RE.search(cleaned)
    if match:
        return _valid_settlement_date(
            int(f"20{match.group(1)}"),
            int(match.group(2)),
            int(match.group(3)),
        )
    return None


def _parse_settlement_time_from_text(line: str) -> str | None:
    cleaned = line.replace("O", "0").replace("o", "0").strip()
    match = _TIME_COLON_RE.search(cleaned)
    if match:
        hour, minute, second = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return f"{hour:02d}:{minute:02d}:{second:02d}"
    if re.fullmatch(r"\d{6}", cleaned):
        hour = int(cleaned[0:2])
        minute = int(cleaned[2:4])
        second = int(cleaned[4:6])
        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return f"{hour:02d}:{minute:02d}:{second:02d}"
    return None


def _extract_datetime_from_zone(zone: str) -> tuple[date | None, str | None]:
    match = _DATETIME_RE.search(zone)
    if match:
        return (
            datetime.strptime(match.group(1), "%Y/%m/%d").date(),
            match.group(2),
        )

    lines = [line.strip() for line in zone.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        record_date = _parse_settlement_date_from_text(line)
        if not record_date:
            continue
        same_line_time = _parse_settlement_time_from_text(line)
        if same_line_time:
            return record_date, same_line_time
        for lookahead in lines[index + 1 : index + 4]:
            record_time = _parse_settlement_time_from_text(lookahead)
            if record_time:
                return record_date, record_time
    return None, None


def extract_settlement_datetime(text: str) -> tuple[date | None, str | None]:
    """精算レシートの日時を、固定順序と行分割の両方から抽出する。"""
    for settlement in _SETTLEMENT_TITLE_RE.finditer(text):
        after_settlement = text[settlement.end() :]
        terminal = _TERMINAL_LABEL_RE.search(after_settlement)
        header = after_settlement[: terminal.start()] if terminal else after_settlement[:250]
        record_date, record_time = _extract_datetime_from_zone(header)
        if record_date and record_time:
            return record_date, record_time

    for match in _TERMINAL_SHORT_ID_ZONE_RE.finditer(text):
        zone = text[match.end() : match.end() + 220]
        terminal = _TERMINAL_LABEL_RE.search(zone)
        header = zone[: terminal.start()] if terminal else zone
        record_date, record_time = _extract_datetime_from_zone(header)
        if record_date and record_time:
            return record_date, record_time

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        record_date = _parse_settlement_date_from_text(line)
        if not record_date:
            continue
        for lookahead in lines[index : index + 4]:
            record_time = _parse_settlement_time_from_text(lookahead)
            if record_time:
                return record_date, record_time

    match = _DATETIME_RE.search(text)
    if match:
        return (
            datetime.strptime(match.group(1), "%Y/%m/%d").date(),
            match.group(2),
        )
    return None, None


def extract_settlement_datetime_from_layout(text: str) -> tuple[date | None, str | None]:
    return extract_settlement_datetime(text)


def extract_amounts_from_layout(text: str) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    block = _first_settlement_sales_block(text)
    if not block:
        return {}, {}
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    amounts: dict[str, Decimal | None] = {}
    corrections: dict[str, str] = {}
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        for key, pattern, sales_field in _LAYOUT_LINE_SPECS:
            if amounts.get(key) is not None:
                continue
            if not pattern.search(line):
                continue
            amount, corrected = _amount_from_lines(line, next_line, sales_field=sales_field)
            if amount is not None:
                amounts[key] = amount
            if corrected:
                corrections[key] = corrected
    return amounts, corrections


def merge_layout_amounts(
    amounts: dict[str, Decimal | None],
    corrections: dict[str, str],
    layout_amounts: dict[str, Decimal | None],
    layout_corrections: dict[str, str],
) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    merged = dict(amounts)
    merged_corrections = dict(corrections)
    for key, value in layout_amounts.items():
        if value is None:
            continue
        current = merged.get(key)
        if current is None or (key == "total" and _is_weak_total(current)):
            merged[key] = value
            if key in layout_corrections:
                merged_corrections[key] = layout_corrections[key]
    if _is_weak_total(merged.get("total")):
        for fallback in ("subtotal", "cash"):
            candidate = merged.get(fallback)
            if candidate is not None and _is_settlement_amount_plausible(candidate):
                merged["total"] = candidate
                break
    return merged, merged_corrections
