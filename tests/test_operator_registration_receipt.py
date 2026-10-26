from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from src.models.line_registration import LineRegistrationReceipt
from src.models.master import RegistrationRequest
from src.models.transaction import AuditLog
from src.services.line_messaging import LineCallResult
from src.services.line_registration_receipt import dispatch_due_registration_receipts
from tests.test_operator_registration import operator_setup, invite, submit


class Client:
    def __init__(self, *results):
        self.results = list(results) or [LineCallResult(200, "", "accepted")]
        self.calls = []
        self.before_send = lambda: None

    def push_receipt(self, to, text, retry_key):
        self.before_send()
        self.calls.append((to, text, retry_key))
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


def test_operator_receipt_is_exact_and_only_after_commit_and_once(api_client, db_session, operator_setup, monkeypatch):
    invitation = invite(api_client, operator_setup)
    client = Client()
    committed = []
    event.listen(db_session, "after_commit", lambda session: committed.append(True))
    client.before_send = lambda: pytest.fail("sent before commit") if not committed else None
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    response = submit(api_client, invitation)
    assert response.status_code == 200
    db_session.expire_all()
    receipt = db_session.get(LineRegistrationReceipt, invitation["request_id"])
    assert receipt.status == "sent"
    UUID(receipt.retry_key)
    assert client.calls == [("U-verified-person", "運営登録の申請を受け付けました", receipt.retry_key)]
    assert submit(api_client, invitation).status_code == 200
    assert submit(api_client, invitation, name="different").status_code == 409
    assert len(client.calls) == 1 and db_session.query(LineRegistrationReceipt).count() == 1
    audit = db_session.query(AuditLog).filter_by(action="line_registration_receipt_sent").one()
    assert "U-verified-person" not in str(audit.after_value)


def test_failed_operator_receipt_keeps_application_and_restarts_with_same_key(api_client, db_session, operator_setup, monkeypatch):
    client = Client(LineCallResult(0, "timeout", None), LineCallResult(200, "", "accepted"))
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    invitation = invite(api_client, operator_setup)
    assert submit(api_client, invitation).status_code == 200
    db_session.expire_all()
    receipt = db_session.get(LineRegistrationReceipt, invitation["request_id"])
    assert receipt.status == "pending" and receipt.attempt_count == 1
    assert db_session.get(RegistrationRequest, receipt.request_id).status == "pending"
    assert submit(api_client, invitation).status_code == 200
    assert len(client.calls) == 1
    receipt.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    dispatch_due_registration_receipts(sessionmaker(bind=db_session.get_bind()))
    db_session.expire_all()
    assert db_session.get(LineRegistrationReceipt, invitation["request_id"]).status == "sent"
    assert client.calls[0] == client.calls[1]


def test_operator_invalid_input_or_rollback_sends_no_receipt(api_client, db_session, operator_setup, monkeypatch):
    client = Client()
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    invitation = invite(api_client, operator_setup)
    assert submit(api_client, invitation, phone="bad").status_code == 422
    assert not client.calls and db_session.query(LineRegistrationReceipt).count() == 0
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("test save failure")))
    assert submit(api_client, invitation).status_code == 500
    assert not client.calls and db_session.query(LineRegistrationReceipt).count() == 0
    assert db_session.get(RegistrationRequest, invitation["request_id"]).status == "link_issued"


def test_old_operator_application_replay_is_not_backfilled(api_client, db_session, operator_setup, monkeypatch):
    invitation = invite(api_client, operator_setup)
    client = Client()
    monkeypatch.setattr("src.services.line_registration_receipt.build_line_client", lambda: client)
    # Simulate a pre-release application that has no receipt row.
    monkeypatch.setattr("src.api.operator_registration_routes.dispatch_registration_receipt", lambda *args: None)
    assert submit(api_client, invitation).status_code == 200
    receipt = db_session.get(LineRegistrationReceipt, invitation["request_id"])
    db_session.delete(receipt); db_session.commit()
    assert submit(api_client, invitation).status_code == 200
    assert db_session.query(LineRegistrationReceipt).count() == 0 and not client.calls
