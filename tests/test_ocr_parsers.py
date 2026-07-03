"""OCR parser and validation unit tests."""
from datetime import date
from decimal import Decimal

from src.services.ocr.dedupe import dedupe_paygate_screenshot_rows
from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.parsers.paygate_settlement import PaygateSettlementParser
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.validation import is_paygate_row_saveable, validate_parsed_row


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
2026/06/13 19:10:23
端末番号: 98f0ec2f-fc54-4e00-a503-2ecb6659c7be
端末識別番号: f353
小計 ¥8,820
合計 ¥8,820
現金売上 ¥6,860
-PAYGATE POS ¥1,960
通常取引数 9
消費税 ¥802
内税額 ¥802
"""


def test_paygate_screenshot_parser_skips_incomplete_rows():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10
123054
1010912457325
2026/06/10 19:48:28
980
1230501
7810885087325
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].transaction_no == "1230501"
    assert rows[0].receipt_no == "7810885087325"


def test_paygate_screenshot_parser_extracts_seven_complete_rows():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10 21:30:33
980
1230567
7810946337325
2026/06/10 20:52:59
980
1230557
7810923797325
2026/06/10 20:34:05
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
2026/06/10 19:01:20
980
1230445
7810856807325
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 7
    assert {row.transaction_no for row in rows} == {
        "1230567",
        "1230557",
        "1230543",
        "1230542",
        "1230501",
        "1230447",
        "1230445",
    }


def test_is_paygate_row_saveable_requires_core_fields():
    complete = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 6, 10),
        transaction_no="1230501",
        receipt_no="7810885087325",
    )
    incomplete = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 6, 10),
        transaction_no="123054",
        receipt_no="1010912457325",
    )
    assert is_paygate_row_saveable(complete) is True
    assert is_paygate_row_saveable(incomplete) is False

    corrected_receipt = ParsedOcrRow(
        source_type="paygate_screenshot",
        record_date=date(2026, 6, 10),
        transaction_no="1230543",
        receipt_no="7810912457325",
    )
    assert is_paygate_row_saveable(corrected_receipt) is True


def test_paygate_screenshot_parser_extracts_rows_without_labels():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10 19:48:28
1980
1230501
7810885087325
2026/06/10 19:02:05
1480
1230447
7810857257325
2026/06/10 19:01:20
980
1230445
7810856807325
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 3
    by_txn = {row.transaction_no: row for row in rows}
    assert by_txn["1230501"].amount == Decimal("980")
    assert by_txn["1230447"].amount == Decimal("1480")
    assert by_txn["1230445"].amount == Decimal("980")


def test_paygate_screenshot_parser_extracts_rows_without_yen_symbol():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10
20:38:51
980
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
    assert rows[0].transaction_no == "1230545"
    assert rows[0].receipt_no == "7810915317330"


def test_paygate_screenshot_parser_extracts_production_like_blocks():
    parser = PaygateScreenshotParser()
    text = """
2026/06/10
19:02:46
4980
取引番号
1230449
レシート番号
7810857657330
決済方法
ORコード
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].amount == Decimal("980")
    assert rows[0].transaction_no == "1230449"


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
    assert row.terminal_short_id == "f353"
    assert row.record_date == date(2026, 6, 13)
    assert row.record_time == "19:10:23"
    assert row.terminal_id.startswith("98f0")
    assert row.subtotal == Decimal("8820")
    assert row.amount == Decimal("8820")
    assert row.cash_sales == Decimal("6860")
    assert row.pos_sales == Decimal("1960")
    assert row.transaction_count == 9


def test_paygate_settlement_parser_extracts_labeled_settlement_datetime():
    parser = PaygateSettlementParser()
    text = """
精算
精算日 2026/06/14
精算時間 05:30:00
端末識別番号: f999
合計 ¥980
現金売上 ¥980
通常取引数 1
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].record_date == date(2026, 6, 14)
    assert rows[0].record_time == "05:30:00"


def test_paygate_settlement_parser_corrects_yen_misread_amounts():
    parser = PaygateSettlementParser()
    text = """
日本たばこ産業株式会社
精算
2026/07/02 23:05:23
登録番号
T4-0104-0102-3000
端末識別番号:0ed7
端末番号:
0ed777ad-eba8-46df-babd-d131c08d6e76
小計 15,880
合計 15,880
現金売上 15,880
PAYGATE POS 0
通常取引数 6
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    row = rows[0]
    assert row.terminal_short_id == "0ed7"
    assert row.terminal_id == "0ed777ad-eba8-46df-babd-d131c08d6e76"
    assert row.subtotal == Decimal("5880")
    assert row.amount == Decimal("5880")
    assert row.cash_sales == Decimal("5880")
    assert row.transaction_count == 6
    assert row.raw_payload.get("amount_corrections")


def test_paygate_settlement_parser_handles_split_terminal_uuid_and_loose_labels():
    """実レシート相当: UUID改行折返し・登録番号断片3000の誤検知防止・通常取引数の余白。"""
    parser = PaygateSettlementParser()
    text = """
日本たばこ産業株式会社
登録番号
T4-0104-0102-3000
端末識別番号:0ed7
精算
2026/07/02 23:05:23
端末番号:
0ed777ad-eba8-46df-babd-
d131c08d6e76
小計 5,880
合計 5,880
現金売上 5,880
 -PAYGATE POS 0
通常取引数        6
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    row = rows[0]
    assert row.terminal_short_id == "0ed7"
    assert row.terminal_id == "0ed777ad-eba8-46df-babd-d131c08d6e76"
    assert row.transaction_count == 6


def test_paygate_settlement_parser_rejects_registration_segment_as_short_id():
    parser = PaygateSettlementParser()
    text = """
精算
2026/07/02 23:05:23
登録番号
3000
小計 5,880
合計 5,880
現金売上 5,880
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].terminal_short_id is None


PRODUCTION_OCR_TEXT_260703_18 = """
1105-6927
登録番号
3000
14-0104-0102-
精算
2026/07/02
23:05:23
端末番号
- babd-
d131c08d6e76
小計
15,880
合計
15,880
現金売上
15,880
クレヅット売上
0
その他支払い
-PAYGATE
POS
0
-その他
10
消費税
534
-内税額
534
-外税額
返品計
取消計
20
通常取引数
0
"""


PRODUCTION_OCR_TEXT_260703_19 = """
日本たはこ産業株式会社
登録番号.
14-0104-0102-
3000
端末識別番号2C0e
精算
2026/07/0223:09:37
端末番号
1c0e8213-6cd5-
-4f9á-bc6a-
e0b50bfe1671
小計
15/880
合計
15880
現金売上
15880
通常取引数
6
"""


def test_paygate_settlement_parser_handles_production_ocr_text_260703_18():
    parser = PaygateSettlementParser()
    rows = parser.parse(run_ocr_from_text(PRODUCTION_OCR_TEXT_260703_18))
    assert len(rows) == 1
    row = rows[0]
    assert row.terminal_short_id is None
    assert row.terminal_id is None
    assert row.amount == Decimal("5880")
    assert row.subtotal == Decimal("5880")
    assert row.cash_sales == Decimal("5880")
    assert row.transaction_count == 6


def test_paygate_settlement_parser_handles_production_ocr_text_260703_19():
    parser = PaygateSettlementParser()
    rows = parser.parse(run_ocr_from_text(PRODUCTION_OCR_TEXT_260703_19))
    assert len(rows) == 1
    row = rows[0]
    assert row.terminal_short_id == "2c0e"
    assert row.terminal_id == "1c0e8213-6cd5-4f9a-bc6a-e0b50bfe1671"
    assert row.amount == Decimal("5880")
    assert row.subtotal == Decimal("5880")
    assert row.transaction_count == 6


def test_paygate_settlement_parser_ignores_zero_transaction_count_when_sales_exist():
    parser = PaygateSettlementParser()
    text = """
精算
精算日 2026/07/02
精算時間 23:05:23
合計 15,880
小計 15,880
現金売上 15,880
PAYGATE POS 0
通常取引数 0
"""
    rows = parser.parse(run_ocr_from_text(text))
    assert len(rows) == 1
    assert rows[0].amount == Decimal("5880")
    assert rows[0].transaction_count == 6
    assert "unit_breakdown_invalid" not in (rows[0].warnings or [])


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
