"""Tests for Paygate receipt number extraction."""
from src.services.ocr.parsers.paygate_receipt import correct_paygate_receipt_digits, extract_paygate_receipt_no


def test_correct_paygate_receipt_digits_fixes_101_prefix():
    assert correct_paygate_receipt_digits("1010912457325") == "7810912457325"


def test_extract_paygate_receipt_no_accepts_101_misread():
    block = "レシート番号\n1010912457325\n決済方法\n現金"
    assert extract_paygate_receipt_no(block) == "7810912457325"
