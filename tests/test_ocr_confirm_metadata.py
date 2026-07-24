"""Tests for OCR confirm metadata and guard rules."""
from datetime import date
from decimal import Decimal

import pytest

from src.services.ocr.confirm_metadata import (
    get_confirm_rejection_reasons,
    metadata_from_parsed_fields,
    resolve_amount_from_parser_meta,
)
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_amount import extract_paygate_amount
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.validation import validate_parsed_row

FAILED_IMAGE_TEXT = """
取引番号
1230567
レシート番号
7810946337325
2026/06/10
20:521
"""


def test_fallback_default_metadata():
    amount, meta = extract_paygate_amount(
        "取引番号\n1230567\n",
        "",
        [],
        has_transaction=True,
    )
    assert amount == Decimal("980")
    inferred, source = resolve_amount_from_parser_meta(meta)
    assert inferred is True
    assert source == "fallback_default"

    row_meta = metadata_from_parsed_fields(
        record_date=date(2026, 6, 10),
        record_time="20:52:59",
        amount=amount,
        transaction_no="1230567",
        receipt_no="7810946337325",
        amount_meta=meta,
        parsed_datetime_source="ocr_strict",
        validation_errors=None,
    )
    assert row_meta.amount_inferred is True
    assert row_meta.amount_source == "fallback_default"
    assert row_meta.confirm_required is True


def test_corrected_ocr_metadata():
    amount, meta = extract_paygate_amount(
        "2026/06/10 20:52:59\n2980\n取引番号\n1230567\n",
        "20:52:59",
        [],
        has_transaction=True,
    )
    assert amount == Decimal("980")
    assert meta["amount_source"] == "corrected_ocr"
    row_meta = metadata_from_parsed_fields(
        record_date=date(2026, 6, 10),
        record_time="20:52:59",
        amount=amount,
        transaction_no="1230567",
        receipt_no="7810946337325",
        amount_meta=meta,
        parsed_datetime_source="ocr_strict",
        validation_errors=None,
    )
    assert row_meta.amount_source == "corrected_ocr"
    assert row_meta.confirm_required is True


def test_fuzzy_datetime_row_requires_confirm():
    rows = PaygateScreenshotParser().parse(run_ocr_from_text(FAILED_IMAGE_TEXT))
    assert rows
    row = rows[0]
    assert row.datetime_source == "fuzzy"
    assert row.confirm_required is True
    assert any("record_time format" in err for err in row.validation_errors)


def test_strict_row_can_be_confirmable():
    text = """
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
"""
    rows = PaygateScreenshotParser().parse(run_ocr_from_text(text))
    assert len(rows) == 1
    row = rows[0]
    assert row.amount_source == "ocr"
    assert row.datetime_source == "ocr_strict"
    assert row.confirm_required is False
    assert not row.validation_errors


def test_invalid_record_time_adds_validation_error():
    parsed = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 6, 10),
        record_time="20:52:1",
        amount=Decimal("980"),
        transaction_no="1230567",
        receipt_no="7810946337325",
    )
    errors = validate_parsed_row(parsed)
    assert "record_time format is invalid (expected HH:MM:SS)" in errors


def test_screenshot_confirm_allows_corrected_ocr_without_confirm_required_block():
    class _Row:
        source_type = "paygate_screenshot"
        status = "pending_review"
        deleted_at = None
        validation_errors = None
        amount_inferred = False
        amount_source = "corrected_ocr"
        datetime_source = "fuzzy"
        confirm_required = True
        record_date = date(2026, 6, 10)
        record_time = "20:52:07"
        amount = Decimal("980")
        transaction_no = "1230567"
        receipt_no = "7810946337325"

    assert get_confirm_rejection_reasons(_Row()) == []


def test_screenshot_confirm_still_blocks_inferred_amount():
    class _Row:
        source_type = "paygate_screenshot"
        status = "pending_review"
        deleted_at = None
        validation_errors = None
        amount_inferred = True
        amount_source = "fallback_default"
        datetime_source = "ocr_strict"
        confirm_required = True
        record_date = date(2026, 6, 10)
        record_time = "20:52:07"
        amount = Decimal("980")
        transaction_no = "1230567"
        receipt_no = "7810946337325"

    reasons = get_confirm_rejection_reasons(_Row())
    assert "amount_inferred" in reasons
    assert "confirm_required" not in reasons
