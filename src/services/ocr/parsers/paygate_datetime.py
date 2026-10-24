"""Fuzzy date/time parsing for noisy Paygate OCR text."""
from __future__ import annotations

import re
from datetime import date, datetime

_DATE_RE = re.compile(r"(\d{4})[/,，.\-](\d{2})[/,，.\-](\d{2})")
_STRICT_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def normalize_paygate_ocr_text(text: str) -> str:
    normalized = text.replace("，", ",").replace("：", ":")
    normalized = re.sub(r"(\d{4}),(\d{2})/(\d{2})", r"\1/\2/\3", normalized)
    normalized = re.sub(r"(\d{4}),(\d{2}),(\d{2})", r"\1/\2/\3", normalized)
    return normalized


def parse_fuzzy_time(value: str) -> str | None:
    line = value.strip().rstrip(".")
    if _STRICT_TIME_RE.fullmatch(line):
        return line

    match = re.fullmatch(r"(\d{2})(\d{2}):(\d{2})", line)
    if match:
        return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"

    match = re.fullmatch(r"(\d{2}):(\d{2})(\d{2})", line)
    if match:
        return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"

    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d)(\d)?", line)
    if match:
        seconds = f"{match.group(3)}{match.group(4) or ''}".ljust(2, "0")[:2]
        return f"{match.group(1)}:{match.group(2)}:{seconds}"

    match = re.fullmatch(r"(\d{2}):(\d{3})(\d)", line)
    if match:
        middle = match.group(2)
        return f"{match.group(1)}:{middle[:2]}:{middle[2:]}{match.group(3)}"

    match = re.fullmatch(r"(\d{2}):(\d{2})(\d{1,2})", line)
    if match and line.count(":") == 1:
        return f"{match.group(1)}:{match.group(2)}:{match.group(3)}"

    return None


def extract_paygate_datetime(block: str) -> tuple[date | None, str | None, str]:
    """Return (record_date, record_time, datetime_source).

    datetime_source is one of: ocr_strict | fuzzy | missing
    """
    normalized = normalize_paygate_ocr_text(block)
    date_match = _DATE_RE.search(normalized)
    if not date_match:
        return None, None, "missing"

    record_date = datetime.strptime(
        f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}",
        "%Y/%m/%d",
    ).date()

    for line in normalized.splitlines():
        stripped = line.strip()
        if _STRICT_TIME_RE.fullmatch(stripped):
            return record_date, stripped, "ocr_strict"
        candidate = parse_fuzzy_time(stripped)
        if candidate:
            source = "ocr_strict" if _STRICT_TIME_RE.fullmatch(candidate) else "fuzzy"
            return record_date, candidate, source

    inline_time = re.search(
        rf"{re.escape(date_match.group(0))}[\s\n]+([0-9:]{{4,10}})",
        normalized,
    )
    if inline_time:
        raw = inline_time.group(1)
        if _STRICT_TIME_RE.fullmatch(raw):
            return record_date, raw, "ocr_strict"
        candidate = parse_fuzzy_time(raw)
        if candidate:
            source = "ocr_strict" if _STRICT_TIME_RE.fullmatch(candidate) else "fuzzy"
            return record_date, candidate, source

    return record_date, None, "missing"


def extract_fuzzy_datetime(block: str) -> tuple[date, str] | None:
    """Backward-compatible helper returning only date/time when both present."""
    record_date, record_time, source = extract_paygate_datetime(block)
    if record_date is None or record_time is None:
        return None
    if source == "missing":
        return None
    return record_date, record_time
