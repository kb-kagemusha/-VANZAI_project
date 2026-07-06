"""Tests for Paygate payment method normalization."""
from src.services.ocr.parsers.paygate_payment import (
    PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE,
    normalize_paygate_payment_method,
    paygate_screenshot_has_payment_method_label,
)


def test_normalize_paygate_payment_method_accepts_allowed_values():
    assert normalize_paygate_payment_method("現金") == "現金"
    assert normalize_paygate_payment_method("QRコード") == "QRコード"
    assert normalize_paygate_payment_method("クレジット") == "クレジット"


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
