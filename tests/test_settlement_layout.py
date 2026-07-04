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


def test_extract_settlement_datetime_handles_time_before_date_with_garbled_yen():
    text = """
端末識別番号:980
精算
23：04円16
2026/05/08
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 5, 8)
    assert record_time == "23:04:16"


def test_extract_settlement_datetime_handles_bracket_date_and_dash_time():
    text = """
端末識別番号:0ed7
精算
2026/06]29
23-07:13
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 6, 29)
    assert record_time == "23:07:13"


def test_extract_settlement_datetime_handles_hyphen_seconds_and_merged_month_day():
    text = """
端末識別番号:84e2
精算
2026/07101
23:02-59
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 7, 1)
    assert record_time == "23:02:59"


def test_extract_settlement_datetime_handles_split_year_line_and_partial_colon_time():
    text = """
端末識別番号:84e2
精算
2026
07/01
23:0259
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 7, 1)
    assert record_time == "23:02:59"


def test_extract_settlement_datetime_handles_compact_date_without_slashes():
    text = """
端末識別番号:636f
精算
20260629
23：04:47
端末番号
"""
    record_date, record_time = extract_settlement_datetime(text)
    assert record_date == date(2026, 6, 29)
    assert record_time == "23:04:47"
