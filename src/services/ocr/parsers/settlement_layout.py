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
_DATE_COMPACT8_RE = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
_TIME_COLON_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})")
_TIME_PARTIAL_COLON_RE = re.compile(r"(\d{2}):(\d{4})\b")
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


def _valid_settlement_time(hour: int, minute: int, second: int) -> str | None:
    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    return None


def _normalize_datetime_line(line: str) -> str:
    cleaned = line.replace("O", "0").replace("o", "0").replace("　", " ").strip()
    cleaned = cleaned.replace("：", ":").replace("／", "/")
    cleaned = re.sub(r"[\]】|｜]", "/", cleaned)
    cleaned = re.sub(r"(?<=\d{2})[円元](?=\d{2})", ":", cleaned)
    cleaned = re.sub(r"(\d{2}):(\d{2})-(\d{2})\b", r"\1:\2:\3", cleaned)
    cleaned = re.sub(r"(\d{2})-(\d{2}):(\d{2})\b", r"\1:\2:\3", cleaned)
    if "/" not in cleaned:
        cleaned = re.sub(r"\b(20\d{2})(\d{2})(\d{2})\b", r"\1/\2/\3", cleaned)
    cleaned = re.sub(
        r"(20\d{2})/(\d{5})(?!\d)",
        lambda match: f"{match.group(1)}/{match.group(2)[:2]}/{match.group(2)[3:5]}",
        cleaned,
    )
    return cleaned


def _join_split_date_lines(lines: list[str]) -> list[str]:
    joined: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"20\d{2}", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            match = re.match(r"(\d{2})[/／](\d{1,2})", next_line)
            if match:
                day_digits = re.sub(r"[^\d]", "", match.group(2))[:2]
                if day_digits:
                    joined.append(f"{line}/{match.group(1)}/{int(day_digits):02d}")
                    index += 2
                    continue
        joined.append(line)
        index += 1
    return joined


def _parse_settlement_date_from_text(line: str) -> date | None:
    cleaned = _normalize_datetime_line(line)
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
    match = _DATE_COMPACT8_RE.search(cleaned)
    if match:
        digits = match.group(1)
        return _valid_settlement_date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    return None


def _parse_settlement_time_from_text(line: str) -> str | None:
    cleaned = _normalize_datetime_line(line)
    match = _TIME_COLON_RE.search(cleaned)
    if match:
        return _valid_settlement_time(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    match = _TIME_PARTIAL_COLON_RE.search(cleaned)
    if match:
        rest = match.group(2)
        return _valid_settlement_time(int(match.group(1)), int(rest[0:2]), int(rest[2:4]))
    if re.fullmatch(r"\d{6,7}", cleaned):
        digits = cleaned[:6]
        return _valid_settlement_time(int(digits[0:2]), int(digits[2:4]), int(digits[4:6]))
    return None


def _pair_date_time_from_lines(lines: list[str], *, max_gap: int = 3) -> tuple[date | None, str | None]:
    normalized = _join_split_date_lines([_normalize_datetime_line(line) for line in lines])
    date_hits: list[tuple[int, date]] = []
    time_hits: list[tuple[int, str]] = []
    for index, line in enumerate(normalized):
        record_date = _parse_settlement_date_from_text(line)
        record_time = _parse_settlement_time_from_text(line)
        if record_date and record_time:
            return record_date, record_time
        if record_date:
            date_hits.append((index, record_date))
        if record_time:
            time_hits.append((index, record_time))

    best: tuple[date | None, str | None] = (None, None)
    best_gap = max_gap + 1
    for date_index, record_date in date_hits:
        for time_index, record_time in time_hits:
            gap = abs(date_index - time_index)
            if gap <= max_gap and gap < best_gap:
                best = (record_date, record_time)
                best_gap = gap
    return best


def _extract_datetime_from_zone(zone: str) -> tuple[date | None, str | None]:
    normalized_zone = "\n".join(_normalize_datetime_line(line) for line in zone.splitlines())
    match = _DATETIME_RE.search(normalized_zone)
    if match:
        return (
            datetime.strptime(match.group(1), "%Y/%m/%d").date(),
            match.group(2),
        )

    lines = [line.strip() for line in normalized_zone.splitlines() if line.strip()]
    return _pair_date_time_from_lines(lines)


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
    record_date, record_time = _pair_date_time_from_lines(lines, max_gap=4)
    if record_date and record_time:
        return record_date, record_time

    normalized_text = "\n".join(_normalize_datetime_line(line) for line in text.splitlines())
    match = _DATETIME_RE.search(normalized_text)
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
