"""Work-date (稼働日) resolution for Paygate settlement receipts.

Business rule (Phase 0 暫定, see docs/ops/OCR_INVENTORY_PILOT_TEMPLATE.md):
精算時刻が 06:00 未満の場合は、精算日の前日を稼働日とみなす（深夜またぎ対応）。
このルールはパイロット結果を踏まえて見直す可能性がある。
"""
from __future__ import annotations

from datetime import date, time, timedelta

NIGHT_CUTOFF = time(6, 0, 0)


def compute_work_date(record_date: date | None, record_time: str | None) -> date | None:
    """Resolve the 稼働日 from a settlement record_date/record_time pair."""
    if record_date is None:
        return None
    if not record_time:
        return record_date
    try:
        hour, minute, second = (int(part) for part in record_time.split(":"))
        parsed_time = time(hour, minute, second)
    except (ValueError, TypeError):
        return record_date
    if parsed_time < NIGHT_CUTOFF:
        return record_date - timedelta(days=1)
    return record_date
