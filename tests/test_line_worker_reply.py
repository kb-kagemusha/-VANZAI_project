"""Web確認画面からの返事（統合計画 ③-C、D-09）：全日程で受諾・理由付きの辞退。トークと同じ結果・二重送信の防止・機能の公開。"""
from __future__ import annotations

import json

from src.models.line_daily import LineWorkerSubmitKey
from src.models.order_request import ACK_ACKED, ACK_DECLINED, OrderRequestDelivery
from src.services.line_worker import reply_notice_key
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
from tests.test_line_daily import _create_confirm, _entries, _payload, _release, _revise_confirm, _schedule, _send_and_accept
from tests.test_line_worker_pick import _session, liff_env  # noqa: F401

ALL = ("wk_wake", "wk_orders", "wk_schedule", "pick_dates", "web_home", "web_orders", "web_reply")


def _sent(api_client, ops_user, worker, **kw):
    version = _create_confirm(api_client, ops_user, [worker.id], **kw)
    delivery_id = version["deliveries"][0]["id"]
    sent = api_client.post(f"/api/order-requests/deliveries/{delivery_id}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    return version, delivery_id


def _recorder(monkeypatch):
    from src.services.line_messaging import LineCallResult

    sent = []

    class Recorder:
        def push_receipt(self, to, text, retry_key):
            sent.append((to, text, retry_key))
            return LineCallResult(200, "", "req")

    monkeypatch.setattr("src.services.line_worker.build_line_client", Recorder)
    return sent


def _reply(api_client, headers, delivery_id, action, reason="", key="k1"):
    return api_client.post(
        f"/api/line/worker/deliveries/{delivery_id}/reply",
        json={"action": action, "reason": reason},
        headers={**headers, "Idempotency-Key": key},
    )


def test_reply_requires_web_reply_feature(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _version, delivery_id = _sent(api_client, ops_user, worker)
    _release(db_session, actions=("wk_wake", "web_home", "web_orders"))
    headers = _session(api_client)
    assert api_client.get(f"/api/line/worker/deliveries/{delivery_id}/reply", headers=headers).status_code == 403
    assert _reply(api_client, headers, delivery_id, "accept").status_code == 403
    home = api_client.get("/api/line/worker/home", headers=headers).json()
    assert home["reply_enabled"] is False


def test_accept_all_from_web_matches_talk_and_is_idempotent(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch):
    sent = _recorder(monkeypatch)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _version, delivery_id = _sent(api_client, ops_user, worker, schedule=_schedule(1, 3))
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    view = api_client.get(f"/api/line/worker/deliveries/{delivery_id}/reply", headers=headers)
    assert view.status_code == 200, view.text
    assert view.json()["state"] == "open" and view.json()["can_pick"] is False  # 日付を選べない依頼書でも返事できる

    first = _reply(api_client, headers, delivery_id, "accept")
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "acked" and len(first.json()["accepted_dates"]) == 3
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_status == ACK_ACKED
    assert len([e for e in _entries(db_session, worker.id) if e.status == "active"]) == 3
    assert len(sent) == 1 and sent[0][0] == "U123" and sent[0][1].startswith("【受付】受諾を受け付けました。")  # 受付の通知（commit の後）
    assert sent[0][2] == reply_notice_key(delivery_id, "acked")

    again = _reply(api_client, headers, delivery_id, "accept")  # 同じキーの再送は同じ結果、通知は送らない
    assert again.json() == first.json()
    assert len(sent) == 1
    other_key = _reply(api_client, headers, delivery_id, "accept", key="k2")  # 別のキーでも二重には記録しない
    assert other_key.json()["outcome"] == "already"
    assert db_session.query(LineWorkerSubmitKey).filter(LineWorkerSubmitKey.worker_id == worker.id).count() == 2
    conflict = _reply(api_client, headers, delivery_id, "decline", reason="都合", key="k1")
    assert conflict.status_code == 409


def test_decline_from_web_requires_reason(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line, monkeypatch):
    sent = _recorder(monkeypatch)
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    _version, delivery_id = _sent(api_client, ops_user, worker)
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    assert _reply(api_client, headers, delivery_id, "decline", reason="  ").status_code == 400
    declined = _reply(api_client, headers, delivery_id, "decline", reason="体調不良のため", key="k2")
    assert declined.status_code == 200, declined.text
    assert declined.json()["outcome"] == "declined"
    db_session.expire_all()
    row = db_session.get(OrderRequestDelivery, delivery_id)
    assert row.ack_status == ACK_DECLINED and row.decline_reason == "体調不良のため"
    assert len(sent) == 1 and "理由：体調不良のため" in sent[0][1]


def test_reply_to_new_version_switches_schedule(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    _link(api_client, ops_user, worker.id, "U123")
    v1 = _create_confirm(api_client, ops_user, [worker.id], schedule=_schedule(1, 2))
    _send_and_accept(api_client, ops_user, v1["deliveries"][0]["id"])
    conditions = json.loads(_payload([worker.id], schedule=_schedule(2, 3))["request_conditions"])
    v2 = _revise_confirm(api_client, ops_user, v1["id"], request_conditions=json.dumps(conditions))
    new_delivery = v2["deliveries"][0]["id"]
    sent = api_client.post(f"/api/order-requests/deliveries/{new_delivery}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    # 旧い版には返事できない（回答受付版ではない）
    old = _reply(api_client, headers, v1["deliveries"][0]["id"], "accept", key="old")
    assert old.json()["outcome"] in ("superseded_version", "already")
    accepted = _reply(api_client, headers, new_delivery, "accept", key="new")
    assert accepted.json()["outcome"] == "acked"
    active = [e for e in _entries(db_session, worker.id) if e.status == "active"]
    assert {e.version_id for e in active} == {v2["id"]} and len(active) == 2


def test_reply_rejects_other_workers_delivery(api_client, db_session, ops_user, pdf_root, line_env, liff_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    other = _worker(db_session, "稼働者B")
    _link(api_client, ops_user, worker.id, "U123")
    theirs = _create_confirm(api_client, ops_user, [other.id])["deliveries"][0]["id"]
    _release(db_session, actions=ALL)
    headers = _session(api_client)
    assert api_client.get(f"/api/line/worker/deliveries/{theirs}/reply", headers=headers).status_code == 404
    result = _reply(api_client, headers, theirs, "accept")
    assert result.json()["outcome"] == "rejected"
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, theirs).ack_status != ACK_ACKED


def test_reply_notice_key_is_stable_per_delivery_and_outcome():
    assert reply_notice_key("d1", "acked") == reply_notice_key("d1", "acked")
    assert reply_notice_key("d1", "acked") != reply_notice_key("d1", "declined")
    assert reply_notice_key("d1", "acked") != reply_notice_key("d2", "acked")
