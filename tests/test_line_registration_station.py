"""Optional access information survives submission, review, approval and replay."""
import pytest
from datetime import datetime, timezone

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.domain.line_registration_input import LineRegistrationInputError, normalize_line_registration
from src.domain.worker_edit_guard import WorkerEditGuardError, issue_worker_edit_guard, verify_worker_edit_guard
from src.models.base import generate_ulid
from src.models.line_order import LineWorkerLink
from src.models.master import RegistrationRequest, Worker, WorkerRegistrationRequestDetail


def _enable(monkeypatch):
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("LINE_LIFF_ID", "station-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "test-channel")
    monkeypatch.setattr("src.api.line_registration_routes.verify_line_id_token", lambda _token: "U-station-test")


def _body():
    return {"last_name": "山田", "first_name": "太郎", "last_name_furigana": "やまだ", "first_name_furigana": "たろう",
            "phone": "09000001111", "birth_date": "1990-01-02", "postal_code": "1000001", "prefecture": "東京都", "address1": "千代田区1-1", "address2": "",
            "email": "worker@example.com", "nearest_station": "新宿駅", "station_walk_minutes": "0",
            "emergency_contact_phone": "09000002222", "emergency_contact_name": "山田 花子", "emergency_contact_relationship": "実母"}


def _submit(api_client, body, key="station-key"):
    session = api_client.post("/api/line/registration/sessions", json={"id_token": "test-only"})
    assert session.status_code == 200
    token = session.json()["token"]
    result = api_client.post("/api/line/registration/submissions", json=body, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key})
    return token, result


def _admin(db_session):
    admin = create_user_with_hashed_password(db=db_session, username="station-admin", email="station@example.com", password="test-only123", role="admin")
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': admin.username})}"}


@pytest.mark.parametrize("value", ["-1", "1.5", "301", "1e2", "true", "9" * 5000])
def test_walk_minutes_invalid_input(value):
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration({"station_walk_minutes": value}, sent={"station_walk_minutes"}, linked=True)


def test_zero_minutes_is_a_change_and_blank_keys_keep_old_hash():
    changed = normalize_line_registration({"station_walk_minutes": "0"}, sent={"station_walk_minutes"}, linked=True)
    assert changed.station_walk_minutes == 0
    assert changed.canonical()["station_walk_minutes"] == 0
    body = {key: value for key, value in _body().items() if key not in ("nearest_station", "station_walk_minutes")}
    old = normalize_line_registration(body, sent=set(body), linked=False).canonical()
    with_blanks = {**body, "nearest_station": "", "station_walk_minutes": ""}
    new = normalize_line_registration(with_blanks, sent=set(with_blanks), linked=False).canonical()
    assert old == new
    assert "nearest_station" not in new
    assert "station_walk_minutes" not in new


def test_new_worker_station_saved_only_after_approval(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    _, submitted = _submit(api_client, {**_body(), "nearest_station": "新宿駅", "station_walk_minutes": "0"})
    assert submitted.status_code == 200, submitted.text
    request_id = submitted.json()["request_id"]
    detail = db_session.query(WorkerRegistrationRequestDetail).filter_by(request_id=request_id).one()
    assert detail.nearest_station == "新宿駅"
    assert detail.station_walk_minutes == 0
    assert db_session.query(Worker).count() == 0
    headers = _admin(db_session)
    review = api_client.post(f"/api/line/registration/reviews/{request_id}/choice", json={"decision": "create_new"}, headers=headers)
    assert review.status_code == 200, review.text
    assert review.json()["after"]["nearest_station"] == "新宿駅"
    assert review.json()["after"]["station_walk_minutes"] == "0"
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review.json()["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    worker = db_session.get(Worker, approved.json()["worker_id"])
    db_session.refresh(worker)
    assert worker.nearest_station == "新宿駅"
    assert worker.station_walk_minutes == 0


def test_station_replay_and_competing_edit_are_guarded(api_client, db_session, monkeypatch, worker):
    _enable(monkeypatch)
    worker.nearest_station = "旧駅"
    worker.station_walk_minutes = 12
    db_session.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-station-test", status="active", linked_at=datetime.now(timezone.utc)))
    db_session.commit()
    old_edit_ticket = issue_worker_edit_guard(worker, "editor")
    token, submitted = _submit(api_client, {"station_walk_minutes": "0"})
    assert submitted.status_code == 200, submitted.text
    request_id = submitted.json()["request_id"]
    changed = api_client.post("/api/line/registration/submissions", json={"station_walk_minutes": "5"}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "station-key"})
    assert changed.status_code == 409
    headers = _admin(db_session)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers).json()
    worker.nearest_station = "別の管理者が変更した駅"
    db_session.commit()
    rejected = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review["comparison_ticket"]}, headers=headers)
    assert rejected.status_code == 409
    db_session.refresh(worker)
    assert worker.station_walk_minutes == 12
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    with pytest.raises(WorkerEditGuardError):
        verify_worker_edit_guard(old_edit_ticket, worker, "editor")
    fresh = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers).json()
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": fresh["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    db_session.refresh(worker)
    assert worker.nearest_station == "別の管理者が変更した駅"  # Blank station never clears an existing value.
    assert worker.station_walk_minutes == 0


def test_legacy_submission_can_replay_with_new_blank_fields(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    token, first = _submit(api_client, _body())
    assert first.status_code == 200
    replay = api_client.post("/api/line/registration/submissions", json=_body(), headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "station-key"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["request_id"] == first.json()["request_id"]
    assert db_session.query(RegistrationRequest).count() == 1
