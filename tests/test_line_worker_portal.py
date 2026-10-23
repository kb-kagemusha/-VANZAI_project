"""稼働者向けのWeb確認画面（統合計画 ②、DEC-084）：月間・直近7日の予定、確認が必要な依頼、報酬見込み、受託済みの依頼書。"""
from __future__ import annotations

import json
from datetime import date, timedelta

from src.models.line_daily import WorkerScheduleEntry
from src.services import worker_schedule as ws
from src.services.line_worker_portal import estimate_for, parse_month
from tests.test_api_line_order_requests import (  # noqa: F401  （fixture の再利用）
    FakeLine,
    _auth,
    _link,
    _worker,
    fake_line,
    line_env,
    ops_user,
    pdf_root,
)
from tests.test_line_daily import _create_confirm, _day, _payload, _release, _revise_confirm, _schedule, _send_and_accept
from tests.test_line_worker_pick import _session, liff_env  # noqa: F401

ALL = ("wk_wake", "wk_orders", "wk_schedule", "pick_dates", "web_home", "web_orders")


def _month_of(offset: int) -> str:
    return _day(offset)[:7]


def _days_in_month(offsets, month: str) -> int:
    return sum(1 for o in offsets if _day(o).startswith(month))


def test_home_requires_web_home_feature(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _release(db_session, actions=("wk_wake", "pick_dates"))
    headers = _session(api_client)
    response = api_client.get("/api/line/worker/home", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "feature_off"
    assert api_client.get("/api/line/worker/orders", headers=headers).status_code == 403
    assert api_client.get("/api/line/worker/home").status_code == 401


def test_home_shows_month_week_estimate_and_confirmations(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    accepted = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(0, 2))
    _send_and_accept(api_client, ops_user, accepted["deliveries"][0]["id"])
    # 未回答の依頼（送付済み・返事なし）は予定にも見込みにも入らない
    pending = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(10, 11), project="未回答の案件")
    sent = api_client.post(f"/api/order-requests/deliveries/{pending['deliveries'][0]['id']}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    _release(db_session, actions=ALL)
    headers = _session(api_client)

    month = _month_of(0)
    home = api_client.get("/api/line/worker/home", params={"month": month}, headers=headers)
    assert home.status_code == 200, home.text
    body = home.json()
    assert body["month"] == month and body["worker_name"] == "稼働者A"
    expected_days = _days_in_month((0, 1, 2), month)
    assert len(body["month_days"]) == expected_days
    assert body["estimate"]["work_days"] == expected_days
    assert body["estimate"]["amount"] == str(15000 * expected_days)
    assert body["estimate"]["excluded_hourly"] == 0 and body["estimate"]["excluded_unknown"] == 0
    # 直近7日は月と関係なく今日から6日後まで
    assert body["week"]["from"] == _day(0) and body["week"]["to"] == _day(6)
    assert [d["date"] for d in body["week"]["days"]] == [_day(0), _day(1), _day(2)]
    entry = body["week"]["days"][0]["entries"][0]
    assert entry["project_name"] == "駅前イベント" and entry["start_time"] == "09:00" and entry["meeting_place"] == "北口改札"
    kinds = [(c["kind"], c["project_name"]) for c in body["confirmations"]]
    assert kinds == [("unanswered", "未回答の案件")]
    assert body["confirmations"][0]["offered_days"] == 2
    assert body["orders_enabled"] is True


def test_revision_shows_changing_and_keeps_old_estimate(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 2))
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    schedule = _schedule(1, 2)
    schedule["rate_groups"][0]["amount"] = "16000"
    conditions = json.loads(_payload([worker.id], schedule=schedule)["request_conditions"])
    v2 = _revise_confirm(api_client, ops_user, v1["id"], request_conditions=json.dumps(conditions))
    sent = api_client.post(f"/api/order-requests/deliveries/{v2['deliveries'][0]['id']}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    month = _month_of(1)
    body = api_client.get("/api/line/worker/home", params={"month": month}, headers=headers).json()
    assert [c["kind"] for c in body["confirmations"]] == ["changing"]
    days = _days_in_month((1, 2), month)
    assert body["estimate"]["amount"] == str(15000 * days)  # 新しい版を受諾するまでは旧い版の単価
    assert all(e["changing"] for d in body["month_days"] for e in d["entries"])

    orders = api_client.get("/api/line/worker/orders", headers=headers).json()["items"]
    assert len(orders) == 1 and orders[0]["changing"] is True
    assert orders[0]["newer_delivery_id"] == v2["deliveries"][0]["id"]


def test_test_documents_are_shown_but_not_counted(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_confirm(api_client, ops_user, [worker.id], kind="test", schedule=_schedule(1, 1))
    _send_and_accept(api_client, ops_user, version["deliveries"][0]["id"])
    _release(db_session, actions=ALL)
    body = api_client.get("/api/line/worker/home", params={"month": _month_of(1)}, headers=_session(api_client)).json()
    assert body["month_days"][0]["entries"][0]["is_test"] is True
    assert body["estimate"]["amount"] is None and body["estimate"]["work_days"] == 0
    # テストの分は正式に混ぜず、別に返す（画面では【テスト】として表示）
    assert body["estimate"]["test"]["amount"] == "15000" and body["estimate"]["test"]["work_days"] == 1


def test_pdf_link_only_for_own_delivery(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    other = _worker(db_session, "稼働者B")
    _link(api_client, ops_user, worker.id, "U123")
    _link(api_client, ops_user, other.id, "U999")
    mine = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 1))
    _send_and_accept(api_client, ops_user, mine["deliveries"][0]["id"])
    theirs = _create_confirm(api_client, ops_user, [other.id], schedule=_schedule(1, 1))
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    ok = api_client.post(f"/api/line/worker/deliveries/{mine['deliveries'][0]['id']}/pdf-link", headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["url"].startswith("https://api.example.test/api/line/order-request-files/")
    denied = api_client.post(f"/api/line/worker/deliveries/{theirs['deliveries'][0]['id']}/pdf-link", headers=headers)
    assert denied.status_code == 404


def test_month_parameter_is_validated():
    today = date(2026, 10, 23)
    assert parse_month(None, today) == date(2026, 10, 1)
    assert parse_month("2026-12", today) == date(2026, 12, 1)
    for bad in ("2026-13", "2026-1", "abc", "2030-01"):
        try:
            parse_month(bad, today)
        except Exception as exc:  # noqa: BLE001
            assert getattr(exc, "status_code", None) == 400
        else:
            raise AssertionError(bad)


def test_estimate_excludes_hourly_and_unknown_and_floors_yen(db_session):
    class FakeVersion:
        pass

    def entry(version_id, day, group="g1", is_test=False):
        return WorkerScheduleEntry(id=f"{version_id}-{day}", series_id="s", document_id="d", version_id=version_id, delivery_id="x",
            worker_id="w", work_group_id=group, work_date=day, status="active", is_test=is_test)

    from src.services import line_worker_portal as portal

    schedules = {
        "daily": {"rate_groups": [{"work_group_id": "g1", "from": "2026-11-01", "to": "2026-11-30", "amount": "15000.50", "unit": "day", "lunch_included": True, "transport_included": False}]},
        "hourly": {"rate_groups": [{"work_group_id": "g1", "from": "2026-11-01", "to": "2026-11-30", "amount": "1200", "unit": "hour"}]},
        "blank": {"rate_groups": [{"work_group_id": "g1", "from": "2026-11-01", "to": "2026-11-30", "amount": "", "unit": "day"}]},
    }
    original_get = db_session.get
    original_sections = ws._version_sections
    try:
        db_session.get = lambda model, key: key  # noqa: E731
        ws._version_sections = lambda key: {"schedule": schedules[key]}
        rows = [entry("daily", date(2026, 11, 1)), entry("daily", date(2026, 11, 2)), entry("hourly", date(2026, 11, 2)),
            entry("blank", date(2026, 11, 3)), entry("daily", date(2026, 11, 4), is_test=True)]
        result = portal.estimate_for(db_session, rows)
    finally:
        db_session.get = original_get
        ws._version_sections = original_sections
    assert result["amount"] == "30001"  # 15000.50×2 = 30001.00 → 円未満切り捨て
    assert result["work_days"] == 3  # 11/1・11/2・11/3（同じ日の2件は1日。テストは数えない）
    assert result["excluded_hourly"] == 1 and result["excluded_unknown"] == 1
    assert result["separate_cost"] is True
    assert result["test"]["amount"] == "15000" and result["test"]["work_days"] == 1  # 15000.50 → 切り捨て
