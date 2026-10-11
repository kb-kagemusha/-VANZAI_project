"""LINE申請は、専用の審査ができるまで既存の承認・却下では処理しない。"""
from datetime import datetime, timezone

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.line_registration import LineRegistrationContext
from src.models.master import RegistrationRequest, Worker
from src.services.line_registration import EXISTING_REVIEW_UNAVAILABLE


def _enable(monkeypatch):
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("LINE_LIFF_ID", "liff-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "login-channel")
    monkeypatch.setattr(
        "src.api.line_registration_routes.verify_line_id_token",
        lambda id_token: "U-line-review",
    )


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


def _line_request(api_client) -> str:
    created = api_client.post("/api/line/registration/sessions", json={"id_token": "verified-by-test"})
    assert created.status_code == 200, created.text
    submitted = api_client.post(
        "/api/line/registration/submissions",
        json={
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
        },
        headers={
            "Authorization": f"Bearer {created.json()['token']}",
            "Idempotency-Key": "review-guard",
        },
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()["request_id"]


def test_existing_approve_and_reject_leave_line_requests_untouched(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = create_user_with_hashed_password(
        db=db_session,
        username="line_review_admin",
        email="line_review_admin@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    worker = Worker(id=generate_ulid(), name="反映しない", is_active=True)
    db_session.add(worker)
    db_session.commit()
    request_id = _line_request(api_client)
    headers = _auth(admin.username)

    approved = api_client.post(
        f"/api/registration-requests/{request_id}/approve",
        json={"approved_target_id": worker.id, "notes": "既存経路"},
        headers=headers,
    )
    assert approved.status_code == 409
    assert approved.json()["detail"] == EXISTING_REVIEW_UNAVAILABLE

    rejected = api_client.post(
        f"/api/registration-requests/{request_id}/reject",
        json={"reason": "既存経路"},
        headers=headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == EXISTING_REVIEW_UNAVAILABLE

    locked = api_client.post(f"/api/registration-links/{request_id}/reset-pin-lock", headers=headers)
    assert locked.status_code == 409

    db_session.expire_all()
    stored = db_session.get(RegistrationRequest, request_id)
    context = db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one()
    assert stored.status == "pending"
    assert stored.deleted_at is None
    assert context.is_open is True
    assert db_session.get(Worker, worker.id).name == "反映しない"

    plain = RegistrationRequest(
        id=generate_ulid(),
        request_type="worker",
        status="pending",
        source_type="public_form",
        failed_attempts=2,
        locked_at=datetime.now(timezone.utc),
    )
    db_session.add(plain)
    db_session.commit()
    plain_reject = api_client.post(
        f"/api/registration-requests/{plain.id}/reject",
        json={"reason": "従来フォーム"},
        headers=headers,
    )
    assert plain_reject.status_code == 200, plain_reject.text
    db_session.expire_all()
    assert db_session.get(RegistrationRequest, plain.id).status == "rejected"

    plain_lock = RegistrationRequest(
        id=generate_ulid(),
        request_type="worker",
        status="link_issued",
        source_type="public_form",
        failed_attempts=2,
        locked_at=datetime.now(timezone.utc),
    )
    db_session.add(plain_lock)
    db_session.commit()
    reset = api_client.post(f"/api/registration-links/{plain_lock.id}/reset-pin-lock", headers=headers)
    assert reset.status_code == 200, reset.text
    db_session.expire_all()
    unlocked = db_session.get(RegistrationRequest, plain_lock.id)
    assert unlocked.failed_attempts == 0
    assert unlocked.locked_at is None
