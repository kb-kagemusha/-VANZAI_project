"""③-B／③-C 結合試験：Web確認画面から「新しい版を辞退」したとき、始まっていた日を残す（統合計画 v1.2、結合試験の段取り §2・§3）。

担当：③-C側が用意した試験を③-Bの共通修正で検証。5件のXPASS(strict)を確認後、WAITING_3Bを解除した。
固定時計を進めても勤務日と期待値が動かないよう、元の基準日を保存している。
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

import pytest

from src.models.transaction import AuditLog
from src.models.order_request import ACK_DECLINED, OrderRequestDelivery, OrderRequestVersion
from src.services import worker_schedule as ws
from src.services.line_worker import reply_notice_key
from tests.test_api_line_order_requests import (  # noqa: F401  （fixture の再利用）
    FakeLine,
    _auth,
    _link,
    _webhook,
    _worker,
    fake_line,
    line_env,
    ops_user,
    pdf_root,
)
from tests.test_line_daily import _create_confirm, _day, _entries, _payload, _postback, _release, _revise_confirm, _schedule, _send_and_accept
from tests.test_line_worker_pick import _session, liff_env  # noqa: F401
from tests.test_line_worker_reply import ALL, _recorder, _reply



@pytest.fixture(autouse=True)
def _fixed_base_day(monkeypatch):
    # today_jstを動かした後も、元の勤務日と期待値の基準日は動かさない。
    import sys
    base = ws.today_jst()
    monkeypatch.setattr(sys.modules[__name__], "_day", lambda offset: (base + timedelta(days=offset)).isoformat())


def _night_schedule(first: int, last: int) -> dict:
    """22:00〜翌06:00 の夜勤。勤務日は開始日で数える（split_started の約束）。"""
    work = [{
        "id": "g1", "date_mode": "range", "from": _day(first), "to": _day(last),
        "start_time": "22:00", "end_time": "06:00", "end_next_day": True, "excluded_dates": [],
    }]
    rates = [{"id": "r1", "work_group_id": "g1", "date_mode": "range", "from": _day(first), "to": _day(last), "amount": "18000", "unit": "day"}]
    return {"version": 1, "work_groups": work, "rates_follow_work": True, "rate_groups": rates}


def _with_rate(schedule: dict, amount: str) -> dict:
    changed = json.loads(json.dumps(schedule))
    for rate in changed["rate_groups"]:
        rate["amount"] = amount
    return changed


def _set_clock(monkeypatch, day_offset: int, hour: int, minute: int = 0) -> datetime:
    """日本時間の固定時計（作り直し・始まった日の判定・画面の「今日」）。"""
    day = date.fromisoformat(_day(day_offset))
    moment = datetime.combine(day, time(hour, minute), tzinfo=ws.JST)
    monkeypatch.setattr(ws, "now_utc", lambda: moment.astimezone(timezone.utc))
    monkeypatch.setattr(ws, "today_jst", lambda: day)
    return moment


def _accepted_then_new_version_sent(api_client, db_session, ops_user, worker, schedule):
    """旧版を受諾 → 単価だけ変えた新しい版を確定・送付（日付は同じ）。新しい版の送付行IDを返す。"""
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=schedule)
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    conditions = json.loads(_payload([worker.id], schedule=_with_rate(schedule, "16000"))["request_conditions"])
    v2 = _revise_confirm(api_client, ops_user, v1["id"], request_conditions=json.dumps(conditions))
    new_delivery = v2["deliveries"][0]["id"]
    sent = api_client.post(f"/api/order-requests/deliveries/{new_delivery}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    rows = _entries(db_session, worker.id)
    assert rows and {r.status for r in rows if r.version_id == v1["id"]} == {"changing"}  # 前提：◆の状態
    return v1, v2, new_delivery


def _live_dates(db_session, worker_id) -> list[str]:
    return sorted(r.work_date.isoformat() for r in _entries(db_session, worker_id) if r.status in ("active", "changing"))


def _snapshot(db_session, worker_id) -> list[tuple]:
    return [(r.work_date.isoformat(), r.version_id, r.status, r.status_reason) for r in _entries(db_session, worker_id)]


def _rebuild_twice(db_session, series_id, worker_id):
    for _ in range(2):
        ws.rebuild(db_session, series_id, worker_id, actor="test")
        db_session.commit()


def _assert_end_state(db_session, worker_id, v1_id, kept, ended):
    rows = {r.work_date.isoformat(): r for r in _entries(db_session, worker_id) if r.version_id == v1_id}
    for day in kept:
        assert rows[day].status == "active", (day, rows[day].status)  # 始まっていた日は残る。◆（changing）にしない
    for day in ended:
        assert rows[day].status == "cancelled" and rows[day].status_reason == "declined_new_version", (day, rows[day].status)
    assert _live_dates(db_session, worker_id) == sorted(kept)


# 結合試験の段取り §2 の表（3勤務日 09:00 開始、2日目に終了）
CASES = [
    pytest.param((2, 8, 59), [1], [2, 3], id="2日目の開始1分前"),
    pytest.param((2, 9, 0), [1, 2], [3], id="2日目の開始ちょうど"),
    pytest.param((2, 18, 0), [1, 2], [3], id="2日目の終業時刻"),
]


@pytest.mark.parametrize("clock,kept,ended", CASES)
def test_web_decline_of_new_version_keeps_started_days(
    api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch, clock, kept, ended
):
    sent = _recorder(monkeypatch)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1, _v2, new_delivery = _accepted_then_new_version_sent(api_client, db_session, ops_user, worker, _schedule(1, 3))
    _release(db_session, actions=ALL)
    _set_clock(monkeypatch, *clock)
    headers = _session(api_client)  # 画面の有効期限は固定時計で数えるため、時計を合わせてから開く

    declined = _reply(api_client, headers, new_delivery, "decline", reason="新しい条件では働けない")
    assert declined.status_code == 200, declined.text
    assert declined.json()["outcome"] == "declined"
    kept_days, ended_days = [_day(k) for k in kept], [_day(e) for e in ended]
    _assert_end_state(db_session, worker.id, v1["id"], kept_days, ended_days)
    assert len(sent) == 1 and sent[0][2] == reply_notice_key(new_delivery, "declined")

    # 作り直しても、日を進めても同じ（終了した未来の日が復活しない・残した日が消えない）
    series_id = db_session.get(OrderRequestVersion, v1["id"]).series_id
    before = _snapshot(db_session, worker.id)
    _rebuild_twice(db_session, series_id, worker.id)
    assert _snapshot(db_session, worker.id) == before
    _set_clock(monkeypatch, 5, 12)
    _rebuild_twice(db_session, series_id, worker.id)
    ws.rebuild_series(db_session, series_id, actor="test")
    db_session.commit()
    assert _snapshot(db_session, worker.id) == before

    # 本人の画面：残した日に◆や返事の要求が出ない
    _set_clock(monkeypatch, 1, 6)
    headers = _session(api_client)
    home = api_client.get("/api/line/worker/home", headers=headers).json()
    assert home["confirmations"] == []
    shown = [e for d in home["month_days"] for e in d["entries"]]
    assert sorted({e["date"] for e in shown} & set(kept_days + ended_days)) == kept_days
    assert not any(e["changing"] for e in shown)


def test_web_decline_during_night_shift_keeps_the_started_shift(
    api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch
):
    """1日目 22:00〜2日目 06:00 の夜勤の途中（2日目 01:00）に辞退：1日目開始の夜勤は残り、2日目以降は終了。"""
    _recorder(monkeypatch)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1, _v2, new_delivery = _accepted_then_new_version_sent(api_client, db_session, ops_user, worker, _night_schedule(1, 3))
    _release(db_session, actions=ALL)
    _set_clock(monkeypatch, 2, 1)
    headers = _session(api_client)
    declined = _reply(api_client, headers, new_delivery, "decline", reason="夜勤が続けられない")
    assert declined.json()["outcome"] == "declined", declined.text
    _assert_end_state(db_session, worker.id, v1["id"], [_day(1)], [_day(2), _day(3)])
    series_id = db_session.get(OrderRequestVersion, v1["id"]).series_id
    before = _snapshot(db_session, worker.id)
    _set_clock(monkeypatch, 6, 12)
    _rebuild_twice(db_session, series_id, worker.id)
    assert _snapshot(db_session, worker.id) == before


def test_talk_decline_gives_the_same_result_as_web(
    api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch
):
    """トークで辞退しても、Web と同じ結果（同じ共通処理 decline_delivery を通る）。"""
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1, _v2, new_delivery = _accepted_then_new_version_sent(api_client, db_session, ops_user, worker, _schedule(1, 3))
    _set_clock(monkeypatch, 2, 9)
    _postback(api_client, f"or_decline:{new_delivery}")
    _webhook(api_client, {"events": [{"type": "message", "replyToken": "rr", "source": {"type": "user", "userId": "U123"}, "message": {"type": "text", "text": "新しい条件では働けない"}}]}, event_id="talk-decline-3b")
    _assert_end_state(db_session, worker.id, v1["id"], [_day(1), _day(2)], [_day(3)])


def test_web_decline_is_not_duplicated_by_resend_or_talk(
    api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch
):
    """二度押し・同じキーの再送・別のキー・トークでの後追いでも、辞退・終了・受付の通知は1回だけ（段取り §3-6）。"""
    sent = _recorder(monkeypatch)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1, _v2, new_delivery = _accepted_then_new_version_sent(api_client, db_session, ops_user, worker, _schedule(1, 3))
    _release(db_session, actions=ALL)
    _set_clock(monkeypatch, 2, 10)
    headers = _session(api_client)

    first = _reply(api_client, headers, new_delivery, "decline", reason="都合が悪い", key="k1")
    assert first.status_code == 200 and first.json()["outcome"] == "declined", first.text
    after_first = _snapshot(db_session, worker.id)
    same_key = _reply(api_client, headers, new_delivery, "decline", reason="都合が悪い", key="k1")
    assert same_key.json() == first.json()
    other_key = _reply(api_client, headers, new_delivery, "decline", reason="別の理由", key="k2")
    assert other_key.json()["outcome"] == "already"
    accept_after = _reply(api_client, headers, new_delivery, "accept", key="k3")
    assert accept_after.json()["outcome"] == "already"
    _postback(api_client, f"or_decline:{new_delivery}")  # トークでの後追い
    _webhook(api_client, {"events": [{"type": "message", "replyToken": "rr2", "source": {"type": "user", "userId": "U123"}, "message": {"type": "text", "text": "トークからの理由"}}]}, event_id="talk-after-web")

    db_session.expire_all()
    row = db_session.get(OrderRequestDelivery, new_delivery)
    assert row.ack_status == ACK_DECLINED and row.decline_reason == "都合が悪い"  # 最初の理由のまま
    assert _snapshot(db_session, worker.id) == after_first
    declined_logs = db_session.query(AuditLog).filter(AuditLog.action == "order_request_declined", AuditLog.target_id == new_delivery).count()
    assert declined_logs == 1
    assert [s[2] for s in sent] == [reply_notice_key(new_delivery, "declined")]  # 受付の通知は1回だけ
    application = ws.get_application(db_session, db_session.get(OrderRequestVersion, v1["id"]).series_id, worker.id)
    assert application is not None and application.applied_delivery_id is None and application.ended_reason == "declined_new_version"
