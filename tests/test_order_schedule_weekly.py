"""Weekly order groups must select one rate for each actual work day."""
import copy
from datetime import date
from types import SimpleNamespace

import pytest

from src.domain.order_schedule import expand_work_days, normalize_schedule, schedule_text
from src.services.line_worker_portal import _rate_for


def weekly_schedule():
    holiday = ["2027-01-01", "2027-01-11"]
    groups = [
        {"id": "a", "date_mode": "weekly", "from": "2027-01-01", "to": "2027-01-14",
         "weekdays": [0, 1, 2, 3, 4, 5], "holiday_mode": "exclude", "holiday_dates": holiday, "holiday_review_from": "2027-01-01", "holiday_review_to": "2027-01-14",
         "start_time": "09:00", "end_time": "17:00"},
        {"id": "b", "date_mode": "weekly", "from": "2027-01-01", "to": "2027-01-14",
         "weekdays": [6], "holiday_mode": "include", "holiday_dates": holiday, "holiday_review_from": "2027-01-01", "holiday_review_to": "2027-01-14",
         "start_time": "08:00", "end_time": "19:00"},
    ]
    rates = [{"id": "rate-" + group["id"], "work_group_id": group["id"],
              "date_mode": "range", "from": group["from"], "to": group["to"],
              "amount": "10000" if group["id"] == "a" else "15000"} for group in groups]
    return {"version": 1, "work_groups": groups, "rates_follow_work": True, "rate_groups": rates}


def test_weekly_groups_expand_holidays_and_linked_rates_without_overlap():
    value = normalize_schedule(weekly_schedule(), complete=True)
    days = {entry["work_date"]: entry for entry in expand_work_days(value)}
    assert len(days) == 14
    assert days["2027-01-11"]["work_group_id"] == "b"  # Monday holiday
    assert days["2027-01-10"]["work_group_id"] == "b"  # Sunday
    assert days["2027-01-12"]["work_group_id"] == "a"
    assert value["rate_groups"][1]["holiday_dates"] == ["2027-01-01", "2027-01-11"]
    assert "祝日を含む" in schedule_text(value)[2]


def test_weekly_overlap_is_rejected_and_independent_rates_not_yet_supported():
    value = weekly_schedule()
    value["work_groups"][1]["weekdays"].append(0)
    with pytest.raises(ValueError, match="重複"):
        normalize_schedule(value)
    value = copy.deepcopy(weekly_schedule())
    value["rates_follow_work"] = False
    for rate in value["rate_groups"]:
        rate["work_group_id"] = None
    with pytest.raises(ValueError, match="単価を稼働日に"):
        normalize_schedule(value)


def test_worker_pay_uses_the_holiday_rate_for_a_weekday_holiday():
    schedule = normalize_schedule(weekly_schedule(), complete=True)
    holiday = SimpleNamespace(work_date=date(2027, 1, 11), work_group_id="b")
    weekday = SimpleNamespace(work_date=date(2027, 1, 12), work_group_id="a")
    assert _rate_for(schedule, holiday)["amount"] == "15000"
    assert _rate_for(schedule, weekday)["amount"] == "10000"
