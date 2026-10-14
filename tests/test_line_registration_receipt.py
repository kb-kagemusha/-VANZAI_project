from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy.orm import sessionmaker

from src.models.line_registration import LineRegistrationReceipt
from src.models.master import RegistrationRequest, Worker
from src.models.transaction import AuditLog
from src.services.line_messaging import LineCallResult, LineMessagingClient
from src.services.line_registration_receipt import LineRegistrationReceiptService, dispatch_due_registration_receipts
from tests.test_line_registration_submit import _enable, _session, _submit, _body


class ReceiptClient:
    def __init__(self, *results):
        self.results = list(results) or [LineCallResult(200, "", "receipt-1")]
        self.calls = []

    def push_receipt(self, to, text, retry_key):
        self.calls.append((to, text, retry_key))
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result


def setup_receipt(api_client, db_session, monkeypatch, client):
    _enable(monkeypatch)
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    token = _session(api_client)
    response = _submit(api_client, token, "receipt-test")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    return token, response.json()["request_id"], db_session.get(LineRegistrationReceipt, response.json()["request_id"])


def test_receipt_is_sent_only_after_saved_request_and_once_on_replay(api_client, db_session, monkeypatch):
    client = ReceiptClient()
    token, request_id, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    assert receipt.status == "sent"
    assert receipt.sent_at is not None
    UUID(receipt.retry_key)
    assert client.calls == [("U-line-1", "登録を受付けました", receipt.retry_key)]
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    assert db_session.query(Worker).count() == 0
    assert _submit(api_client, token, "receipt-test").status_code == 200
    unsaved = _submit(api_client, token, "different-key", {**_body(), "phone": "09000009999"})
    assert unsaved.status_code == 200 and unsaved.json()["saved"] is False
    assert len(client.calls) == 1
    assert db_session.query(LineRegistrationReceipt).count() == 1
    audit = db_session.query(AuditLog).filter_by(action="line_registration_receipt_sent").one()
    assert "U-line-1" not in str(audit.after_value)


def test_invalid_input_does_not_send_or_queue_receipt(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    client = ReceiptClient()
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    token = _session(api_client)
    assert _submit(api_client, token, "invalid", {"last_name": "不足"}).status_code == 422
    assert client.calls == []
    assert db_session.query(LineRegistrationReceipt).count() == 0


def test_submit_rollback_does_not_send_or_preserve_notification(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    client = ReceiptClient()
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    token = _session(api_client)
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("test database failure")))
    assert _submit(api_client, token, "rollback").status_code == 500
    assert client.calls == []
    assert db_session.query(LineRegistrationReceipt).count() == 0
    assert db_session.query(RegistrationRequest).count() == 0


def test_failed_message_keeps_saved_request_and_backoff_uses_same_key(api_client, db_session, monkeypatch):
    client = ReceiptClient(LineCallResult(0, "timeout", None), LineCallResult(200, "", "receipt-2"))
    token, request_id, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    assert receipt.status == "pending" and receipt.attempt_count == 1
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    _submit(api_client, token, "receipt-test")
    assert len(client.calls) == 1  # backoffを再送で迂回しない。
    LineRegistrationReceiptService(db_session, client).send(request_id, now=receipt.next_attempt_at.replace(tzinfo=timezone.utc))
    db_session.commit()
    assert receipt.status == "sent"
    assert len(client.calls) == 2
    assert client.calls[0] == client.calls[1]


@pytest.mark.parametrize("accepted_id,expected", [("accepted-before-crash", "sent"), (None, "failed")])
def test_409_is_success_only_with_line_accepted_request_header(api_client, db_session, monkeypatch, accepted_id, expected):
    client = ReceiptClient(LineCallResult(409, "retry", "new-request", accepted_id))
    _, _, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    assert receipt.status == expected


def test_unrecorded_success_is_retried_with_persisted_key(api_client, db_session, monkeypatch):
    client = ReceiptClient(LineCallResult(0, "first-timeout", None))
    _, request_id, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    moment = receipt.next_attempt_at.replace(tzinfo=timezone.utc)
    client.results = [LineCallResult(200, "", "accepted"), LineCallResult(409, "already accepted", "retry", "accepted")]
    LineRegistrationReceiptService(db_session, client).send(request_id, now=moment)
    db_session.rollback()  # API受理後にDB結果の保存が失敗した場合。
    receipt = db_session.get(LineRegistrationReceipt, request_id)
    assert receipt.status == "pending"
    LineRegistrationReceiptService(db_session, client).send(request_id, now=moment)
    db_session.commit()
    assert receipt.status == "sent"
    assert len({call[2] for call in client.calls}) == 1


def test_retry_stops_at_five_attempts_and_before_24_hour_dedupe_expiry(api_client, db_session, monkeypatch):
    client = ReceiptClient(LineCallResult(503, "unavailable", None))
    _, request_id, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    for _ in range(4):
        LineRegistrationReceiptService(db_session, client).send(request_id, now=receipt.next_attempt_at.replace(tzinfo=timezone.utc))
        db_session.commit()
    assert receipt.status == "failed" and receipt.attempt_count == 5
    LineRegistrationReceiptService(db_session, client).send(request_id, now=datetime.now(timezone.utc) + timedelta(days=2))
    assert len(client.calls) == 5
    receipt.status = "pending"
    receipt.attempt_count = 1
    receipt.next_attempt_at = datetime.now(timezone.utc)
    LineRegistrationReceiptService(db_session, client).send(request_id, now=receipt.created_at.replace(tzinfo=timezone.utc) + timedelta(hours=23))
    assert receipt.status == "failed" and len(client.calls) == 5


def test_restart_queue_sends_due_receipt_without_resubmission(api_client, db_session, monkeypatch):
    client = ReceiptClient(LineCallResult(500, "unavailable", None), LineCallResult(200, "", "receipt"))
    _, request_id, receipt = setup_receipt(api_client, db_session, monkeypatch, client)
    receipt.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    dispatch_due_registration_receipts(sessionmaker(bind=db_session.get_bind()))
    db_session.expire_all()
    assert db_session.get(LineRegistrationReceipt, request_id).status == "sent"


def test_push_transport_includes_retry_key_and_reads_accepted_header(monkeypatch):
    import io
    import urllib.error
    from src.services.line_messaging import LineSettings

    captured = []
    monkeypatch.setattr("src.services.line_messaging.line_settings", lambda: LineSettings("test", "test", "fake-token", "test"))
    def reject(request, timeout):
        captured.append(request)
        raise urllib.error.HTTPError(request.full_url, 409, "Conflict", {"X-Line-Accepted-Request-Id": "accepted"}, io.BytesIO(b'{"message":"already accepted"}'))
    monkeypatch.setattr("src.services.line_messaging.urllib.request.urlopen", reject)
    result = LineMessagingClient().push_receipt("U-test", "登録を受付けました", "11111111-1111-4111-8111-111111111111")
    assert captured[0].get_header("X-line-retry-key") == "11111111-1111-4111-8111-111111111111"
    assert result.status == 409 and result.accepted_request_id == "accepted"
