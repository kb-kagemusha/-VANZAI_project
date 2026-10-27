"""日付を選んでの受諾と、稼働者向けLIFFの共通部分（統合計画 ①、A1+ §3）。"""
from __future__ import annotations

from datetime import timedelta

import pytest

from src.models.line_daily import LineWorkerSubmitKey
from src.models.order_request import OrderRequestDelivery
from src.services import worker_schedule as ws
from tests.test_api_line_order_requests import (  # noqa: F401
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
from tests.test_line_daily import _create_confirm, _entries, _postback, _release, _schedule, _day


@pytest.fixture
def liff_env(monkeypatch):
    monkeypatch.setenv("LINE_WORKER_LIFF_ID", "2011980694-TestLiff")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "2011980694")
    # 登録の受付は閉じていても、稼働者機能の本人確認は動く（R-06）
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "false")
    monkeypatch.setattr("src.services.line_id_token.verify_id_token", lambda token, channel: token.removeprefix("idtoken-"))


def _session(api_client, line_user="U123"):
    response = api_client.post("/api/line/worker/sessions", json={"id_token": f"idtoken-{line_user}"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _create_partial(api_client, ops_user, worker_ids, *, allow=True, first=1, last=4, holidays=None):
    from tests.test_line_daily import _payload
    body = _payload(worker_ids, schedule=_schedule(first, last, holidays=holidays))
    body["allow_partial_accept"] = allow
    created = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username))
    assert created.status_code == 200, created.text
    assert created.json()["allow_partial_accept"] is allow
    confirmed = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops_user.username))
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _send(api_client, ops_user, delivery_id):
    sent = api_client.post(f"/api/order-requests/deliveries/{delivery_id}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text


def test_send_shows_pick_button_only_when_allowed_and_enabled(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    allowed = _create_partial(api_client, ops_user, [worker.id])
    _release(db_session, actions=("wk_wake", "wk_orders", "wk_schedule", "pick_dates"))
    _send(api_client, ops_user, allowed["deliveries"][0]["id"])
    buttons = [c for c in fake_line.pushes[-1][1][1]["contents"]["body"]["contents"] if c["type"] == "button"]
    assert [b["action"]["label"] for b in buttons] == ["全日程で受諾します", "日付を選んで受諾する", "今回は辞退します"]
    assert buttons[1]["action"]["uri"] == f"https://liff.line.me/2011980694-TestLiff?m=pick&d={allowed['deliveries'][0]['id']}"

    not_allowed = _create_partial(api_client, ops_user, [worker.id], allow=False)
    _send(api_client, ops_user, not_allowed["deliveries"][0]["id"])
    labels = [c["action"]["label"] for c in fake_line.pushes[-1][1][1]["contents"]["body"]["contents"] if c["type"] == "button"]
    assert labels == ["依頼の案件、受諾します", "今回は辞退します"]


def test_pick_accept_records_only_chosen_days(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id])
    delivery_id = version["deliveries"][0]["id"]
    _send(api_client, ops_user, delivery_id)
    _release(db_session, actions=("wk_wake", "pick_dates"))
    headers = _session(api_client)

    view = api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=headers)
    assert view.status_code == 200, view.text
    assert view.json()["state"] == "open" and view.json()["offered_dates"] == [_day(1), _day(2), _day(3), _day(4)]

    chosen = [_day(1), _day(3)]
    key = {"Idempotency-Key": "key-1"}
    accepted = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": chosen}, headers={**headers, **key})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["outcome"] == "acked" and accepted.json()["accepted_dates"] == chosen
    assert [r.work_date.isoformat() for r in _entries(db_session, worker.id)] == chosen

    # 同じキーの再送は同じ結果、内容が違えば拒否（R-06）
    again = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": chosen}, headers={**headers, **key})
    assert again.status_code == 200 and again.json() == accepted.json()
    conflict = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(2)]}, headers={**headers, **key})
    assert conflict.status_code == 409
    other = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(2)]}, headers={**headers, "Idempotency-Key": "key-2"})
    assert other.json()["outcome"] == "already"
    db_session.expire_all()
    assert db_session.query(LineWorkerSubmitKey).count() == 2

    detail = api_client.get(f"/api/order-requests/versions/{version['id']}", headers=_auth(ops_user.username)).json()
    assert detail["deliveries"][0]["participation_dates"] == chosen


@pytest.mark.parametrize("dates", [[], ["2000-01-01"]])
def test_pick_rejects_empty_or_unoffered_days(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, dates):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id])
    delivery_id = version["deliveries"][0]["id"]
    _send(api_client, ops_user, delivery_id)
    _release(db_session, actions=("pick_dates",))
    response = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": dates}, headers={**_session(api_client), "Idempotency-Key": "k"})
    assert response.json()["outcome"] == "partial_invalid"
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_status == "unacked"


def test_pick_rejected_when_not_allowed_superseded_or_other_worker(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    a = _worker(db_session, "稼働者A")
    b = _worker(db_session, "稼働者B")
    _link(api_client, ops_user, a.id, "U123")
    _link(api_client, ops_user, b.id, "U999", event_id="link-b")
    _release(db_session, actions=("pick_dates",))
    plain = _create_partial(api_client, ops_user, [a.id], allow=False)
    r = api_client.post(f"/api/line/worker/deliveries/{plain['deliveries'][0]['id']}/pick", json={"dates": [_day(1)]}, headers={**_session(api_client), "Idempotency-Key": "k1"})
    assert r.json()["outcome"] == "partial_not_allowed"

    allowed = _create_partial(api_client, ops_user, [a.id])
    delivery_id = allowed["deliveries"][0]["id"]
    # 他人のセッションでは開けない・操作できない
    other = _session(api_client, "U999")
    assert api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=other).status_code == 404
    r = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(1)]}, headers={**other, "Idempotency-Key": "k2"})
    assert r.json()["outcome"] == "rejected"

    # 修正版の確定後は旧い版で受諾できない
    revised = api_client.post(f"/api/order-requests/versions/{allowed['id']}/revise", json={"reason": "変更"}, headers=_auth(ops_user.username))
    api_client.post(f"/api/order-requests/versions/{revised.json()['id']}/confirm", headers=_auth(ops_user.username))
    view = api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=_session(api_client))
    assert view.json()["state"] == "superseded"
    r = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(1)]}, headers={**_session(api_client), "Idempotency-Key": "k3"})
    assert r.json()["outcome"] == "superseded_version"


def test_feature_off_and_unlinked_and_revoked_link(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id])
    delivery_id = version["deliveries"][0]["id"]
    headers = _session(api_client)
    # 機能が公開されていなければ使えない（R-02）
    assert api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=headers).status_code == 403
    # 未連携は本人確認で止まる
    assert api_client.post("/api/line/worker/sessions", json={"id_token": "idtoken-Unknown"}).status_code == 403
    # 連携を解除すると、発行済みのセッションでも見られない
    _release(db_session, actions=("pick_dates",))
    assert api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=headers).status_code == 200
    revoked = api_client.post(f"/api/order-requests/line-links/{worker.id}/revoke", json={"reason": "試験"}, headers=_auth(ops_user.username))
    assert revoked.status_code == 200, revoked.text
    assert api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=headers).status_code == 403


def test_session_expires(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _release(db_session, actions=("pick_dates",))
    version = _create_partial(api_client, ops_user, [worker.id])
    headers = _session(api_client)
    later = ws.now_utc() + timedelta(minutes=31)
    monkeypatch.setattr(ws, "now_utc", lambda: later)
    assert api_client.get(f"/api/line/worker/deliveries/{version['deliveries'][0]['id']}/pick", headers=headers).status_code == 401


def test_full_accept_still_works_on_allowed_document(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id])
    delivery_id = version["deliveries"][0]["id"]
    _send(api_client, ops_user, delivery_id)
    _postback(api_client, f"or_accept:{delivery_id}")
    assert len(_entries(db_session, worker.id)) == 4


def test_entry_reports_liff_and_features(api_client, db_session, liff_env):
    _release(db_session, actions=("wk_wake", "pick_dates"))
    entry = api_client.get("/api/line/worker/entry").json()
    assert entry == {"liff_id": "2011980694-TestLiff", "features": ["pick_dates"]}


def _counts(calendar_days, day):
    for entry in calendar_days:
        if entry["date"] == day:
            event = entry["events"][0]
            return len(event["ok"]), len(event["changing"]), len(event["unanswered"])
    return (0, 0, 0)


def test_participation_calendar_classifies_without_double_counting(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    a, b, c, d = (_worker(db_session, n) for n in ("Aさん", "Bさん", "Cさん", "Dさん"))
    for worker, uid in ((a, "UA"), (b, "UB"), (c, "UC"), (d, "UD")):
        _link(api_client, ops_user, worker.id, uid, event_id=f"link-{uid}")
    v1 = _create_partial(api_client, ops_user, [a.id, b.id, c.id, d.id], first=1, last=3)
    rows = {r["worker_id"]: r["id"] for r in v1["deliveries"]}
    for worker in (a, b, c, d):
        _send(api_client, ops_user, rows[worker.id])
    _release(db_session, actions=("pick_dates",))
    # A：全日程で受諾、B：1日目だけ受諾、C：辞退、D：未回答
    _postback(api_client, f"or_accept:{rows[a.id]}", user="UA")
    api_client.post(f"/api/line/worker/deliveries/{rows[b.id]}/pick", json={"dates": [_day(1)]}, headers={**_session(api_client, "UB"), "Idempotency-Key": "kb"})
    _postback(api_client, f"or_decline:{rows[c.id]}", user="UC")
    _webhook(api_client, {"events": [{"type": "message", "replyToken": "rc", "source": {"type": "user", "userId": "UC"}, "message": {"type": "text", "text": "都合が悪い"}}]}, event_id="decline-c")

    cal = api_client.get(f"/api/order-requests/participation-calendar?version_id={v1['id']}", headers=_auth(ops_user.username)).json()["days"]
    assert _counts(cal, _day(1)) == (2, 0, 1)  # A・B 参加OK、D 未回答（C は辞退で数えない）
    assert _counts(cal, _day(2)) == (1, 0, 1)

    # 修正版を確定 → A・B は「変更確認待ち」（旧い参加日で）、D は新しい版の未送付なので数えない
    revised = api_client.post(f"/api/order-requests/versions/{v1['id']}/revise", json={"reason": "変更"}, headers=_auth(ops_user.username))
    v2 = api_client.post(f"/api/order-requests/versions/{revised.json()['id']}/confirm", headers=_auth(ops_user.username)).json()
    cal = api_client.get(f"/api/order-requests/participation-calendar?version_id={v2['id']}", headers=_auth(ops_user.username)).json()["days"]
    assert _counts(cal, _day(1)) == (0, 2, 0)
    # 新しい版を A に送ると、A は変更確認待ちのまま（未回答に重ねて数えない）
    rows2 = {r["worker_id"]: r["id"] for r in v2["deliveries"]}
    _send(api_client, ops_user, rows2[a.id])
    _send(api_client, ops_user, rows2[d.id])
    cal = api_client.get(f"/api/order-requests/participation-calendar?version_id={v2['id']}", headers=_auth(ops_user.username)).json()["days"]
    assert _counts(cal, _day(1)) == (0, 2, 1)  # D は新しい版で未回答
    month = _day(1)[:7]
    monthly = api_client.get(f"/api/order-requests/participation-calendar?month={month}", headers=_auth(ops_user.username))
    assert monthly.status_code == 200 and any(entry["date"] == _day(1) for entry in monthly.json()["days"])


def test_pick_holiday_not_offered_and_accept_notice_sent_once(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch):
    from src.services.line_messaging import LineCallResult

    sent = []

    class Recorder:
        def push_receipt(self, to, text, retry_key):
            sent.append((to, text, retry_key))
            return LineCallResult(200, "", "req")

    monkeypatch.setattr("src.services.line_worker.build_line_client", Recorder)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id], holidays=[2])
    delivery_id = version["deliveries"][0]["id"]
    _send(api_client, ops_user, delivery_id)
    _release(db_session, actions=("pick_dates",))
    headers = _session(api_client)

    view = api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=headers).json()
    assert _day(2) not in view["offered_dates"] and _day(2) in view["holidays"]
    holiday = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(2)]}, headers={**headers, "Idempotency-Key": "h"})
    assert holiday.json()["outcome"] == "partial_invalid"
    assert sent == []

    key = {"Idempotency-Key": "ok"}
    accepted = api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(1), _day(3)]}, headers={**headers, **key})
    assert accepted.json()["outcome"] == "acked"
    assert len(sent) == 1
    to, text, retry_key = sent[0]
    assert to == "U123" and "受け付けました" in text and "（2日）" in text and len(retry_key) == 36
    from src.services.line_order import format_date_set
    # 休業日と参加しない日を分離し、離れた参加日は1日につき1行。
    assert "期間：" in text
    assert f"期間中の休業日：\n{format_date_set([_day(2)])}" in text
    assert f"参加する日（2日）：\n{format_date_set([_day(1)])}\n{format_date_set([_day(3)])}" in text
    assert f"参加しない日：\n{format_date_set([_day(4)])}" in text
    sent_text = fake_line.pushes[0][1][0]["text"]
    assert f"期間中の休業日: {format_date_set([_day(2)])}" in sent_text and "あなたの稼働日" not in sent_text
    # 同じキーの再送では通知しない
    api_client.post(f"/api/line/worker/deliveries/{delivery_id}/pick", json={"dates": [_day(1), _day(3)]}, headers={**headers, **key})
    assert len(sent) == 1


def test_participation_shows_zero_days_and_test_documents(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    from tests.test_line_daily import _payload

    worker = _worker(db_session, "稼働者A")
    body = _payload([worker.id], kind="test", schedule=_schedule(1, 3))
    created = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username)).json()
    confirmed = api_client.post(f"/api/order-requests/versions/{created['id']}/confirm", headers=_auth(ops_user.username)).json()
    # 未送付（未回答にも数えない）でも、テストの依頼書でも、稼働日は0人として表示する
    days = api_client.get(f"/api/order-requests/participation-calendar?version_id={confirmed['id']}", headers=_auth(ops_user.username)).json()["days"]
    assert [d["date"] for d in days] == [_day(1), _day(2), _day(3)]
    assert all(len(d["events"][0]["ok"]) == 0 and len(d["events"][0]["unanswered"]) == 0 for d in days)
    # 月のカレンダーには、テストの依頼書は出さない
    month = _day(1)[:7]
    monthly = api_client.get(f"/api/order-requests/participation-calendar?month={month}", headers=_auth(ops_user.username)).json()["days"]
    assert all(e["version_id"] != confirmed["id"] for d in monthly for e in d["events"])
    # 俯瞰カレンダーでテストも含めるときは出す
    with_test = api_client.get(f"/api/order-requests/participation-calendar?month={month}&include_test=true", headers=_auth(ops_user.username)).json()["days"]
    events = [e for d in with_test for e in d["events"] if e["version_id"] == confirmed["id"]]
    assert events and all(e["is_test"] for e in events)


def test_document_body_lists_holidays_under_work_date():
    from src.services.order_request_format import holiday_label
    from datetime import date

    schedule = {"work_groups": [{"excluded_dates": ["2026-10-25", "2026-10-28"]}]}
    assert holiday_label({"schedule": schedule}) == "10月25日（日）、10月28日（水）"
    assert holiday_label({}) == ""
    assert date(2026, 10, 25).weekday() == 6


def test_confirmed_body_has_holiday_section(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    version = _create_partial(api_client, ops_user, [worker.id], holidays=[2])
    body = version["body"]
    assert body.index("■稼働日") < body.index("■休業日") < body.index("■稼働日の詳細")


def test_period_holidays_are_distributed_to_work_groups(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    import json
    from tests.test_line_daily import _payload

    worker = _worker(db_session, "稼働者A")
    body = _payload([worker.id], schedule=_schedule(1, 5))
    conditions = json.loads(body["request_conditions"])
    conditions["work_period"] = {"from": _day(1), "to": _day(5), "excluded_dates": [_day(2), _day(4)]}
    body["request_conditions"] = json.dumps(conditions)
    created = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username))
    assert created.status_code == 200, created.text
    confirmed = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops_user.username)).json()
    assert confirmed["deliveries"][0]["offered_dates"] == [_day(1), _day(3), _day(5)]
    assert "■休業日" in confirmed["body"]

    # 休業日が稼働日の期間外ならエラー
    conditions["work_period"]["excluded_dates"] = [_day(9)]
    body["request_conditions"] = json.dumps(conditions)
    bad = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username))
    assert bad.status_code == 400 and "期間外の休業日" in bad.text


def test_period_holiday_on_single_day_group_is_rejected():
    from src.domain.order_schedule import apply_period_holidays

    schedule = {"work_groups": [{"id": "g1", "date_mode": "single", "from": "2026-11-01", "to": "2026-11-01"}]}
    with pytest.raises(ValueError, match="1日ごと"):
        apply_period_holidays(schedule, ["2026-11-01"])


def test_overview_lists_all_registered_workers_with_line_status(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    linked = _worker(db_session, "連携あり")
    unlinked = _worker(db_session, "連携なし")
    _link(api_client, ops_user, linked.id, "U123")
    month = _day(1)[:7]
    body = api_client.get(f"/api/order-requests/participation-calendar?month={month}&include_workers=true", headers=_auth(ops_user.username)).json()
    rows = {w["worker_id"]: w for w in body["workers"]}
    # 依頼を送っていない人も、登録のある人は全員出す
    assert rows[linked.id]["line_linked"] is True and rows[unlinked.id]["line_linked"] is False
    assert "workers" not in api_client.get(f"/api/order-requests/participation-calendar?month={month}", headers=_auth(ops_user.username)).json()


def test_pick_retains_period_edge_holidays_and_groups_only_consecutive_dates(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    from src.services.line_order import format_date_set, participation_summary
    from src.models.order_request import OrderRequestVersion

    worker = _worker(db_session, "期間確認")
    _link(api_client, ops_user, worker.id, "U123")
    version = _create_partial(api_client, ops_user, [worker.id], last=6, holidays=[1, 6])
    delivery_id = version["deliveries"][0]["id"]
    _release(db_session, actions=("pick_dates",))
    view = api_client.get(f"/api/line/worker/deliveries/{delivery_id}/pick", headers=_session(api_client)).json()
    assert view["period"] == {"from": _day(1), "to": _day(6)}
    assert view["holidays"] == [_day(1), _day(6)]
    assert view["offered_dates"] == [_day(2), _day(3), _day(4), _day(5)]
    text = participation_summary(db_session.get(OrderRequestVersion, version["id"]), [_day(2), _day(3)])
    assert f"参加する日（2日）：\n{format_date_set([_day(2), _day(3)])}\n" in text
    assert text.split("参加しない日：\n")[1] == format_date_set([_day(4), _day(5)])


def test_pick_personal_absence_is_not_a_common_holiday(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    from tests.test_line_daily import _payload
    from src.services.line_order import format_date_set, participation_summary
    from src.models.order_request import OrderRequestVersion

    worker = _worker(db_session, "個人不参加")
    _link(api_client, ops_user, worker.id, "U123")
    body = _payload([worker.id], schedule=_schedule(1, 5, holidays=[2]), absences={worker.id: [_day(4)]})
    body["allow_partial_accept"] = True
    created = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username)).json()
    version = api_client.post(f"/api/order-requests/versions/{created['id']}/confirm", headers=_auth(ops_user.username)).json()
    _release(db_session, actions=("pick_dates",))
    view = api_client.get(f"/api/line/worker/deliveries/{version['deliveries'][0]['id']}/pick", headers=_session(api_client)).json()
    assert view["holidays"] == [_day(2)]
    assert _day(4) not in view["offered_dates"]
    text = participation_summary(db_session.get(OrderRequestVersion, version["id"]), view["offered_dates"])
    assert text.split("参加しない日：\n")[1] == format_date_set([_day(4)])
