"""Date/rate grouping and document preservation without modifying settled payroll."""
import copy
import json
import pytest
from src.domain.order_schedule import normalize_schedule, schedule_text
from src.services.order_request_format import apply_template_fields, parse_sections


def schedule():
    work = [
        {"id": "day1", "date_mode": "single", "from": "2027-03-01", "to": "2027-03-01", "start_time": "08:00", "end_time": "17:00", "notes": "初日準備"},
        {"id": "rest", "date_mode": "range", "from": "2027-03-02", "to": "2027-03-10", "start_time": "09:00", "end_time": "17:00"},
    ]
    rates = [{"id": f"rate-{w['id']}", "work_group_id": w["id"], "date_mode": w["date_mode"], "from": w["from"], "to": w["to"], "amount": "20500" if i == 0 else "19500", "unit": "day"} for i, w in enumerate(work)]
    return {"version": 1, "work_groups": work, "rates_follow_work": True, "rate_groups": rates}


def test_daily_and_range_snapshot_roundtrip_and_canonical_body():
    raw = {"format": "additional-request-v1", "project_name": "イベント", "hours": "誤った時間", "fee": "誤った単価", "schedule": schedule(), "previous_hours": "旧勤務条件"}
    conditions, body = apply_template_fields(json.dumps(raw), "client supplied body", work_date_label="client supplied dates", site_name="会場")
    stored = parse_sections(conditions)
    assert stored["schedule"]["rate_groups"][0]["lunch_included"] is True
    assert stored["previous_hours"] == "旧勤務条件"
    assert "08:00～17:00" in body and "09:00～17:00" in body
    assert "2027年3月2日～2027年3月10日" in body and "¥20,500" in body
    assert "誤った" not in body


@pytest.mark.parametrize("changes", [
    {"from": "2027-03-01"}, {"to": "2027-02-01"}, {"from": "2027-02-30"}, {"end_time": "08:30"}, {"start_time": "25:00"},
])
def test_invalid_or_overlapping_dates_and_times_rejected(changes):
    value = schedule()
    value["work_groups"][1].update(changes)
    with pytest.raises(ValueError): normalize_schedule(value)


def test_linked_prices_follow_ids_and_sort_chronologically():
    value = schedule()
    value["work_groups"][0]["from"] = "2027-02-28"
    value["work_groups"].reverse()
    normalized = normalize_schedule(value, complete=True)
    assert normalized["rate_groups"][0]["work_group_id"] == "day1"
    assert normalized["rate_groups"][0]["from"] == "2027-02-28"
    assert normalized["rate_groups"][0]["amount"] == "20500"


def test_overnight_work_requires_explicit_next_day():
    value = schedule()
    value["work_groups"][0].update(start_time="22:00", end_time="06:00")
    with pytest.raises(ValueError): normalize_schedule(value)
    value["work_groups"][0]["end_next_day"] = True
    assert "22:00～翌日 06:00" in schedule_text(normalize_schedule(value))[1]


def test_extra_allowance_needs_notes_on_confirmation_and_keeps_notes():
    value = schedule()
    value["rate_groups"][0].update(transport_included=False)
    normalize_schedule(value)  # incomplete drafts may be saved
    with pytest.raises(ValueError, match="交通費"): normalize_schedule(value, complete=True)
    value["rate_groups"][0]["transport_note"] = "実費、上限1,000円"
    result = normalize_schedule(value, complete=True)
    assert "交通費：別途（実費、上限1,000円）" in schedule_text(result)[2]


@pytest.mark.parametrize("amount", ["-1", "1.234", "NaN", "1e3", "1,000"])
def test_invalid_money_rejected(amount):
    value = schedule(); value["rate_groups"][0]["amount"] = amount
    with pytest.raises(ValueError): normalize_schedule(value)


def test_separate_price_periods_must_cover_working_days():
    value = schedule(); value["rates_follow_work"] = False
    for r in value["rate_groups"]: r["work_group_id"] = None
    value["rate_groups"][1]["to"] = "2027-03-09"
    normalize_schedule(value)
    with pytest.raises(ValueError, match="単価が設定されていない"): normalize_schedule(value, complete=True)


def test_legacy_text_untouched():
    assert apply_template_fields("旧依頼条件", "旧本文", work_date_label="3/1", site_name="会場") == ("旧依頼条件", "旧本文")


def test_duplicate_ids_or_missing_linked_price_rejected():
    for invalid in ("duplicate", "missing"):
        value = schedule()
        if invalid == "duplicate": value["work_groups"][1]["id"] = "day1"
        else: value["rate_groups"].pop()
        with pytest.raises(ValueError): normalize_schedule(value)
