"""Tests for Paygate cross-row consensus."""
from datetime import date

from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.parsers.paygate_consensus import apply_paygate_image_consensus, dates_differ_by_ocr_confusion


def test_dates_differ_by_ocr_confusion_detects_year_and_month_noise():
    assert dates_differ_by_ocr_confusion(date(2025, 6, 10), date(2026, 6, 10))
    assert dates_differ_by_ocr_confusion(date(2026, 5, 10), date(2026, 6, 10))
    assert not dates_differ_by_ocr_confusion(date(2026, 6, 10), date(2026, 6, 11))


def test_apply_paygate_image_consensus_normalizes_outlier_dates():
    rows = [
        ParsedOcrRow(
            source_type="paygate_screenshot",
            record_date=date(2026, 6, 10),
            transaction_no="1230567",
            receipt_no="7810946337325",
            raw_payload={},
        ),
        ParsedOcrRow(
            source_type="paygate_screenshot",
            record_date=date(2026, 6, 10),
            transaction_no="1230557",
            receipt_no="7810923797325",
            raw_payload={},
        ),
        ParsedOcrRow(
            source_type="paygate_screenshot",
            record_date=date(2025, 6, 10),
            transaction_no="1230543",
            receipt_no="7810912457325",
            raw_payload={},
        ),
    ]
    apply_paygate_image_consensus(rows)
    assert rows[2].record_date == date(2026, 6, 10)
    assert rows[2].raw_payload["datetime_corrected_from"] == "2025-06-10"
