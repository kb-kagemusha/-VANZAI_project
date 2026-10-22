"""A1：稼働予定の生成と版の切り替え、公式LINEの①⑤⑥、起床状況、受諾後の辞退（DEC-063〜065）。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src.api.jwt_auth import create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.line_daily import (
    LineActionToken,
    LineRichMenuRelease,
    OrderRequestSeries,
    OrderRequestWorkerApplication,
    WakeReport,
    WorkerScheduleEntry,
)
from src.models.line_order import LineWebhookEvent
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.services import worker_schedule as ws
from src.services.line_daily import NOT_AVAILABLE, NOT_LINKED, TOKEN_EXPIRED
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


def _day(offset: int) -> str:
    return (ws.today_jst() + timedelta(days=offset)).isoformat()


def _schedule(first: int = 1, last: int = 3, *, holidays: list[int] | None = None) -> dict:
    work = [
        {
            "id": "g1", "date_mode": "range" if last > first else "single", "from": _day(first), "to": _day(last),
            "start_time": "09:00", "end_time": "18:00",
            "excluded_dates": [_day(h) for h in (holidays or [])],
        }
    ]
    rates = [{"id": "r1", "work_group_id": "g1", "date_mode": work[0]["date_mode"], "from": _day(first), "to": _day(last), "amount": "15000", "unit": "day"}]
    return {"version": 1, "work_groups": work, "rates_follow_work": True, "rate_groups": rates}


def _payload(worker_ids, *, kind="formal", schedule=None, absences=None, based_on=None, project="駅前イベント"):
    conditions = {
        "format": "additional-request-v1", "project_name": project, "meeting_place": "北口改札",
        "schedule": schedule or _schedule(),
    }
    body = {
        "kind": kind, "work_date_label": "", "site_name": "会場A", "request_conditions": json.dumps(conditions),
        "body": "", "contact_name": "依頼担当", "contact_desk": "", "worker_ids": worker_ids,
        "follow_up_due_on": _day(0), "follow_up_due_time": "21:00",
    }
    if absences:
        body["recipient_absences"] = absences
    if based_on:
        body["based_on_version_id"] = based_on
    return body


def _create_confirm(api_client, ops_user, worker_ids, **kw) -> dict:
    created = api_client.post("/api/order-requests", json=_payload(worker_ids, **kw), headers=_auth(ops_user.username))
    assert created.status_code == 200, created.text
    confirmed = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops_user.username))
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _revise_confirm(api_client, ops_user, version_id, **changes) -> dict:
    revised = api_client.post(f"/api/order-requests/versions/{version_id}/revise", json={"reason": "変更"}, headers=_auth(ops_user.username))
    assert revised.status_code == 200, revised.text
    if changes:
        patched = api_client.patch(f"/api/order-requests/versions/{revised.json()['id']}", json=changes, headers=_auth(ops_user.username))
        assert patched.status_code == 200, patched.text
    confirmed = api_client.post(f"/api/order-requests/versions/{revised.json()['id']}/confirm", headers=_auth(ops_user.username))
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


_event_no = [0]


def _postback(api_client, data: str, user: str = "U123", *, timestamp: int | None = None):
    _event_no[0] += 1
    event = {
        "type": "postback", "replyToken": f"r-{_event_no[0]}",
        "source": {"type": "user", "userId": user}, "postback": {"data": data},
    }
    if timestamp is not None:
        event["timestamp"] = timestamp
    return _webhook(api_client, {"events": [event]}, event_id=f"ev-{_event_no[0]}")


def _send_and_accept(api_client, ops_user, delivery_id: str, user: str = "U123"):
    sent = api_client.post(f"/api/order-requests/deliveries/{delivery_id}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    accepted = _postback(api_client, f"or_accept:{delivery_id}", user)
    assert accepted.status_code == 200, accepted.text


def _entries(db_session, worker_id: str) -> list[WorkerScheduleEntry]:
    db_session.expire_all()
    return (
        db_session.query(WorkerScheduleEntry)
        .filter(WorkerScheduleEntry.worker_id == worker_id)
        .order_by(WorkerScheduleEntry.work_date, WorkerScheduleEntry.version_id)
        .all()
    )


def _release(db_session, actions=("wk_wake", "wk_orders", "wk_schedule")):
    db_session.add(LineRichMenuRelease(
        id=generate_ulid(), stage="a1", rich_menu_id="richmenu-test", enabled_actions=list(actions),
        image_sha256="0" * 64, applied_at=datetime.now(timezone.utc), applied_by="test",
    ))
    db_session.commit()


def _last_reply(fake_line: FakeLine):
    return fake_line.messages[-1][1] if fake_line.messages else None


def _last_text(fake_line: FakeLine) -> str:
    if fake_line.messages:
        return fake_line.messages[-1][1][0].get("text", "")
    return fake_line.replies[-1][1]


# ---- 受諾で稼働予定ができる ---------------------------------------------------------

def test_accept_creates_entries_for_offered_days_only(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    other = _worker(db_session, "稼働者B")
    version = _create_confirm(
        api_client, ops_user, [worker.id, other.id],
        schedule=_schedule(1, 5, holidays=[3]), absences={worker.id: [_day(2)]},
    )
    mine = next(d for d in version["deliveries"] if d["worker_id"] == worker.id)
    assert mine["offered_dates"] == [_day(1), _day(4), _day(5)]
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, mine["id"])

    rows = _entries(db_session, worker.id)
    assert [r.work_date.isoformat() for r in rows] == [_day(1), _day(4), _day(5)]
    assert {r.status for r in rows} == {"active"}
    assert rows[0].project_name == "駅前イベント" and rows[0].meeting_place == "北口改札"
    assert rows[0].is_test is False
    assert "あなたの稼働日" in fake_line.replies[-1][1]
    assert _entries(db_session, other.id) == []  # 未受諾の人には作らない

    detail = api_client.get(f"/api/order-requests/versions/{version['id']}", headers=_auth(ops_user.username)).json()
    row = next(d for d in detail["deliveries"] if d["worker_id"] == worker.id)
    assert row["applied"] is True and row["participation_dates"] == [_day(1), _day(4), _day(5)]


def test_free_text_document_cannot_be_confirmed_but_can_be_copied(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    """文章の稼働時間の依頼書は確定できない（DEC-069）。下書きの保存と、それを基にした作成はできる。"""
    worker = _worker(db_session, "稼働者A")
    body = _payload([worker.id])
    body["request_conditions"] = "自由文の条件"
    body["work_date_label"] = "10月下旬"
    body["body"] = "自由文の本文"
    created = api_client.post("/api/order-requests", json=body, headers=_auth(ops_user.username))
    assert created.status_code == 200, created.text
    response = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops_user.username))
    assert response.status_code == 400
    assert "日付・期間ごとの入力" in response.json()["detail"]
    copied = api_client.post("/api/order-requests", json=_payload([worker.id], based_on=created.json()["id"]), headers=_auth(ops_user.username))
    assert copied.status_code == 200, copied.text
    confirmed = api_client.post(f"/api/order-requests/versions/{copied.json()['id']}/confirm", headers=_auth(ops_user.username))
    assert confirmed.status_code == 200, confirmed.text

def test_test_document_creates_isolated_test_entries(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    version = _create_confirm(api_client, ops_user, [worker.id], kind="test", schedule=_schedule(0, 0))
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, version["deliveries"][0]["id"])
    rows = _entries(db_session, worker.id)
    assert rows and all(r.is_test for r in rows)
    status = api_client.get("/api/line-daily/wake-status", headers=_auth(ops_user.username)).json()
    assert status["total"] == 0  # テストの予定は起床状況に出さない


# ---- 版の切り替え ---------------------------------------------------------------

def test_revision_marks_changing_then_accept_switches(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 3))
    d1 = v1["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, d1)

    conditions = json.loads(_payload([worker.id], schedule=_schedule(2, 4))["request_conditions"])
    v2 = _revise_confirm(api_client, ops_user, v1["id"], request_conditions=json.dumps(conditions))
    rows = _entries(db_session, worker.id)
    assert {r.status for r in rows} == {"changing"}
    assert all(r.version_id == v1["id"] for r in rows)

    # 旧版への受諾はもう受け付けない（回答受付版は新しい版）
    stale = api_client.post(f"/api/order-requests/deliveries/{d1}/line-send", headers=_auth(ops_user.username))
    assert stale.status_code == 409

    d2 = v2["deliveries"][0]["id"]
    _send_and_accept(api_client, ops_user, d2)
    rows = _entries(db_session, worker.id)
    active = [r for r in rows if r.status == "active"]
    assert [r.work_date.isoformat() for r in active] == [_day(2), _day(3), _day(4)]
    assert all(r.version_id == v2["id"] for r in active)
    assert {r.status for r in rows if r.version_id == v1["id"]} == {"superseded"}


def test_declining_new_version_cancels_old_entries(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id])
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    v2 = _revise_confirm(api_client, ops_user, v1["id"])
    d2 = v2["deliveries"][0]["id"]
    assert api_client.post(f"/api/order-requests/deliveries/{d2}/line-send", headers=_auth(ops_user.username)).status_code == 200
    _postback(api_client, f"or_decline:{d2}")
    _webhook(api_client, {"events": [{"type": "message", "replyToken": "rr", "source": {"type": "user", "userId": "U123"}, "message": {"type": "text", "text": "日程が合わない"}}]}, event_id="decline-text")
    rows = _entries(db_session, worker.id)
    assert rows and {r.status for r in rows} == {"cancelled"}
    assert {r.status_reason for r in rows} == {"declined_new_version"}


def test_removed_recipient_loses_entries_and_pdf(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    a = _worker(db_session, "稼働者A")
    b = _worker(db_session, "稼働者B")
    v1 = _create_confirm(api_client, ops_user, [a.id, b.id])
    da = next(d for d in v1["deliveries"] if d["worker_id"] == a.id)["id"]
    _link(api_client, ops_user, a.id, "U123")
    _send_and_accept(api_client, ops_user, da)
    pdf_url = fake_line.pushes[-1][1][0]["text"].split("PDF: ", 1)[1].strip()
    token = pdf_url.rsplit("/", 1)[-1]
    assert api_client.get(f"/api/line/order-request-files/{token}").status_code == 200

    _revise_confirm(api_client, ops_user, v1["id"], worker_ids=[b.id])
    rows = _entries(db_session, a.id)
    assert {r.status for r in rows} == {"cancelled"} and {r.status_reason for r in rows} == {"removed_from_recipients"}
    assert api_client.get(f"/api/line/order-request-files/{token}").status_code in (403, 404, 410)


def test_cancel_answerable_version_ends_series(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id])
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    cancelled = api_client.post(f"/api/order-requests/versions/{v1['id']}/cancel", json={"reason": "中止"}, headers=_auth(ops_user.username))
    assert cancelled.status_code == 200, cancelled.text
    rows = _entries(db_session, worker.id)
    assert {r.status for r in rows} == {"cancelled"} and {r.status_reason for r in rows} == {"document_ended"}
    db_session.expire_all()
    version = db_session.get(OrderRequestVersion, v1["id"])
    assert db_session.get(OrderRequestSeries, version.series_id).answerable_version_id is None


def test_hide_is_blocked_while_future_entries_exist(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    admin = create_user_with_hashed_password(db=db_session, username="admin_daily", email="admin_daily@example.com", password="pass123", role=UserRole.ADMIN.value)
    db_session.commit()
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id])
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    blocked = api_client.post(f"/api/order-requests/documents/{v1['document_id']}/hide", headers=_auth(admin.username))
    assert blocked.status_code == 409
    api_client.post(f"/api/order-requests/versions/{v1['id']}/cancel", json={"reason": "中止"}, headers=_auth(ops_user.username))
    allowed = api_client.post(f"/api/order-requests/documents/{v1['document_id']}/hide", headers=_auth(admin.username))
    assert allowed.status_code == 200, allowed.text


def test_change_document_joins_the_same_series(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    """「変更を作成」で作った依頼書は元と同じ系列（詳細設計 §4.4）。"""
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 2))
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])

    changed = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(3, 4), based_on=v1["id"])
    assert changed["document_id"] != v1["document_id"]
    db_session.expire_all()
    first = db_session.get(OrderRequestVersion, v1["id"])
    second = db_session.get(OrderRequestVersion, changed["id"])
    assert first.series_id == second.series_id
    assert db_session.get(OrderRequestSeries, first.series_id).answerable_version_id == changed["id"]
    rows = _entries(db_session, worker.id)
    assert {r.status for r in rows} == {"changing"}  # 新しい依頼書の確認待ち

    _send_and_accept(api_client, ops_user, changed["deliveries"][0]["id"])
    rows = _entries(db_session, worker.id)
    assert [r.work_date.isoformat() for r in rows if r.status == "active"] == [_day(3), _day(4)]
    assert {r.status for r in rows if r.document_id == v1["document_id"]} == {"superseded"}


# ---- 受諾後の辞退（運営記録） ---------------------------------------------------------

def test_withdraw_acceptance_cancels_entries_and_is_idempotent(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id])
    url = f"/api/order-requests/documents/{v1['document_id']}/workers/{worker.id}/withdraw-acceptance"
    none_yet = api_client.post(url, json={"reason": "体調不良"}, headers=_auth(ops_user.username))
    assert none_yet.status_code == 409

    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    assert api_client.post(url, json={"reason": " "}, headers=_auth(ops_user.username)).status_code == 400
    first = api_client.post(url, json={"reason": "体調不良"}, headers=_auth(ops_user.username))
    assert first.status_code == 200, first.text
    assert first.json()["recorded"] is True
    rows = _entries(db_session, worker.id)
    assert {r.status for r in rows} == {"cancelled"} and {r.status_reason for r in rows} == {"ops_recorded_decline"}
    again = api_client.post(url, json={"reason": "体調不良"}, headers=_auth(ops_user.username))
    assert again.status_code == 200 and again.json()["recorded"] is False


def test_withdraw_requires_order_write(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    accounting = create_user_with_hashed_password(db=db_session, username="acc_daily", email="acc_daily@example.com", password="pass123", role=UserRole.ACCOUNTING.value)
    db_session.commit()
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id])
    url = f"/api/order-requests/documents/{v1['document_id']}/workers/{worker.id}/withdraw-acceptance"
    assert api_client.post(url, json={"reason": "x"}, headers=_auth(accounting.username)).status_code == 403


# ---- 公式LINE：①起床報告 ⑤受託済みの発注依頼書 ⑥スケジュール確認 ----------------------------

def _accepted_today(api_client, db_session, ops_user, *, first=0, last=2):
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(first, last))
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    return worker, v1


def test_menu_actions_are_unavailable_before_release(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    _accepted_today(api_client, db_session, ops_user)
    _postback(api_client, "wk_wake")
    assert _last_text(fake_line) == NOT_AVAILABLE
    _release(db_session, actions=("wk_schedule",))
    _postback(api_client, "wk_wake")
    assert _last_text(fake_line) == NOT_AVAILABLE


def test_unlinked_user_is_told_to_contact_ops(api_client, db_session, ops_user, line_env, fake_line):
    _release(db_session)
    _postback(api_client, "wk_schedule", user="U-unknown")
    assert _last_text(fake_line) == NOT_LINKED


def test_wake_report_greets_and_lists_today_once(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    _release(db_session)
    _postback(api_client, "wk_wake")
    text = _last_text(fake_line)
    assert "稼働者Aさん、おはようございます" in text
    assert "09:00〜18:00 駅前イベント" in text and "集合場所：北口改札" in text
    db_session.expire_all()
    reports = db_session.query(WakeReport).filter(WakeReport.worker_id == worker.id).all()
    assert len(reports) == 1 and reports[0].is_test is False and reports[0].report_date == ws.today_jst()

    _postback(api_client, "wk_wake")
    assert _last_text(fake_line).startswith("報告済みです")
    db_session.expire_all()
    assert db_session.query(WakeReport).filter(WakeReport.worker_id == worker.id).count() == 1

    status = api_client.get("/api/line-daily/wake-status", headers=_auth(ops_user.username)).json()
    assert status["total"] == 1 and status["reported"] == 1
    assert status["items"][0]["worker_name"] == "稼働者A" and status["items"][0]["line_linked"] is True


def test_wake_report_date_follows_event_time_in_japan(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    _release(db_session)
    occurred = datetime.now(timezone.utc) - timedelta(hours=1)
    _postback(api_client, "wk_wake", timestamp=int(occurred.timestamp() * 1000))
    db_session.expire_all()
    report = db_session.query(WakeReport).filter(WakeReport.worker_id == worker.id).one()
    assert report.report_date == occurred.astimezone(ws.JST).date()
    assert report.late_received is True  # 30分以上遅れて届いた


def test_wake_without_schedule_says_so(api_client, db_session, ops_user, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _release(db_session)
    _postback(api_client, "wk_wake")
    assert "本日の予定は登録されていません" in _last_text(fake_line)


def test_schedule_shows_seven_days_and_pages_after_ten(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    for project in ("案件1", "案件2"):
        v = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(0, 9), project=project)
        _send_and_accept(api_client, ops_user, v["deliveries"][0]["id"])
    _release(db_session)
    _postback(api_client, "wk_schedule")
    carousel = _last_reply(fake_line)[0]["contents"]["contents"]
    assert len(carousel) == 11  # 7日×2件=14件のうち10件と「続きを見る」
    next_button = carousel[-1]["footer"]["contents"][0]["action"]
    assert next_button["data"].startswith("wk_next:")
    _postback(api_client, next_button["data"])
    rest = _last_reply(fake_line)[0]["contents"]["contents"]
    assert len(rest) == 4

    # 他人のトークンは使えない
    other = _worker(db_session, "稼働者B")
    _link(api_client, ops_user, other.id, "U999", event_id="link-other")
    _postback(api_client, next_button["data"], user="U999")
    assert _last_text(fake_line) == TOKEN_EXPIRED

    # 期限切れのトークンは使えない
    db_session.expire_all()
    for row in db_session.query(LineActionToken).all():
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    _postback(api_client, next_button["data"])
    assert _last_text(fake_line) == TOKEN_EXPIRED


def test_orders_list_opens_a_fresh_pdf_link(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    _accepted_today(api_client, db_session, ops_user)
    _release(db_session)
    _postback(api_client, "wk_orders")
    bubble = _last_reply(fake_line)[0]["contents"]["contents"][0]
    open_action = bubble["footer"]["contents"][0]["action"]
    assert open_action["data"].startswith("wk_open:")
    _postback(api_client, open_action["data"])
    text = _last_text(fake_line)
    url = text.split("\n", 1)[1].strip()
    assert url.startswith("https://api.example.test/api/line/order-request-files/")
    assert api_client.get("/api/line/order-request-files/" + url.rsplit("/", 1)[-1]).status_code == 200


def test_orders_offer_the_new_document_while_changing(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, v1 = _accepted_today(api_client, db_session, ops_user)
    _revise_confirm(api_client, ops_user, v1["id"])
    _release(db_session)
    _postback(api_client, "wk_orders")
    bubble = _last_reply(fake_line)[0]["contents"]["contents"][0]
    labels = [b["action"]["label"] for b in bubble["footer"]["contents"]]
    assert labels == ["依頼書を開く", "新しい依頼書を開く"]
    texts = [c["text"] for c in bubble["body"]["contents"]]
    assert "新しい依頼書の確認待ち" in texts
    del worker


# ---- Webhook の扱い ------------------------------------------------------------

def test_same_event_is_processed_once(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    _release(db_session)
    event = {"type": "postback", "replyToken": "same", "source": {"type": "user", "userId": "U123"}, "postback": {"data": "wk_wake"}}
    first = _webhook(api_client, {"events": [event]}, event_id="dup-1")
    before = len(fake_line.messages) + len(fake_line.replies)
    second = _webhook(api_client, {"events": [event]}, event_id="dup-1")
    assert first.status_code == 200 and second.status_code == 200
    assert len(fake_line.messages) + len(fake_line.replies) == before
    db_session.expire_all()
    assert db_session.query(LineWebhookEvent).filter(LineWebhookEvent.event_id == "dup-1").count() == 1
    del worker


def test_wake_status_permission(api_client, db_session, ops_user, line_env, fake_line):
    manager = create_user_with_hashed_password(db=db_session, username="sm_daily", email="sm_daily@example.com", password="pass123", role=UserRole.SITE_MANAGER.value)
    db_session.commit()
    assert api_client.get("/api/line-daily/wake-status", headers=_auth(manager.username)).status_code == 403
    assert api_client.get("/api/line-daily/wake-status", headers=_auth(ops_user.username)).status_code == 200


def test_application_row_pairs_delivery_and_version(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, v1 = _accepted_today(api_client, db_session, ops_user)
    db_session.expire_all()
    row = db_session.query(OrderRequestWorkerApplication).filter(OrderRequestWorkerApplication.worker_id == worker.id).one()
    delivery = db_session.get(OrderRequestDelivery, row.applied_delivery_id)
    assert delivery.version_id == row.applied_version_id == v1["id"]


def test_composite_foreign_keys_reject_mismatched_rows():
    """適用行の送付行・版・系列は同じ系列の中で対になっていること（R3-01）。"""
    from sqlalchemy import create_engine, event
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from src.models.base import Base
    from src.models.master import User, Worker
    from src.models.order_request import OrderRequestDocument

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        worker = Worker(id=generate_ulid(), name="A", is_active=True)
        user = User(id=generate_ulid(), username="fk", email="fk@example.com", role="ops")
        session.add_all([worker, user])
        session.flush()
        ids = {}
        for key in ("s1", "s2"):
            series = OrderRequestSeries(id=generate_ulid())
            session.add(series)
            session.flush()
            document = OrderRequestDocument(id=generate_ulid(), document_number=key, kind="formal", created_by_user_id=user.id)
            session.add(document)
            session.flush()
            version = OrderRequestVersion(id=generate_ulid(), document_id=document.id, version_no=1, series_id=series.id, created_by_user_id=user.id)
            session.add(version)
            session.flush()
            delivery = OrderRequestDelivery(id=generate_ulid(), version_id=version.id, worker_id=worker.id, worker_name_snapshot="A")
            session.add(delivery)
            session.flush()
            ids[key] = (series.id, version.id, delivery.id)
        session.commit()
        good = OrderRequestWorkerApplication(
            id=generate_ulid(), series_id=ids["s1"][0], worker_id=worker.id,
            applied_delivery_id=ids["s1"][2], applied_version_id=ids["s1"][1], updated_by="t", updated_at=now,
        )
        session.add(good)
        session.commit()
        bad = OrderRequestWorkerApplication(
            id=generate_ulid(), series_id=ids["s2"][0], worker_id=worker.id,
            applied_delivery_id=ids["s1"][2], applied_version_id=ids["s1"][1], updated_by="t", updated_at=now,
        )
        session.add(bad)
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_copy_for_another_day_is_an_independent_series(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    """「別日で新規作成」（based_on なしの新規作成）は別の系列。元の依頼書の予定は変わらない。"""
    worker = _worker(db_session, "稼働者A")
    first = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 1))
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, first["deliveries"][0]["id"])
    second = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(3, 3))
    db_session.expire_all()
    assert db_session.get(OrderRequestVersion, first["id"]).series_id != db_session.get(OrderRequestVersion, second["id"]).series_id
    _send_and_accept(api_client, ops_user, second["deliveries"][0]["id"])
    rows = _entries(db_session, worker.id)
    assert [(r.work_date.isoformat(), r.status) for r in rows] == [(_day(1), "active"), (_day(3), "active")]


def test_end_participation_keeps_days_already_started(api_client, db_session, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    """今後の参加を終了：記録した時点で勤務が始まっている日は残す（統合計画 D-05、0.47.8）。"""
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 3))  # 09:00〜18:00
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    second_day = date.fromisoformat(_day(2))
    # 2日目の 10:00（勤務開始後）に記録したことにする
    moment = datetime(second_day.year, second_day.month, second_day.day, 10, 0, tzinfo=ws.JST)
    monkeypatch.setattr(ws, "now_utc", lambda: moment.astimezone(timezone.utc))

    detail = api_client.get(f"/api/order-requests/versions/{v1['id']}", headers=_auth(ops_user.username)).json()
    preview = detail["deliveries"][0]["end_preview"]
    assert preview["kept_dates"] == [_day(1), _day(2)] and preview["removed_dates"] == [_day(3)]
    assert detail["deliveries"][0]["can_end_participation"] is True

    url = f"/api/order-requests/documents/{v1['document_id']}/workers/{worker.id}/withdraw-acceptance"
    ended = api_client.post(url, json={"reason": "体調不良"}, headers=_auth(ops_user.username))
    assert ended.status_code == 200, ended.text
    assert ended.json()["kept_dates"] == [_day(1), _day(2)]
    rows = {r.work_date.isoformat(): r for r in _entries(db_session, worker.id)}
    assert rows[_day(1)].status == "active" and rows[_day(2)].status == "active"
    assert rows[_day(3)].status == "cancelled" and rows[_day(3)].status_reason == "ops_recorded_decline"
    again = api_client.post(url, json={"reason": "体調不良"}, headers=_auth(ops_user.username))
    assert again.json()["recorded"] is False


def test_end_participation_before_start_cancels_today(api_client, db_session, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    """当日の開始前（朝の欠勤連絡）は当日も取り消す。画面の確認に当日の開始時刻を出す。"""
    worker = _worker(db_session, "稼働者A")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 2))
    _link(api_client, ops_user, worker.id, "U123")
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    first_day = date.fromisoformat(_day(1))
    moment = datetime(first_day.year, first_day.month, first_day.day, 7, 0, tzinfo=ws.JST)
    monkeypatch.setattr(ws, "now_utc", lambda: moment.astimezone(timezone.utc))
    monkeypatch.setattr(ws, "today_jst", lambda: first_day)
    detail = api_client.get(f"/api/order-requests/versions/{v1['id']}", headers=_auth(ops_user.username)).json()
    preview = detail["deliveries"][0]["end_preview"]
    assert preview["kept_dates"] == [] and preview["today_removed_start"] == "09:00"
    url = f"/api/order-requests/documents/{v1['document_id']}/workers/{worker.id}/withdraw-acceptance"
    assert api_client.post(url, json={"reason": "寝坊"}, headers=_auth(ops_user.username)).status_code == 200
    assert {r.status for r in _entries(db_session, worker.id)} == {"cancelled"}
