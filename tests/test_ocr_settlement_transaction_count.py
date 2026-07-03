"""Tests for settlement receipt 通常取引数 extraction."""
from src.services.ocr.parsers.settlement_transaction_count import (
    extract_transaction_count_before_cash_blank,
)


def test_extract_count_from_line_before_settlement_cash_blank():
    text = """
返品計 ¥0
取消計 ¥0
通常取引数 8
精算現金
-1万円札 (0枚) ¥0
"""
    assert extract_transaction_count_before_cash_blank(text) == 8


def test_extract_count_when_label_and_value_are_split():
    text = """
取消計
0
通常取引数
8
精算現金
-500円玉 (0枚)
"""
    assert extract_transaction_count_before_cash_blank(text) == 8


def test_extract_count_uses_cash_breakdown_when_cash_header_missing():
    text = """
通常取引数
6
-1万円札 (0枚) ¥0
"""
    assert extract_transaction_count_before_cash_blank(text) == 6


def test_extract_count_returns_none_without_blank_marker():
    text = """
通常取引数
0
"""
    assert extract_transaction_count_before_cash_blank(text) is None
