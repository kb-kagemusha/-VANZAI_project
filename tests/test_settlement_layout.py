from datetime import date

from src.services.ocr.parsers.settlement_layout import extract_settlement_datetime

PRODUCTION_OCR_TEXT_260703_15_GARBLED = """
1番号:0021
202607/02
23:01:45
岡末善号
Ob21ee3e-0e48
4750-8246-7
小計
8,820
合計
8,820
現金売上
7,840
通常取引数
9
"""


def test_extract_settlement_datetime_handles_merged_slash_date_and_next_line_time():
    record_date, record_time = extract_settlement_datetime(PRODUCTION_OCR_TEXT_260703_15_GARBLED)
    assert record_date == date(2026, 7, 2)
    assert record_time == "23:01:45"


def test_extract_settlement_datetime_handles_split_lines_after_settlement_title():
    text = """
精算
2026/07/02
23:05:23
端末番号
0ed777ad-eba8-
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 7, 2)
    assert record_time == "23:05:23"


def test_extract_settlement_datetime_handles_compact_time_line():
    text = """
端末識別番号:0b21
2026/07/02
230145
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 7, 2)
    assert record_time == "23:01:45"
