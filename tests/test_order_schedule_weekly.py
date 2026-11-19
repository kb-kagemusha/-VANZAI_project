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


# ---- 新しい「毎週」（曜日と祝日のボタン）。祝日はいつも上書き。旧データは旧規則のまま。 ----

HOLIDAYS = ["2027-01-01", "2027-01-11"]  # 金曜の祝日、月曜の祝日
PERIOD = {"from": "2027-01-01", "to": "2027-01-14"}


def v2_group(identifier, weekdays, *, holiday=False, start="09:00", end="17:00", period=PERIOD):
    return {"id": identifier, "date_mode": "weekly", **period, "weekdays": weekdays, "weekly_rule": "v2",
            "holiday_selected": holiday, "holiday_mode": "include", "holiday_dates": [d for d in HOLIDAYS if period["from"] <= d <= period["to"]],
            "holiday_review_from": period["from"], "holiday_review_to": period["to"], "start_time": start, "end_time": end}


def v2_schedule(*groups):
    rates = [{"id": "rate-" + g["id"], "work_group_id": g["id"], "date_mode": "range", "from": g["from"], "to": g["to"],
              "amount": {"a": "10000", "b": "12000", "c": "20000"}.get(g["id"], "9000")} for g in groups]
    return {"version": 1, "work_groups": list(groups), "rates_follow_work": True, "rate_groups": rates}


def day_map(schedule):
    return {entry["work_date"]: entry["work_group_id"] for entry in expand_work_days(schedule)}


def test_holiday_row_overrides_weekday_and_weekend_rows():
    value = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4]), v2_group("b", [5, 6]), v2_group("c", [], holiday=True)), complete=True)
    days = day_map(value)
    assert len(days) == 14
    assert days["2027-01-01"] == "c" and days["2027-01-11"] == "c"  # 平日の祝日も祝日の行
    assert days["2027-01-04"] == "a" and days["2027-01-02"] == "b" and days["2027-01-03"] == "b"
    assert value["work_groups"][0]["holiday_skip"] == HOLIDAYS
    # 稼働者の報酬も、祝日は祝日の行の単価
    holiday = SimpleNamespace(work_date=date(2027, 1, 11), work_group_id="c")
    assert _rate_for(value, holiday)["amount"] == "20000"
    assert "祝日" in schedule_text(value)[0]


def test_without_a_holiday_row_a_holiday_follows_its_weekday_row():
    value = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4]), v2_group("b", [5, 6])), complete=True)
    days = day_map(value)
    assert days["2027-01-01"] == "a" and days["2027-01-11"] == "a"
    assert value["work_groups"][0]["holiday_skip"] == []


def test_holiday_pressed_with_weekend_days_uses_that_row_on_weekday_holidays():
    value = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4]), v2_group("b", [5, 6], holiday=True)), complete=True)
    days = day_map(value)
    assert days["2027-01-11"] == "b" and days["2027-01-02"] == "b" and days["2027-01-12"] == "a"


def test_holiday_row_only_overrides_inside_its_own_period():
    inside = {"from": "2027-01-10", "to": "2027-01-14"}
    value = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4, 5, 6]), v2_group("c", [], holiday=True, period=inside)), complete=True)
    days = day_map(value)
    assert days["2027-01-01"] == "a"  # 祝日の行の期間外は曜日の行
    assert days["2027-01-11"] == "c"


def test_same_weekday_or_holiday_pressed_twice_is_rejected_before_saving():
    with pytest.raises(ValueError, match="重複"):
        normalize_schedule(v2_schedule(v2_group("a", [0, 1]), v2_group("b", [1, 2])))
    with pytest.raises(ValueError, match="重複"):
        normalize_schedule(v2_schedule(v2_group("a", [0], holiday=True), v2_group("b", [1], holiday=True)))
    # 期間が別なら同じ曜日でもよい
    other = {"from": "2027-01-08", "to": "2027-01-14"}
    first = {"from": "2027-01-01", "to": "2027-01-07"}
    normalize_schedule(v2_schedule(v2_group("a", [0], period=first), v2_group("b", [0], period=other)))


def test_row_without_weekday_or_holiday_cannot_be_confirmed():
    with pytest.raises(ValueError, match="曜日か祝日"):
        normalize_schedule(v2_schedule(v2_group("a", [])), complete=True)
    normalize_schedule(v2_schedule(v2_group("a", [])))  # 下書きの保存は止めない


def test_old_exclude_rows_keep_the_old_rule_and_stored_shape():
    value = normalize_schedule(weekly_schedule(), complete=True)
    for group in [*value["work_groups"], *value["rate_groups"]]:
        assert "weekly_rule" not in group and "holiday_skip" not in group
    assert day_map(value)["2027-01-01"] == "b"  # 旧規則：「祝日を除く」の行は祝日を稼働にせず、「含む」の行が取る


def test_pdf_text_shows_how_holidays_are_handled_for_each_row():
    from src.services.order_request_pdf import order_request_document_title, order_request_pdf_filename

    value = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4]), v2_group("b", [5, 6]), v2_group("c", [], holiday=True)), complete=True)
    dates, hours, fees = schedule_text(value)
    assert "毎週月・火・水・木・金（祝日を除く）" in dates and "毎週土・日（祝日を除く）" in dates
    assert "祝日（曜日に関係なく）" in dates and "祝日（曜日に関係なく）" in fees and "稼働：08:00～17:00" not in hours
    # 「祝日」の行がなければ、祝日は曜日の行の条件
    plain = normalize_schedule(v2_schedule(v2_group("a", [0, 1, 2, 3, 4]), v2_group("b", [5, 6])), complete=True)
    assert "毎週月・火・水・木・金（祝日も含む）" in schedule_text(plain)[0]
    # 見出し・ファイル名は、行ごとの長い表記ではなく全体の期間にまとめる
    title = order_request_document_title(work_date_label=dates, project_name="確認")
    assert "2027年1月1日～2027年1月14日：確認" in title and "毎週" not in title
    assert "毎週" not in order_request_pdf_filename(work_date_label=dates, project_name="確認")
    # 1日ごと・複数日の期間の見出しは今までどおり
    assert order_request_document_title(work_date_label="2027年3月1日 2027年3月3日", project_name="確認").endswith("2027年3月1日 2027年3月3日：確認")
