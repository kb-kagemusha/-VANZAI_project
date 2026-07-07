"""Tests for Paygate payment method normalization and extraction."""
from src.services.ocr.models import OcrTextLine
from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr.parsers.paygate_payment import (
    PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE,
    extract_paygate_payment_method,
    normalize_paygate_payment_method,
    paygate_screenshot_has_payment_method_label,
)
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser


def test_normalize_paygate_payment_method_accepts_allowed_values():
    assert normalize_paygate_payment_method("現金") == "現金"
    assert normalize_paygate_payment_method("QRコード") == "QRコード"
    assert normalize_paygate_payment_method("クレジット") == "クレジット"


def test_normalize_paygate_payment_method_accepts_qr_ocr_variants():
    assert normalize_paygate_payment_method("QR コード") == "QRコード"
    assert normalize_paygate_payment_method("0Rコード") == "QRコード"
    assert normalize_paygate_payment_method("ORコード") == "QRコード"
    assert normalize_paygate_payment_method("ＱＲコード") == "QRコード"
    assert normalize_paygate_payment_method("QRコ一ド") == "QRコード"


def test_normalize_paygate_payment_method_rejects_invalid_values():
    assert normalize_paygate_payment_method("現金売上") is None
    assert normalize_paygate_payment_method("その他") is None
    assert normalize_paygate_payment_method(None) is None


def test_paygate_screenshot_has_payment_method_label():
    assert paygate_screenshot_has_payment_method_label("決済方法 現金")
    assert paygate_screenshot_has_payment_method_label("決 済 方 法\nQRコード")
    assert paygate_screenshot_has_payment_method_label("決消方法 現金")
    assert not paygate_screenshot_has_payment_method_label("取引番号 1154100")
    assert not paygate_screenshot_has_payment_method_label("")
    assert PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE.startswith("正しいPaygate")


def test_extract_paygate_payment_method_from_split_lines():
    block = """
2026/07/02 20:44:00
取引番号 1281155
レシート番号 7829926397319
決済方法
QRコード
"""
    assert extract_paygate_payment_method(block) == "QRコード"


def test_extract_paygate_payment_method_from_ocr_label_typo():
    block = """
2026/07/02 20:44:00
取引番号 1281155
レシート番号 7829926397319
決消方法
0Rコード
"""
    assert extract_paygate_payment_method(block) == "QRコード"


def test_extract_paygate_payment_method_from_block_scan_when_not_adjacent():
    block = """
2026/07/02 20:44:00
取引番号 1281155
レシート番号 7829926397319
決済方法
2026/07/02 20:38:23
QRコード
"""
    assert extract_paygate_payment_method(block) == "QRコード"


def test_extract_paygate_payment_method_from_spatial_lines():
    block = """
2026/07/02 20:44:00
取引番号 1281155
レシート番号 7829926397319
決済方法
2026/07/02 20:38:23
QRコード
"""
    lines = [
        OcrTextLine(text="2026/07/02 20:44:00", confidence=0.99, box=[[10, 10], [200, 10], [200, 30], [10, 30]]),
        OcrTextLine(text="取引番号", confidence=0.99, box=[[10, 40], [80, 40], [80, 60], [10, 60]]),
        OcrTextLine(text="1281155", confidence=0.99, box=[[220, 40], [320, 40], [320, 60], [220, 60]]),
        OcrTextLine(text="レシート番号", confidence=0.99, box=[[10, 70], [120, 70], [120, 90], [10, 90]]),
        OcrTextLine(text="7829926397319", confidence=0.99, box=[[220, 70], [360, 70], [360, 90], [220, 90]]),
        OcrTextLine(text="決済方法", confidence=0.99, box=[[10, 100], [90, 100], [90, 120], [10, 120]]),
        OcrTextLine(text="QRコード", confidence=0.95, box=[[250, 100], [340, 100], [340, 120], [250, 120]]),
        OcrTextLine(text="2026/07/02 20:38:23", confidence=0.99, box=[[10, 130], [200, 130], [200, 150], [10, 150]]),
    ]
    assert extract_paygate_payment_method(block, lines) == "QRコード"


def test_paygate_screenshot_parser_extracts_qr_payment_method():
    parser = PaygateScreenshotParser()
    text = """
2026/07/02 20:44:00
¥980
取引番号 1281155
レシート番号 7829926397319
決済方法
QRコード
2026/07/02 20:38:23
¥980
取引番号 1281152
レシート番号 7829923037319
決済方法 現金
"""
    rows = parser.parse(run_ocr_from_text(text))
    by_txn = {row.transaction_no: row for row in rows}
    assert by_txn["1281155"].payment_method == "QRコード"
    assert by_txn["1281152"].payment_method == "現金"


def test_paygate_screenshot_parser_keeps_qr_when_prior_row_cash_bleeds_into_block():
    """Regression: partial prior row + wide receipt block must not overwrite QR with 現金."""
    parser = PaygateScreenshotParser()
    text = """
決済方法
現金
2026/07/02 20:44:00
980
取引番号 1281155
レシート番号 7829926397319
決済方法
QRコード
2026/07/02 20:38:23
980
取引番号 1281152
レシート番号 7829923037319
決済方法
現金
"""
    rows = parser.parse(run_ocr_from_text(text))
    by_txn = {row.transaction_no: row for row in rows}
    assert by_txn["1281155"].payment_method == "QRコード"
    assert by_txn["1281152"].payment_method == "現金"


def test_extract_paygate_payment_method_prefers_qr_over_later_cash_in_region():
    block = """
2026/07/02 20:44:00
取引番号 1281155
決済方法
2026/07/02 20:38:23
QRコード
現金
"""
    assert extract_paygate_payment_method(block, transaction_no="1281155") == "QRコード"


def test_payment_method_confidence_uses_paired_value_line_not_other_rows():
    from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
    from src.services.ocr.parsers.ocr_field_confidence import build_paygate_screenshot_field_confidence

    block = """
2026/07/02 20:44:00
取引番号 1281155
決済方法
QRコード
2026/07/02 20:38:23
決済方法
現金
"""
    lines = [
        OcrTextLine(text="決済方法", confidence=0.99, box=[[10, 100], [90, 100], [90, 120], [10, 120]]),
        OcrTextLine(text="QRコード", confidence=0.88, box=[[250, 100], [340, 100], [340, 120], [250, 120]]),
        OcrTextLine(text="決済方法", confidence=0.99, box=[[10, 130], [90, 130], [90, 150], [10, 150]]),
        OcrTextLine(text="現金", confidence=0.99, box=[[250, 130], [300, 130], [300, 150], [250, 150]]),
    ]
    ocr = OcrEngineResult(lines=lines, full_text="\n".join(line.text for line in lines))
    parsed = ParsedOcrRow(
        source_type="paygate_screenshot",
        transaction_no="1281155",
        payment_method="QRコード",
        raw_payload={"block": block},
    )
    field_confidence, field_sources = build_paygate_screenshot_field_confidence(ocr, parsed)
    assert field_confidence["payment_method"] == 0.88
    assert field_sources["payment_method"] == "ocr_line_direct"

    parsed_wrong = ParsedOcrRow(
        source_type="paygate_screenshot",
        transaction_no="1281155",
        payment_method="現金",
        raw_payload={"block": block},
    )
    wrong_conf, wrong_source = build_paygate_screenshot_field_confidence(ocr, parsed_wrong)
    assert wrong_conf["payment_method"] < 0.85
    assert wrong_source["payment_method"] == "ocr_inferred"
