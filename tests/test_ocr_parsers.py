"""OCR parser and validation unit tests."""
from datetime import date
from decimal import Decimal

from src.services.ocr.dedupe import dedupe_paygate_screenshot_rows
from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.parsers.paygate_settlement import PaygateSettlementParser
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.validation import validate_parsed_row


PAYGATE_SCREENSHOT_TEXT = """
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
決済方法 現金
2026/05/08 22:20:36
¥980
取引番号 1154098
レシート番号 7782464367325
決済方法 現金
"""

SETTLEMENT_TEXT = """
日本たばこ産業株式会社
精算
2026/05/08 23:04:16
端末番号: 98f0ec2f-fc54-4e00-a503-2ecb6659c7be
小計 ¥10,780
合計 ¥10,780
現金売上 ¥10,780
クレジット売上 ¥0
通常取引数 11
消費税 ¥979
内税額 ¥979
"""


def test_paygate_screenshot_parser_extracts_rows():
    parser = PaygateScreenshotParser()
    rows = parser.parse(run_ocr_from_text(PAYGATE_SCREENSHOT_TEXT))
    assert len(rows) == 2
    assert rows[0].transaction_no == "1154100"
    assert rows[0].receipt_no == "7782464677325"
    assert rows[0].amount == Decimal("980")
    assert rows[0].period_key == "202605"


def test_paygate_settlement_parser_extracts_summary():
    parser = PaygateSettlementParser()
    rows = parser.parse(run_ocr_from_text(SETTLEMENT_TEXT))
    assert len(rows) == 1
    row = rows[0]
    assert row.amount == Decimal("10780")
    assert row.transaction_count == 11
    assert row.cash_sales == Decimal("10780")
    assert row.terminal_id.startswith("98f0")


def test_validate_parsed_row_flags_missing_date():
    row = ParsedOcrRow(source_type="paygate_screenshot", amount=Decimal("980"))
    errors = validate_parsed_row(row)
    assert "record_date is missing" in errors


def test_paygate_screenshot_dedupe_keeps_complete_row():
    parser = PaygateScreenshotParser()
    text = """
2026/05/08 22:21:07
¥980
取引番号 1154100
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
決済方法 現金
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].transaction_no == "1154100"
    assert rows[0].receipt_no == "7782464677325"
    assert rows[0].payment_method == "現金"


def test_paygate_screenshot_dedupe_by_receipt_no():
    partial = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 5, 8),
        record_time="22:21:07",
        amount=Decimal("980"),
        transaction_no="1154099",
        raw_payload={"block": "partial"},
    )
    complete = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 5, 8),
        record_time="22:21:07",
        amount=Decimal("980"),
        transaction_no="1154100",
        receipt_no="7782464677325",
        payment_method="現金",
        raw_payload={"block": "complete row with receipt and payment method"},
    )
    duplicate = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 5, 8),
        record_time="22:21:07",
        amount=Decimal("980"),
        transaction_no="1154100",
        receipt_no="7782464677325",
        raw_payload={"block": "duplicate"},
    )
    deduped, skipped = dedupe_paygate_screenshot_rows([partial, complete, duplicate])
    assert skipped == 1
    assert len(deduped) == 2
    kept = next(row for row in deduped if row.transaction_no == "1154100")
    assert kept.receipt_no == "7782464677325"
    assert kept.payment_method == "現金"
