"""Tests for Paygate payment method normalization."""
from src.services.ocr.parsers.paygate_payment import normalize_paygate_payment_method


def test_normalize_paygate_payment_method_accepts_allowed_values():
    assert normalize_paygate_payment_method("現金") == "現金"
    assert normalize_paygate_payment_method("QRコード") == "QRコード"
    assert normalize_paygate_payment_method("クレジット") == "クレジット"


def test_normalize_paygate_payment_method_rejects_invalid_values():
    assert normalize_paygate_payment_method("現金売上") is None
    assert normalize_paygate_payment_method("その他") is None
    assert normalize_paygate_payment_method(None) is None
