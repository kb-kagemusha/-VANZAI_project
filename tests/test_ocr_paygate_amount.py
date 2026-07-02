"""Tests for Paygate amount OCR correction."""
from datetime import date
from decimal import Decimal

import pytest

from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_amount import (
    correct_yen_misread_amount,
    extract_paygate_amount,
    sanitize_paygate_amount,
)
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser


@pytest.mark.parametrize(
    ("raw", "expected", "corrected_from"),
    [
        ("980", Decimal("980"), None),
        ("2980", Decimal("980"), "2980"),
        ("5980", Decimal("980"), "5980"),
        ("7980", Decimal("980"), "7980"),
        ("1980", Decimal("980"), "1980"),
        ("1480", Decimal("1480"), None),
        ("4980", Decimal("980"), "4980"),
        ("２９８０", Decimal("980"), "2980"),
    ],
)
def test_sanitize_paygate_amount_corrects_yen_misread(raw, expected, corrected_from):
    amount, source = sanitize_paygate_amount(raw)
    assert amount == expected
    assert source == corrected_from


def test_extract_paygate_amount_infers_default_when_blue_text_missing():
    block = """2026/06/10
22:41:15
取引番号
1230601
レシート番号
7810988757330
決済方法
現金"""
    amount, meta = extract_paygate_amount(block, "22:41:15", has_transaction=True)
    assert amount == Decimal("980")
    assert meta["amount_inferred"] == "paygate_default_980"


def test_extract_paygate_amount_from_right_row_garbage():
    from src.services.ocr.models import OcrTextLine

    block = """2026/06/10
22:41:01
UBO!
取引番号
1230600"""
    lines = [
        OcrTextLine(text="2026/06/10", confidence=1.0, box=[[140, 250], [200, 250], [200, 270], [140, 270]]),
        OcrTextLine(text="22:41:01", confidence=1.0, box=[[280, 250], [340, 250], [340, 270], [280, 270]]),
        OcrTextLine(text="UBO!", confidence=0.7, box=[[700, 250], [760, 250], [760, 270], [700, 270]]),
    ]
    amount, meta = extract_paygate_amount(block, "22:41:01", lines, has_transaction=True)
    assert amount == Decimal("980")
    assert meta["amount_source"] == "fallback_default"


def test_extract_paygate_amount_from_production_like_block():
    block = """2026/06/10
22:41:01
2980
取引番号
1230600"""
    amount, meta = extract_paygate_amount(block, "22:41:01")
    assert amount == Decimal("980")
    assert meta["amount_corrected_from"] == "2980"


def test_paygate_screenshot_parser_corrects_misread_amounts():
    parser = PaygateScreenshotParser()
    for misread in ("2980", "7980"):
        text = f"""
2026/06/10
20:38:51
{misread}
取引番号
1230545
レシート番号
7810915317330
決済方法
現金
"""
        rows = parser.parse(run_ocr_from_text(text))
        assert len(rows) == 1
        assert rows[0].amount == Decimal("980")
        assert rows[0].raw_payload.get("amount_corrected_from") == misread


def test_paygate_screenshot_parser_keeps_valid_1480():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10
20:38:51
1480
取引番号
1230998
レシート番号
7810915317330
決済方法
現金
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].amount == Decimal("1480")
    assert rows[0].raw_payload.get("amount_corrected_from") is None


def test_paygate_image_consensus_fixes_date_and_amount_outliers():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10 21:30:33
1980
1230567
7810946337325
2026/06/10 20:52:59
980
1230557
7810923797325
2026/05/10 20:52:59
980
1230558
7810923797326
2025/06/10 20:34:05
980
1230543
7810912457325
2026/06/10 20:33:06
980
1230542
7810911867325
2026/06/10 19:48:28
980
1230501
7810885087325
2026/06/10 19:02:05
980
1230447
7810857257325
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) >= 5
    for row in rows:
        assert row.record_date == date(2026, 6, 10)
        assert row.amount == Decimal("980")
