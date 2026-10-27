"""Cross-row consensus fixes for Paygate screenshot OCR within one image."""
from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.validation import validate_parsed_row

_OCR_DATE_DIGIT_PAIRS = frozenset({("5", "6"), ("6", "5"), ("0", "6"), ("6", "0"), ("8", "0"), ("0", "8")})
_CONSENSUS_MIN_ROWS = 3
_CONSENSUS_RATIO = 0.6


def _date_digits(value: date) -> str:
    return value.strftime("%Y%m%d")


def dates_differ_by_ocr_confusion(left: date, right: date) -> bool:
    if left == right:
        return False
    left_digits = _date_digits(left)
    right_digits = _date_digits(right)
    if len(left_digits) != 8 or len(right_digits) != 8:
        return False
    diff_positions = [index for index in range(8) if left_digits[index] != right_digits[index]]
    if len(diff_positions) != 1:
        return False
    index = diff_positions[0]
    pair = (left_digits[index], right_digits[index])
    return pair in _OCR_DATE_DIGIT_PAIRS or (pair[1], pair[0]) in _OCR_DATE_DIGIT_PAIRS


def _mode_date(rows: list[ParsedOcrRow]) -> date | None:
    dates = [row.record_date for row in rows if row.record_date is not None]
    if not dates:
        return None
    return Counter(dates).most_common(1)[0][0]


def _mode_amount(rows: list[ParsedOcrRow]) -> Decimal | None:
    amounts = [row.amount for row in rows if row.amount is not None]
    if not amounts:
        return None
    return Counter(amounts).most_common(1)[0][0]


def _recompute_row_metadata(row: ParsedOcrRow) -> None:
    parsed_datetime_source = row.datetime_source
    if row.raw_payload.get("datetime_corrected_from"):
        parsed_datetime_source = "fuzzy"
    row.validation_errors = validate_parsed_row(row)
    meta = metadata_from_parsed_fields(
        record_date=row.record_date,
        record_time=row.record_time,
        amount=row.amount,
        transaction_no=row.transaction_no,
        receipt_no=row.receipt_no,
        amount_meta=row.raw_payload or {},
        parsed_datetime_source=parsed_datetime_source,
        validation_errors=row.validation_errors or None,
    )
    row.amount_inferred = meta.amount_inferred
    row.amount_source = meta.amount_source
    row.datetime_source = meta.datetime_source
    row.confirm_required = meta.confirm_required


def apply_paygate_image_consensus(rows: list[ParsedOcrRow]) -> None:
    """Fix per-image OCR digit noise using same-screenshot majority vote."""
    if len(rows) < _CONSENSUS_MIN_ROWS:
        return

    mode_date = _mode_date(rows)
    if mode_date is not None:
        date_count = sum(1 for row in rows if row.record_date == mode_date)
        if date_count / len(rows) >= _CONSENSUS_RATIO:
            for row in rows:
                if row.record_date is None or row.record_date == mode_date:
                    continue
                if dates_differ_by_ocr_confusion(row.record_date, mode_date):
                    row.raw_payload = dict(row.raw_payload or {})
                    row.raw_payload["datetime_corrected_from"] = row.record_date.isoformat()
                    row.raw_payload["datetime_consensus"] = mode_date.isoformat()
                    row.record_date = mode_date
                    row.datetime_source = "fuzzy"
                    row.confirm_required = True

    mode_amount = _mode_amount(rows)
    if mode_amount == Decimal("980"):
        amount_count = sum(1 for row in rows if row.amount == mode_amount)
        if amount_count / len(rows) >= _CONSENSUS_RATIO:
            for row in rows:
                if row.amount != Decimal("1980"):
                    continue
                block = str((row.raw_payload or {}).get("block", ""))
                if "1,980" in block or "1，980" in block:
                    continue
                row.raw_payload = dict(row.raw_payload or {})
                row.raw_payload["amount_corrected_from"] = "1980"
                row.raw_payload["amount_consensus"] = "980"
                row.raw_payload["amount_source"] = "corrected_ocr"
                row.amount = Decimal("980")
                row.amount_source = "corrected_ocr"
                row.amount_inferred = False
                row.confirm_required = True

    for row in rows:
        if (row.raw_payload or {}).get("datetime_corrected_from") or (row.raw_payload or {}).get(
            "amount_consensus"
        ):
            _recompute_row_metadata(row)
