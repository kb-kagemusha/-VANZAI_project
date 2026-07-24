"""Tests for fuzzy Paygate datetime parsing."""
from datetime import date

from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_datetime import extract_fuzzy_datetime, parse_fuzzy_time
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser

FAILED_IMAGE_TEXT = """
取引ー覧
取引番号
1230567
レシート番号
7810946337325
2026/06/10
20:521
取引番号
1230557
レシート番号
7810923797325
2026/06/10
2034:01
取引番号
1230543
レシート番号
7810912457325
2026,06/10
2033:0.
"""


def test_parse_fuzzy_time_variants():
    assert parse_fuzzy_time("20:52:59") == "20:52:59"
    assert parse_fuzzy_time("2034:01") == "20:34:01"
    assert parse_fuzzy_time("20:521") == "20:52:1"
    assert parse_fuzzy_time("2130:33") == "21:30:33"


def test_parser_extracts_rows_from_failed_image_text():
    rows = PaygateScreenshotParser().parse(run_ocr_from_text(FAILED_IMAGE_TEXT))
    assert len(rows) >= 3
    txn_numbers = {row.transaction_no for row in rows}
    assert "1230567" in txn_numbers
    assert "1230557" in txn_numbers
    assert rows[0].amount is not None


def test_extract_fuzzy_datetime_from_noisy_block():
    block = "2026/06/10\n2034:01\n取引番号\n1230557"
    record_date, record_time = extract_fuzzy_datetime(block)
    assert record_date == date(2026, 6, 10)
    assert record_time == "20:34:01"
