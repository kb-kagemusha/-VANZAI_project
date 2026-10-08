"""Tests for the settlement work_date (稼働日) resolution rule (深夜またぎ)."""
from datetime import date

from src.services.ocr.work_date import compute_work_date


def test_before_cutoff_uses_previous_day():
    assert compute_work_date(date(2026, 6, 14), "05:30:00") == date(2026, 6, 13)


def test_exactly_at_cutoff_uses_same_day():
    assert compute_work_date(date(2026, 6, 14), "06:00:00") == date(2026, 6, 14)


def test_after_cutoff_uses_same_day():
    assert compute_work_date(date(2026, 6, 13), "19:10:23") == date(2026, 6, 13)


def test_missing_record_date_returns_none():
    assert compute_work_date(None, "19:10:23") is None


def test_missing_record_time_falls_back_to_record_date():
    assert compute_work_date(date(2026, 6, 13), None) == date(2026, 6, 13)
