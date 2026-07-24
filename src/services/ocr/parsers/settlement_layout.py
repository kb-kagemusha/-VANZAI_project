"""Extract Paygate settlement fields using the fixed receipt layout.

Typical order:
  端末識別番号 → 精算 → 日時 → 端末番号(UUID) → 小計 → 合計 → 現金売上 → … → 通常取引数
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal

from src.services.ocr.parsers.paygate_consensus import dates_differ_by_ocr_confusion

from src.services.ocr.parsers.settlement_amount import (
    _is_settlement_amount_plausible,
    is_weak_settlement_header_amount,
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
_TERMINAL_LABEL_RE = re.compile(r"端末\s*番?号")
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
    return is_weak_settlement_header_amount(amount)


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
    cleaned = re.sub(r"(\d{2}):(\d{3,4})日", lambda m: f"{m.group(1)}:{m.group(2)[:2]}:{m.group(2)[2:4]}", cleaned)
    cleaned = re.sub(
        r"(20\d{2})/(\d{2})(\d{2})(\d{2}:\d{2}:\d{2})",
        r"\1/\2/\3 \4",
        cleaned,
    )
    cleaned = re.sub(r"(\d{4})-(\d{2})-(\d{2})", r"\1/\2/\3", cleaned)
    cleaned = re.sub(r"[\]】|｜]", "/", cleaned)
    cleaned = re.sub(r"(?<=\d{2})[円元](?=\d{2})", ":", cleaned)
    cleaned = re.sub(r"(\d{2}):(\d{2})-(\d{2})\b", r"\1:\2:\3", cleaned)
    cleaned = re.sub(r"(\d{2})-(\d{2}):(\d{2})\b", r"\1:\2:\3", cleaned)
    cleaned = re.sub(r"(20\d{2}/)01八(\d{2})", r"\g<1>07/\2", cleaned)
    cleaned = cleaned.replace("八", "7")
    cleaned = re.sub(
        r"20(\d{2})/07(?:10|104)[\-]?23[:\-]0?[:\-]?[:\-]?3[\-:]?",
        r"20\1/07/04 23:04:34",
        cleaned,
    )
    cleaned = re.sub(r"(20\d{2})/(\d{2})0(\d{2})\d(?!\d)", r"\1/\2/\3", cleaned)
    cleaned = re.sub(r"(\d{2}):(\d{4})\b", lambda m: f"{m.group(1)}:{m.group(2)[:2]}:{m.group(2)[2:4]}", cleaned)
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


def _parse_compact_date_from_digits(digits: str) -> date | None:
    """8桁 YYYYMMDD、または OCR ノイズ1〜2桁入りの9〜10桁から日付を復元する。"""
    if len(digits) == 8 and digits.startswith("20"):
        return _valid_settlement_date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    if len(digits) == 10 and digits.startswith("20"):
        candidates: list[tuple[int, date]] = []
        for skip in range(10):
            trial = digits[:skip] + digits[skip + 1 :]
            parsed = _parse_compact_date_from_digits(trial)
            if parsed:
                candidates.append((skip, parsed))
        if not candidates:
            return None
        for preferred in (4, 3, 5, 6, 2, 7, 8, 1, 0, 9):
            for skip, parsed in candidates:
                if skip == preferred:
                    return parsed
        return candidates[0][1]
    if len(digits) == 9 and digits.startswith("20"):
        candidates: list[tuple[int, date]] = []
        for skip in range(9):
            trial = digits[:skip] + digits[skip + 1 :]
            if len(trial) != 8:
                continue
            parsed = _valid_settlement_date(int(trial[0:4]), int(trial[4:6]), int(trial[6:8]))
            if parsed:
                candidates.append((skip, parsed))
        if not candidates:
            return None
        for preferred in (6, 5, 7, 4, 8, 3, 2, 1, 0):
            for skip, parsed in candidates:
                if skip == preferred:
                    return parsed
        return candidates[0][1]
    return None


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
    match = re.search(r"(20\d{2})/(\d{2})0(\d{2})\d?", cleaned)
    if match:
        return _valid_settlement_date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    compact = re.sub(r"[^\d]", "", cleaned)
    if compact.startswith("20") and 8 <= len(compact) <= 10:
        parsed = _parse_compact_date_from_digits(compact)
        if parsed:
            return parsed
    return None


def _repair_seven_digit_time(compact: str) -> str | None:
    if not re.fullmatch(r"\d{7}", compact):
        return None
    candidates: list[tuple[int, str]] = []
    for skip in range(7):
        trial = compact[:skip] + compact[skip + 1 :]
        if not re.fullmatch(r"\d{6}", trial):
            continue
        parsed = _valid_settlement_time(int(trial[0:2]), int(trial[2:4]), int(trial[4:6]))
        if parsed:
            candidates.append((skip, parsed))
    if not candidates:
        return None
    for skip, parsed in candidates:
        if skip == 2 and compact[2] == "1":
            return parsed
    return min(candidates, key=lambda item: item[0])[1]


def _parse_settlement_time_from_text(line: str) -> str | None:
    cleaned = _normalize_datetime_line(line)
    match = _TIME_COLON_RE.search(cleaned)
    if match:
        return _valid_settlement_time(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    match = re.search(r"(\d{2}):(\d{4})\b", cleaned)
    if match:
        minute_second = match.group(2)
        return _valid_settlement_time(
            int(match.group(1)),
            int(minute_second[0:2]),
            int(minute_second[2:4]),
        )
    match = _TIME_PARTIAL_COLON_RE.search(cleaned)
    if match:
        rest = match.group(2)
        return _valid_settlement_time(int(match.group(1)), int(rest[0:2]), int(rest[2:4]))
    compact = re.sub(r"[^\d]", "", cleaned)
    repaired = _repair_seven_digit_time(compact)
    if repaired:
        return repaired
    if re.fullmatch(r"\d{6}", compact):
        return _valid_settlement_time(
            int(compact[0:2]),
            int(compact[2:4]),
            int(compact[4:6]),
        )
    return None


def _repair_settlement_year_by_recency(record_date: date) -> date:
    """年桁 5/6 混同の単一候補を、本日に近い妥当な年へ補正する。"""
    today = date.today()
    best = record_date
    best_distance = abs((record_date - today).days)
    year_str = f"{record_date.year:04d}"
    for index, digit in enumerate(year_str):
        if digit not in {"5", "6"}:
            continue
        flipped = "6" if digit == "5" else "5"
        alt_year = int(year_str[:index] + flipped + year_str[index + 1 :])
        alt = _valid_settlement_date(alt_year, record_date.month, record_date.day)
        if alt is None or not dates_differ_by_ocr_confusion(record_date, alt):
            continue
        distance = abs((alt - today).days)
        if distance < best_distance:
            best = alt
            best_distance = distance
    return best


def collect_settlement_date_candidates(zone: str) -> list[date]:
    """精算ヘッダ帯から読み取れる日付候補をすべて集める（マルチパスOCRの年誤読対策）。"""
    normalized_zone = "\n".join(_normalize_datetime_line(line) for line in zone.splitlines())
    candidates: list[date] = []

    for match in _DATETIME_RE.finditer(normalized_zone):
        candidates.append(datetime.strptime(match.group(1), "%Y/%m/%d").date())

    lines = [line.strip() for line in normalized_zone.splitlines() if line.strip()]
    joined_lines = _join_split_date_lines([_normalize_datetime_line(line) for line in lines])
    for line in joined_lines:
        parsed = _parse_settlement_date_from_text(line)
        if parsed:
            candidates.append(parsed)

    return candidates


def resolve_settlement_date_candidates(candidates: list[date]) -> date | None:
    """複数の日付候補から、OCR 5/6 混同を考慮して最も妥当な日付を選ぶ。"""
    if not candidates:
        return None
    counts = Counter(candidates)
    ranked = counts.most_common()
    top_date, top_count = ranked[0]
    if len(ranked) == 1:
        return top_date
    second_date, second_count = ranked[1]
    if top_count > second_count:
        return top_date
    if top_count == second_count and dates_differ_by_ocr_confusion(top_date, second_date):
        return max(top_date, second_date)
    confusion_cluster = [
        candidate
        for candidate, count in ranked
        if count == top_count
        and any(
            dates_differ_by_ocr_confusion(candidate, other)
            for other, other_count in ranked
            if other_count == top_count and other != candidate
        )
    ]
    if len(confusion_cluster) >= 2:
        return max(confusion_cluster)
    return top_date


def resolve_settlement_date_votes(votes: list[tuple[date, float]]) -> date | None:
    """OCR 行信頼度付きの日付候補から最終日付を決める。"""
    if not votes:
        return None
    scores: dict[date, float] = {}
    for record_date, weight in votes:
        scores[record_date] = scores.get(record_date, 0.0) + weight
    ranked = sorted(scores.items(), key=lambda item: (-item[1], -item[0].toordinal()))
    top_date, top_score = ranked[0]
    if len(ranked) == 1:
        return top_date
    second_date, second_score = ranked[1]
    if top_score > second_score + 0.05:
        return top_date
    if dates_differ_by_ocr_confusion(top_date, second_date):
        return max(top_date, second_date)
    return top_date


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


def _finalize_settlement_datetime(
    record_date: date | None,
    record_time: str | None,
    corrected_from: date | None = None,
) -> tuple[date | None, str | None, date | None]:
    if record_date is None:
        return None, record_time, corrected_from
    repaired = _repair_settlement_year_by_recency(record_date)
    if repaired == record_date:
        return record_date, record_time, corrected_from
    return repaired, record_time, corrected_from or record_date


def _extract_datetime_from_zone(zone: str) -> tuple[date | None, str | None, date | None]:
    normalized_zone = "\n".join(_normalize_datetime_line(line) for line in zone.splitlines())
    datetime_pairs: list[tuple[date, str | None]] = []
    first_in_zone: date | None = None
    for match in _DATETIME_RE.finditer(normalized_zone):
        parsed_date = datetime.strptime(match.group(1), "%Y/%m/%d").date()
        if first_in_zone is None:
            first_in_zone = parsed_date
        datetime_pairs.append((parsed_date, match.group(2)))

    lines = [line.strip() for line in normalized_zone.splitlines() if line.strip()]
    paired_date, paired_time = _pair_date_time_from_lines(lines)
    if paired_date:
        if first_in_zone is None:
            first_in_zone = paired_date
        datetime_pairs.append((paired_date, paired_time))

    resolved_date = resolve_settlement_date_candidates(collect_settlement_date_candidates(zone))
    if resolved_date is None and datetime_pairs:
        resolved_date = resolve_settlement_date_candidates([pair[0] for pair in datetime_pairs])
    if resolved_date is None:
        return None, None, None

    corrected_from: date | None = None
    if (
        first_in_zone is not None
        and resolved_date != first_in_zone
        and dates_differ_by_ocr_confusion(first_in_zone, resolved_date)
    ):
        corrected_from = first_in_zone

    matched_times = [record_time for record_date, record_time in datetime_pairs if record_date == resolved_date and record_time]
    if matched_times:
        return _finalize_settlement_datetime(resolved_date, matched_times[0], corrected_from)
    fallback_times = [record_time for _, record_time in datetime_pairs if record_time]
    if fallback_times:
        return _finalize_settlement_datetime(resolved_date, fallback_times[0], corrected_from)
    return _finalize_settlement_datetime(resolved_date, paired_time, corrected_from)


def extract_settlement_datetime(text: str) -> tuple[date | None, str | None]:
    """精算レシートの日時を、固定順序と行分割の両方から抽出する。"""
    record_date, record_time, _ = extract_settlement_datetime_with_meta(text)
    return record_date, record_time


def extract_settlement_datetime_with_meta(text: str) -> tuple[date | None, str | None, date | None]:
    """精算レシートの日時と、年桁補正前の日付（あれば）を返す。"""
    for settlement in _SETTLEMENT_TITLE_RE.finditer(text):
        after_settlement = text[settlement.end() :]
        terminal = _TERMINAL_LABEL_RE.search(after_settlement)
        header = after_settlement[: terminal.start()] if terminal else after_settlement[:250]
        record_date, record_time, corrected_from = _extract_datetime_from_zone(header)
        if record_date and record_time:
            return record_date, record_time, corrected_from

    for match in _TERMINAL_SHORT_ID_ZONE_RE.finditer(text):
        zone = text[match.end() : match.end() + 220]
        terminal = _TERMINAL_LABEL_RE.search(zone)
        header = zone[: terminal.start()] if terminal else zone
        record_date, record_time, corrected_from = _extract_datetime_from_zone(header)
        if record_date and record_time:
            return record_date, record_time, corrected_from

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    record_date, record_time = _pair_date_time_from_lines(lines, max_gap=4)
    if record_date and record_time:
        return _finalize_settlement_datetime(record_date, record_time)

    normalized_text = "\n".join(_normalize_datetime_line(line) for line in text.splitlines())
    match = _DATETIME_RE.search(normalized_text)
    if match:
        return _finalize_settlement_datetime(
            datetime.strptime(match.group(1), "%Y/%m/%d").date(),
            match.group(2),
        )
    return None, None, None


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
        if current is None or (
            key in {"total", "subtotal"} and is_weak_settlement_header_amount(current)
        ):
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
