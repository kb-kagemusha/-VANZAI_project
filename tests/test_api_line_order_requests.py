"""公式LINEの紐付け、送信、受領。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.line_order import LineWorkerLink
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.services.line_order import ACCEPT_REPLY, DECLINE_PROMPT, DECLINE_RECORDED, REMINDER_TEXT, LineOrderService
from src.services.line_messaging import LineCallResult


def _token(username: str) -> str:
    return create_access_token({"sub": username})


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class FakeLine:
    def __init__(self):
        self.pushes: list[tuple[str, list[dict]]] = []
        self.replies: list[tuple[str, str]] = []
        self.push_status = 200

    def push_messages(self, to: str, messages: list[dict]) -> LineCallResult:
        self.pushes.append((to, messages))
        if self.push_status == 200:
            return LineCallResult(200, "", "req-1")
        if self.push_status == 0:
            return LineCallResult(0, "LINEへの接続に失敗しました", None)
        return LineCallResult(self.push_status, "rejected", None)

    def reply_text(self, reply_token: str, text: str) -> None:
        self.replies.append((reply_token, text))

    def profile_name(self, user_id: str) -> str | None:
        return "テストLINE"


@pytest.fixture
def line_env(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ID", "123456")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("LINE_PUBLIC_API_BASE", "https://api.example.test")


@pytest.fixture
def fake_line(monkeypatch):
    fake = FakeLine()
    monkeypatch.setattr("src.services.line_order.build_line_client", lambda: fake)
    return fake


@pytest.fixture
def pdf_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def ops_user(db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="line_ops",
        email="line_ops@example.com",
        password="pass123",
        role=UserRole.OPS.value,
    )
    db_session.commit()
    return user


def _worker(db_session, name: str) -> Worker:
    worker = Worker(id=generate_ulid(), name=name, is_active=True)
    db_session.add(worker)
    db_session.commit()
    return worker


def _confirm(api_client, ops_user, worker_id: str, *, kind: str = "test") -> dict:
    created = api_client.post(
        "/api/order-requests",
        json={
            "kind": kind,
            "work_date_label": "2026-10-06",
            "site_name": "検証現場",
            "request_conditions": "テスト",
            "body": "テスト本文",
            "contact_name": "担当",
            "contact_desk": "03-0000-0000",
            "worker_ids": [worker_id],
        },
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    confirmed = api_client.post(
        f"/api/order-requests/versions/{created.json()['id']}/confirm",
        headers=_auth(ops_user.username),
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _webhook(api_client, payload: dict, *, secret: str = "test-secret", event_id: str = "event-1"):
    body = dict(payload)
    events = []
    for event in body.get("events", []):
        copied = dict(event)
        copied.setdefault("webhookEventId", event_id)
        events.append(copied)
    raw = json.dumps({"events": events}).encode("utf-8")
    return api_client.post(
        "/api/line/webhook",
        content=raw,
        headers={"X-Line-Signature": _sign(raw, secret), "Content-Type": "application/json"},
    )


def _link(api_client, ops_user, worker_id: str, line_user_id: str = "U123", event_id: str = "event-1"):
    issued = api_client.post(
        "/api/order-requests/line-links/codes",
        json={"worker_id": worker_id},
        headers=_auth(ops_user.username),
    )
    assert issued.status_code == 200, issued.text
    code = issued.json()["code"]
    response = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-1",
                    "source": {"type": "user", "userId": line_user_id},
                    "message": {"type": "text", "text": code},
                }
            ]
        },
        event_id=event_id,
    )
    assert response.status_code == 200, response.text
    return issued.json()


def test_link_code_then_webhook_binds_the_sender(api_client, db_session, ops_user, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    issued = _link(api_client, ops_user, worker.id)
    assert issued["instruction"]
    listed = api_client.get("/api/order-requests/line-links", headers=_auth(ops_user.username))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["worker_name"] == "稼働者A"
    assert listed.json()["items"][0]["line_display_name"] == "テストLINE"
    assert "code" not in listed.json()["items"][0]
    assert fake_line.replies[0][1].startswith("紐付けました")
    assert db_session.query(LineWorkerLink).filter(LineWorkerLink.status == "active").count() == 1


def test_webhook_rejects_bad_signature(api_client, line_env):
    raw = b'{"events":[]}'
    response = api_client.post(
        "/api/line/webhook",
        content=raw,
        headers={"X-Line-Signature": "bad", "Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_same_webhook_event_does_not_link_twice(api_client, db_session, ops_user, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    issued = api_client.post(
        "/api/order-requests/line-links/codes",
        json={"worker_id": worker.id},
        headers=_auth(ops_user.username),
    )
    code = issued.json()["code"]
    payload = {
        "events": [
            {
                "type": "message",
                "replyToken": "reply-1",
                "source": {"type": "user", "userId": "U123"},
                "message": {"type": "text", "text": code},
            }
        ]
    }
    first = _webhook(api_client, payload, event_id="same-event")
    second = _webhook(api_client, payload, event_id="same-event")
    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(LineWorkerLink).count() == 1


def test_send_test_document_to_one_linked_worker_and_record_ack(
    api_client, db_session, ops_user, pdf_root, line_env, fake_line
):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    delivery_id = confirmed["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id, "U123")

    sent = api_client.post(
        f"/api/order-requests/deliveries/{delivery_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["deliveries"][0]["send_status"] == "accepted"
    assert body["deliveries"][0]["ack_status"] == "unacked"
    assert fake_line.pushes[0][0] == "U123"
    text = fake_line.pushes[0][1][0]["text"]
    assert "PDF: https://api.example.test/api/line/order-request-files/" in text
    pdf_url = text.split("PDF: ", 1)[1].strip()
    message = fake_line.pushes[0][1][1]
    buttons = [item for item in message["contents"]["body"]["contents"] if item["type"] == "button"]
    assert buttons[0]["action"]["label"] == "依頼の案件、受諾します"
    assert buttons[0]["action"]["data"] == f"or_accept:{delivery_id}"
    assert buttons[0]["color"] == "#06C755"
    assert buttons[1]["action"]["label"] == "今回は辞退します"
    assert buttons[1]["action"]["inputOption"] == "openKeyboard"
    assert buttons[1]["color"] == "#C8553D"
    token = pdf_url.rsplit("/", 1)[-1]
    pdf = api_client.get(f"/api/line/order-request-files/{token}")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    still = db_session.get(OrderRequestDelivery, delivery_id)
    assert still.ack_status == "unacked"

    acked = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "postback",
                    "replyToken": "reply-2",
                    "source": {"type": "user", "userId": "U123"},
                    "postback": {"data": f"or_ack:{delivery_id}"},
                }
            ]
        },
        event_id="ack-1",
    )
    assert acked.status_code == 200, acked.text
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_status == "acked"


def test_other_line_user_cannot_ack(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    delivery_id = confirmed["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id, "U123")
    sent = api_client.post(
        f"/api/order-requests/deliveries/{delivery_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert sent.status_code == 200, sent.text
    response = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "postback",
                    "replyToken": "reply-3",
                    "source": {"type": "user", "userId": "U999"},
                    "postback": {"data": f"or_ack:{delivery_id}"},
                }
            ]
        },
        event_id="ack-other",
    )
    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_status == "unacked"


def test_formal_document_is_sent_without_test_banner(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id, kind="formal")
    delivery_id = confirmed["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id)
    response = api_client.post(
        f"/api/order-requests/deliveries/{delivery_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert response.status_code == 200, response.text
    text = fake_line.pushes[0][1][0]["text"]
    assert "テスト・正式な発注ではありません" not in text
    assert "このメッセージはテスト送信です。" not in text
    assert "PDF: https://api.example.test/api/line/order-request-files/" in text


def test_send_requires_channel_settings(api_client, db_session, ops_user, pdf_root, monkeypatch, fake_line):
    monkeypatch.delenv("LINE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    response = api_client.post(
        f"/api/order-requests/deliveries/{confirmed['deliveries'][0]['id']}/line-send",
        headers=_auth(ops_user.username),
    )
    assert response.status_code == 503


def test_expired_code_is_rejected(api_client, db_session, ops_user, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    issued = api_client.post(
        "/api/order-requests/line-links/codes",
        json={"worker_id": worker.id},
        headers=_auth(ops_user.username),
    )
    from src.models.line_order import LineLinkCode

    row = db_session.query(LineLinkCode).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    response = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-4",
                    "source": {"type": "user", "userId": "U123"},
                    "message": {"type": "text", "text": issued.json()["code"]},
                }
            ]
        },
        event_id="expired",
    )
    assert response.status_code == 200
    assert db_session.query(LineWorkerLink).count() == 0
    assert "使えません" in fake_line.replies[0][1]


def test_revoke_stops_sending(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    _link(api_client, ops_user, worker.id)
    revoked = api_client.post(
        f"/api/order-requests/line-links/{worker.id}/revoke",
        json={"reason": "本人の申し出"},
        headers=_auth(ops_user.username),
    )
    assert revoked.status_code == 200, revoked.text
    response = api_client.post(
        f"/api/order-requests/deliveries/{confirmed['deliveries'][0]['id']}/line-send",
        headers=_auth(ops_user.username),
    )
    assert response.status_code == 409
    assert fake_line.pushes == []


def test_accept_and_decline_with_reason(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    delivery_id = confirmed["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id, "U123")
    sent = api_client.post(
        f"/api/order-requests/deliveries/{delivery_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert sent.status_code == 200, sent.text

    declined = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "postback",
                    "replyToken": "reply-decline",
                    "source": {"type": "user", "userId": "U123"},
                    "postback": {"data": f"or_decline:{delivery_id}"},
                }
            ]
        },
        event_id="decline-1",
    )
    assert declined.status_code == 200
    assert fake_line.replies[-1][1] == DECLINE_PROMPT
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_status == "decline_pending"

    reason = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-reason",
                    "source": {"type": "user", "userId": "U123"},
                    "message": {"type": "text", "text": "その日は別件です"},
                }
            ]
        },
        event_id="decline-reason",
    )
    assert reason.status_code == 200
    assert fake_line.replies[-1][1] == DECLINE_RECORDED
    db_session.expire_all()
    stored = db_session.get(OrderRequestDelivery, delivery_id)
    assert stored.ack_status == "declined"
    assert stored.decline_reason == "その日は別件です"

    other = _worker(db_session, "稼働者B")
    confirmed_b = _confirm(api_client, ops_user, other.id)
    other_id = confirmed_b["deliveries"][0]["id"]
    _link(api_client, ops_user, other.id, "U456", event_id="link-b")
    sent_b = api_client.post(
        f"/api/order-requests/deliveries/{other_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert sent_b.status_code == 200, sent_b.text
    accepted = _webhook(
        api_client,
        {
            "events": [
                {
                    "type": "postback",
                    "replyToken": "reply-accept",
                    "source": {"type": "user", "userId": "U456"},
                    "postback": {"data": f"or_accept:{other_id}"},
                }
            ]
        },
        event_id="accept-1",
    )
    assert accepted.status_code == 200
    assert fake_line.replies[-1][1] == ACCEPT_REPLY
    db_session.expire_all()
    assert db_session.get(OrderRequestDelivery, other_id).ack_status == "acked"

    listed = api_client.get("/api/order-requests/replies", headers=_auth(ops_user.username))
    assert listed.status_code == 200, listed.text
    by_worker = {row["worker_name"]: row for row in listed.json()["items"]}
    assert by_worker["稼働者A"]["ack_status"] == "declined"
    assert by_worker["稼働者A"]["decline_reason"] == "その日は別件です"
    assert by_worker["稼働者B"]["ack_status"] == "acked"


def test_reminder_is_sent_once_after_the_due_date(
    api_client, db_session, ops_user, pdf_root, line_env, fake_line
):
    worker = _worker(db_session, "稼働者A")
    confirmed = _confirm(api_client, ops_user, worker.id)
    delivery_id = confirmed["deliveries"][0]["id"]
    _link(api_client, ops_user, worker.id, "U123")
    sent = api_client.post(
        f"/api/order-requests/deliveries/{delivery_id}/line-send",
        headers=_auth(ops_user.username),
    )
    assert sent.status_code == 200, sent.text
    version = db_session.get(OrderRequestVersion, confirmed["id"])
    version.follow_up_due_on = date(2026, 10, 6)
    db_session.commit()

    service = LineOrderService(db_session)
    assert service.send_due_reminders(today=date(2026, 10, 6)) == 0
    assert service.send_due_reminders(today=date(2026, 10, 7)) == 1
    db_session.commit()
    assert fake_line.pushes[-1][1][0]["text"] == REMINDER_TEXT
    db_session.expire_all()
    assert service.send_due_reminders(today=date(2026, 10, 8)) == 0
    assert db_session.get(OrderRequestDelivery, delivery_id).ack_reminded_at is not None
