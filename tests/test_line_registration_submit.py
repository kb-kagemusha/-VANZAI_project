"""LINE登録の受付。入口はテストの中だけ有効にする。"""
from datetime import datetime, timedelta, timezone

from src.models.base import generate_ulid
from src.models.line_order import LineWorkerLink
from src.models.line_registration import LineRegistrationContext, LineRegistrationSession, LineRegistrationSubmitKey
from src.models.master import RegistrationRequest, Worker, WorkerRegistrationRequestDetail
from src.models.transaction import AuditLog
from src.services.line_registration import NOT_SAVED_MESSAGE


def _enable(monkeypatch):
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("LINE_LIFF_ID", "liff-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "login-channel")
    monkeypatch.setattr(
        "src.api.line_registration_routes.verify_line_id_token",
        lambda id_token: "U-line-1",
    )


def _body():
    return {
        "last_name": "山田",
        "first_name": "太郎",
        "last_name_furigana": "やまだ",
        "first_name_furigana": "たろう",
        "phone": "09000001111",
        "birth_date": "1990-01-02",
        "postal_code": "1000001",
        "prefecture": "東京都",
        "address1": "千代田区1-1",
        "address2": "",
    }


def _session(api_client) -> str:
    created = api_client.post("/api/line/registration/sessions", json={"id_token": "verified-by-test"})
    assert created.status_code == 200, created.text
    return created.json()["token"]


def _submit(api_client, token: str, key: str, body: dict | None = None):
    return api_client.post(
        "/api/line/registration/submissions",
        json=_body() if body is None else body,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )


def test_entry_stays_closed_without_flag(api_client):
    entry = api_client.get("/api/line/registration/entry")
    assert entry.status_code == 200
    assert entry.json() == {"enabled": False, "liff_id": None}
    created = api_client.post("/api/line/registration/sessions", json={"id_token": "x"})
    assert created.status_code == 403
    assert created.json()["detail"] == "LINEからの登録は受け付けていません"


def test_submit_is_idempotent_and_does_not_overwrite(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    token = _session(api_client)
    first = _submit(api_client, token, "key-a")
    assert first.status_code == 200, first.text
    assert first.json()["saved"] is True
    request_id = first.json()["request_id"]

    replay = _submit(api_client, token, "key-a")
    assert replay.status_code == 200, replay.text
    assert replay.json()["request_id"] == request_id
    assert replay.json()["saved"] is True

    changed = _submit(api_client, token, "key-a", {**_body(), "phone": "09000002222"})
    assert changed.status_code == 409
    db_session.expire_all()
    detail = db_session.query(WorkerRegistrationRequestDetail).filter_by(request_id=request_id).one()
    assert detail.phone == "09000001111"

    pending = _submit(api_client, token, "key-b", {**_body(), "phone": "09000003333"})
    assert pending.status_code == 200, pending.text
    assert pending.json()["saved"] is False
    assert pending.json()["message"] == NOT_SAVED_MESSAGE
    assert pending.json()["request_id"] == request_id
    db_session.expire_all()
    assert db_session.query(WorkerRegistrationRequestDetail).filter_by(request_id=request_id).one().phone == "09000001111"
    assert db_session.query(RegistrationRequest).count() == 1

    alias = _submit(api_client, token, "key-b", {**_body(), "phone": "09000003333"})
    assert alias.status_code == 200
    assert alias.json()["saved"] is False
    assert alias.json()["message"] == NOT_SAVED_MESSAGE

    request = db_session.get(RegistrationRequest, request_id)
    request.status = "approved"
    context = db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one()
    context.is_open = False
    db_session.commit()
    new_key = _submit(api_client, token, "key-c", {**_body(), "phone": "09000004444"})
    assert new_key.status_code == 200, new_key.text
    assert new_key.json()["request_id"] != request_id
    assert new_key.json()["saved"] is True
    db_session.expire_all()
    assert db_session.get(WorkerRegistrationRequestDetail, detail.id).phone == "09000001111"


def test_expired_session_and_link_change_do_not_save(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    before = db_session.query(RegistrationRequest).count()
    token = _session(api_client)
    row = db_session.query(LineRegistrationSession).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    expired = _submit(api_client, token, "key-expired")
    assert expired.status_code == 401
    assert db_session.query(RegistrationRequest).count() == before

    fresh = _session(api_client)
    worker = Worker(id=generate_ulid(), name="サンプル", is_active=True)
    db_session.add(worker)
    db_session.flush()
    db_session.add(
        LineWorkerLink(
            id=generate_ulid(),
            worker_id=worker.id,
            line_user_id="U-line-1",
            status="active",
            linked_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    changed = _submit(api_client, fresh, "key-link")
    assert changed.status_code == 409
    assert "保存しませんでした" in changed.json()["detail"]
    assert db_session.query(LineRegistrationSubmitKey).count() == 0
    audits = db_session.query(AuditLog).filter_by(action="line_registration_submit_rejected").all()
    assert audits
    assert all(item.actor == "line-registration" for item in audits)
    assert all("U-line-1" not in str(item.reason) for item in audits)
    assert all(item.before_value is None and item.after_value is None for item in audits)
