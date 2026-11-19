"""ダブルヘッダー（DEC-148）：2件の依頼書を束ね、2件同時に保存・確定し、1通で送り、まとめて返事を受ける。

今の依頼書（束なし）の動きは変えないこと、片方だけ保存・確定・返事されないことを確かめる。
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from src.domain import order_bundle as rules
from src.models.line_daily import WorkerScheduleEntry
from src.models.order_bundle import OrderRequestBundleDelivery, OrderRequestBundleLeg
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.models.transaction import AuditLog
from src.services import order_bundle as bundles
from src.services import worker_schedule as ws
from src.services.line_worker_portal import estimate_for
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
from tests.test_line_daily import _postback


def _day(offset: int) -> str:
    return (ws.today_jst() + timedelta(days=offset)).isoformat()


def _schedule(day: str, start: str, end: str, amount: str = "10000", *, gathering: str = "", unit: str = "day") -> dict:
    work = [{"id": "g1", "date_mode": "single", "from": day, "to": day, "start_time": start, "end_time": end, "gathering_time": gathering}]
    rates = [{"id": "r1", "work_group_id": "g1", "date_mode": "single", "from": day, "to": day, "amount": amount, "unit": unit}]
    return {"version": 1, "work_groups": work, "rates_follow_work": True, "rate_groups": rates}


def _leg(worker_ids, *, project, site, start, end, amount="10000", kind="test", day=None, **extra) -> dict:
    day = day or _day(2)
    conditions = {"format": "additional-request-v1", "project_name": project, "schedule": _schedule(day, start, end, amount)}
    body = {
        "kind": kind, "work_date_label": "", "site_name": site, "request_conditions": json.dumps(conditions),
        "body": "", "contact_name": "依頼担当", "contact_desk": "", "worker_ids": worker_ids,
        "follow_up_due_on": _day(1), "follow_up_due_time": "21:00",
    }
    body.update(extra)
    return body


def _create(api_client, ops_user, legs, travel=None):
    payload = {"legs": legs}
    if travel is not None:
        payload["travel_minutes"] = travel
    return api_client.post("/api/order-request-bundles", json=payload, headers=_auth(ops_user.username))


def _pair_legs(worker_ids, *, second_start="13:00", second_end="16:00", kind="test"):
    return [
        _leg(worker_ids, project="朝の巡回", site="会場A", start="08:00", end="10:00", amount="9000", kind=kind),
        _leg([], project="昼の調査", site="会場B", start=second_start, end=second_end, amount="12000", kind=kind),
    ]


# ---- 時間の確認（規則）---------------------------------------------------------------

def test_rules_overlap_short_gap_and_order():
    day = _day(3)
    early, late = _schedule(day, "08:00", "10:00"), _schedule(day, "10:30", "12:00")
    result = rules.check(late, early, 60)
    assert result["complete"] and result["order"] == [1, 0] and result["gap_minutes"] == 30 and result["short"] and not result["overlap"]
    assert rules.send_blockers(result) == []
    overlap = rules.check(early, _schedule(day, "09:30", "12:00"), 60)
    assert overlap["overlap"] and rules.send_blockers(overlap)
    # 集合時間があれば、それを2件目の始まりとして比べる
    gathering = rules.check(early, _schedule(day, "11:00", "12:00", gathering="10:15"), 10)
    assert gathering["gap_minutes"] == 15 and not gathering["short"]
    # 翌日に終わる1件目は、同じ日の2件目と重なる
    late_night = _schedule(day, "22:00", "02:00")
    late_night["work_groups"][0]["end_next_day"] = True
    night = rules.check(late_night, _schedule(day, "23:30", "23:50"), 0)
    assert night["overlap"]


def test_rules_require_same_single_day_and_sum_day_rates_only():
    assert rules.check(_schedule(_day(2), "08:00", "10:00"), _schedule(_day(3), "12:00", "13:00"), 60)["issues"]
    ranged = _schedule(_day(2), "08:00", "10:00")
    ranged["work_groups"][0]["date_mode"] = "range"
    assert rules.check(ranged, None, 60)["issues"]
    assert rules.legs_pay_total(_schedule(_day(2), "08:00", "10:00", "9000"), _schedule(_day(2), "12:00", "13:00", "12000.5"))["total"] == "21000.5"
    hourly = rules.legs_pay_total(_schedule(_day(2), "08:00", "10:00"), _schedule(_day(2), "12:00", "13:00", "1500", unit="hour"))
    assert hourly["total"] is None and hourly["hourly"]


# ---- 作成・保存 ---------------------------------------------------------------------

def test_create_saves_two_documents_with_shared_fields(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    response = _create(api_client, ops_user, _pair_legs([worker.id]))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["kind"] == "test" and data["travel_minutes"] == rules.PROVISIONAL_TRAVEL_MINUTES
    first, second = data["versions"]
    assert first["document_number"] != second["document_number"]
    assert first["status"] == second["status"] == "draft"
    # 送付先・期限は1件目にそろう
    assert second["draft_worker_ids"] == [worker.id] and second["follow_up_due_on"] == first["follow_up_due_on"]
    assert first["bundle"]["partner_document_number"] == second["document_number"]
    assert data["check"]["gap_minutes"] == 180 and data["pay"]["total"] == "21000"
    assert db_session.query(OrderRequestBundleLeg).count() == 2
    assert db_session.query(AuditLog).filter_by(action="order_request_bundle_created").count() == 1
    listed = api_client.get("/api/order-requests?kind=all", headers=_auth(ops_user.username)).json()
    assert {item["bundle"]["partner_document_number"] for item in listed["items"] if item["bundle"]} == {first["document_number"], second["document_number"]}


def test_formal_bundle_is_closed_until_tests_are_checked(api_client, db_session, ops_user, pdf_root):
    response = _create(api_client, ops_user, _pair_legs([], kind="formal"))
    assert response.status_code == 409 and "テスト区分" in response.json()["detail"]
    mixed = _pair_legs([])
    mixed[1]["kind"] = "formal"
    assert _create(api_client, ops_user, mixed).status_code == 400
    assert db_session.query(OrderRequestVersion).count() == 0


def test_save_rejects_different_days_and_unsupported_modes(api_client, db_session, ops_user, pdf_root):
    legs = _pair_legs([])
    legs[1] = _leg([], project="昼の調査", site="会場B", start="13:00", end="16:00", day=_day(5))
    response = _create(api_client, ops_user, legs)
    assert response.status_code == 400 and "同じ日" in response.json()["detail"]
    legs = _pair_legs([])
    legs[0]["allow_partial_accept"] = True
    assert _create(api_client, ops_user, legs).status_code == 409
    assert db_session.query(OrderRequestVersion).count() == 0  # 片方だけ残らない


def test_update_saves_both_and_blocks_single_leg_operations(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    other = _worker(db_session, "稼働者B")
    data = _create(api_client, ops_user, _pair_legs([worker.id])).json()
    first, second = data["versions"]
    # 1件ずつの保存・確定はできない
    single = api_client.patch(f"/api/order-requests/versions/{first['id']}", json={"site_name": "X"}, headers=_auth(ops_user.username))
    assert single.status_code == 409
    assert api_client.post(f"/api/order-requests/versions/{first['id']}/confirm", headers=_auth(ops_user.username)).status_code == 409
    body = {"travel_minutes": 30, "legs": [
        {"version_id": first["id"], "worker_ids": [worker.id, other.id], "site_name": "会場A2"},
        {"version_id": second["id"], "worker_ids": [worker.id], "site_name": "会場B2"},
    ]}
    updated = api_client.patch(f"/api/order-request-bundles/{data['id']}", json=body, headers=_auth(ops_user.username))
    assert updated.status_code == 200, updated.text
    out = updated.json()
    assert out["travel_minutes"] == 30
    assert out["versions"][0]["site_name"] == "会場A2" and out["versions"][1]["site_name"] == "会場B2"
    assert sorted(out["versions"][1]["draft_worker_ids"]) == sorted([worker.id, other.id])  # 1件目にそろう
    assert db_session.query(AuditLog).filter_by(action="order_request_bundle_travel_changed").count() == 1


# ---- 確定（2件同時）------------------------------------------------------------------

def test_overlap_cannot_be_confirmed_but_can_be_saved(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    data = _create(api_client, ops_user, _pair_legs([worker.id], second_start="09:30", second_end="12:00"))
    assert data.status_code == 200, data.text
    data = data.json()
    assert data["check"]["overlap"] and data["send_blockers"]
    confirmed = api_client.post(f"/api/order-request-bundles/{data['id']}/confirm", json={}, headers=_auth(ops_user.username))
    assert confirmed.status_code == 409 and "重なって" in confirmed.json()["detail"]
    assert {v.status for v in db_session.query(OrderRequestVersion).all()} == {"draft"}


def test_short_gap_needs_reason_then_confirms_both_together(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    data = _create(api_client, ops_user, _pair_legs([worker.id], second_start="10:20", second_end="12:00")).json()
    assert data["check"]["short"] and data["check"]["gap_minutes"] == 20
    url = f"/api/order-request-bundles/{data['id']}/confirm"
    refused = api_client.post(url, json={}, headers=_auth(ops_user.username))
    assert refused.status_code == 409 and "理由" in refused.json()["detail"]
    ok = api_client.post(url, json={"gap_reason": "隣のビルで徒歩5分"}, headers=_auth(ops_user.username))
    assert ok.status_code == 200, ok.text
    out = ok.json()
    assert {v["status"] for v in out["versions"]} == {"confirmed"} and all(v["has_pdf"] for v in out["versions"])
    assert out["gap_ack_reason"] == "隣のビルで徒歩5分" and len(out["pairs"]) == 1
    assert db_session.query(AuditLog).filter_by(action="order_request_bundle_gap_acknowledged").count() == 1
    assert db_session.query(AuditLog).filter_by(action="order_request_order_request_confirmed").count() == 0
    assert db_session.query(AuditLog).filter_by(action="order_request_confirmed").count() == 2
    # 送付後は変更版を作れない（片方が変わったときの扱いは後の段階）
    revise = api_client.post(f"/api/order-requests/versions/{out['versions'][0]['id']}/revise", json={"reason": "x"}, headers=_auth(ops_user.username))
    assert revise.status_code == 409


# ---- 送付と返事 --------------------------------------------------------------------

@pytest.fixture
def sent_bundle(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    data = _create(api_client, ops_user, _pair_legs([worker.id])).json()
    out = api_client.post(f"/api/order-request-bundles/{data['id']}/confirm", json={}, headers=_auth(ops_user.username)).json()
    pair = out["pairs"][0]
    single = api_client.post(f"/api/order-requests/deliveries/{pair['first_delivery_id']}/line-send", headers=_auth(ops_user.username))
    assert single.status_code == 409  # 1件ずつは送らない
    before = len(fake_line.pushes)
    sent = api_client.post(f"/api/order-request-bundles/{data['id']}/pairs/{pair['id']}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    assert len(fake_line.pushes) == before + 1  # 1通だけ
    return worker, data["id"], pair, sent.json()


def test_one_message_covers_both_and_both_rows_are_sent(db_session, fake_line, sent_bundle):
    worker, _bundle_id, pair, out = sent_bundle
    text = fake_line.pushes[-1][1][0]["text"]
    assert "【ダブルヘッダー】" in text and "朝の巡回" in text and "昼の調査" in text
    assert text.index("朝の巡回") < text.index("昼の調査")
    assert "報酬の合計（2件）: ¥21,000" in text and "180分" in text and text.count("PDF: https://") == 2
    buttons = fake_line.pushes[-1][1][1]["contents"]["body"]["contents"]
    assert [b["action"]["label"] for b in buttons if b["type"] == "button"] == ["2件とも受諾します", "2件とも辞退します"]
    rows = {d.id: d for d in db_session.query(OrderRequestDelivery).all()}
    assert rows[pair["first_delivery_id"]].send_status == rows[pair["second_delivery_id"]].send_status == "accepted"


def test_accept_records_both_and_makes_two_entries_on_one_day(api_client, db_session, fake_line, sent_bundle):
    worker, _bundle_id, pair, _out = sent_bundle
    response = _postback(api_client, f"or_accept:{pair['first_delivery_id']}")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    rows = [db_session.get(OrderRequestDelivery, pair[k]) for k in ("first_delivery_id", "second_delivery_id")]
    assert {r.ack_status for r in rows} == {"acked"}
    entries = db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id, status="active").order_by(WorkerScheduleEntry.start_time).all()
    assert [e.project_name for e in entries] == ["朝の巡回", "昼の調査"] and len({e.work_date for e in entries}) == 1
    estimate = estimate_for(db_session, entries)
    assert estimate["test"]["amount"] == "21000" and estimate["test"]["work_days"] == 1  # 合計は2件、稼働日数は1日
    assert "ダブルヘッダー" in fake_line.replies[-1][1]
    assert db_session.query(AuditLog).filter_by(action="order_request_bundle_acked").count() == 1
    # 2つ目の送付行のボタン（古い経路）からでも、同じ組として扱い二重に記録しない
    again = _postback(api_client, f"or_accept:{pair['second_delivery_id']}")
    assert again.status_code == 200 and "記録済み" in fake_line.replies[-1][1]


def test_decline_with_reason_records_both(api_client, db_session, fake_line, sent_bundle):
    worker, _bundle_id, pair, _out = sent_bundle
    _postback(api_client, f"or_decline:{pair['first_delivery_id']}")
    db_session.expire_all()
    assert {db_session.get(OrderRequestDelivery, pair[k]).ack_status for k in ("first_delivery_id", "second_delivery_id")} == {"decline_pending"}
    _webhook(api_client, {"events": [{"type": "message", "replyToken": "rr", "source": {"type": "user", "userId": "U123"},
                                       "message": {"type": "text", "text": "体調不良"}}]}, event_id="bundle-decline-text")
    db_session.expire_all()
    rows = [db_session.get(OrderRequestDelivery, pair[k]) for k in ("first_delivery_id", "second_delivery_id")]
    assert {r.ack_status for r in rows} == {"declined"} and {r.decline_reason for r in rows} == {"体調不良"}
    assert db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id, status="active").count() == 0


def test_cancelled_leg_stops_bundle_reply(api_client, db_session, ops_user, fake_line, sent_bundle):
    worker, bundle_id, pair, out = sent_bundle
    second_version = out["versions"][1]["id"]
    cancelled = api_client.post(f"/api/order-requests/versions/{second_version}/cancel", json={"reason": "取引先の都合"}, headers=_auth(ops_user.username))
    assert cancelled.status_code == 200, cancelled.text
    _postback(api_client, f"or_accept:{pair['first_delivery_id']}")
    assert "内容が変わった" in fake_line.replies[-1][1]
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, pair["first_delivery_id"]).ack_status == "unacked"


def test_reminder_is_sent_once_per_bundle(api_client, db_session, fake_line, sent_bundle):
    from datetime import datetime
    from src.services.line_order import LineOrderService
    before = len(fake_line.pushes)
    sent = LineOrderService(db_session).send_due_reminders(now=datetime.now(ws.JST) + timedelta(days=5))
    assert sent == 1 and len(fake_line.pushes) == before + 1


# ---- 設定（移動に必要な時間の初期値）-----------------------------------------------------

def test_travel_minutes_setting_is_provisional_until_changed(api_client, db_session, ops_user, pdf_root):
    first = api_client.get("/api/order-request-bundles/settings", headers=_auth(ops_user.username)).json()
    assert first["provisional"] and first["default_travel_minutes"] == 60 and first["revision"] == 0
    changed = api_client.put("/api/order-request-bundles/settings", json={"default_travel_minutes": 45, "revision": 0}, headers=_auth(ops_user.username))
    assert changed.status_code == 200, changed.text
    assert changed.json()["default_travel_minutes"] == 45 and not changed.json()["provisional"]
    stale = api_client.put("/api/order-request-bundles/settings", json={"default_travel_minutes": 30, "revision": 0}, headers=_auth(ops_user.username))
    assert stale.status_code == 409
    data = _create(api_client, ops_user, _pair_legs([])).json()
    assert data["travel_minutes"] == 45  # 新しい束は設定の初期値から始まる
    assert db_session.query(AuditLog).filter_by(action="order_request_bundle_settings_changed").count() == 1


def test_pair_rows_are_unique_per_worker(db_session, sent_bundle):
    assert db_session.query(OrderRequestBundleDelivery).count() == 1
    assert bundles.FORMAL_BUNDLES_ENABLED is False
