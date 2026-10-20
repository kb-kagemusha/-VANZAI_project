"""Complete new registration, partial updates and legacy replay/approval."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.domain.line_registration_input import normalize_line_registration
from src.models.base import generate_ulid
from src.models.line_registration import LineRegistrationSession, LineRegistrationContext, LineRegistrationSubmitKey
from src.models.master import RegistrationRequest, WorkerRegistrationRequestDetail, Worker
from src.services.line_registration import content_hash
from tests.test_line_registration_station import _body, _enable, _submit, _admin


@pytest.mark.parametrize("missing", ["email", "nearest_station", "station_walk_minutes", "emergency_contact_phone", "emergency_contact_name", "emergency_contact_relationship"])
def test_new_registration_requires_everything_except_building(api_client, db_session, monkeypatch, missing):
    _enable(monkeypatch)
    body = _body()
    del body[missing]
    _, submitted = _submit(api_client, body)
    assert submitted.status_code == 422
    assert db_session.query(RegistrationRequest).count() == 0


def test_emergency_saved_reviewed_and_applied(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    _, submitted = _submit(api_client, _body())
    assert submitted.status_code == 200, submitted.text
    request_id = submitted.json()["request_id"]
    detail = db_session.scalar(select(WorkerRegistrationRequestDetail).where(WorkerRegistrationRequestDetail.request_id == request_id))
    assert detail.line_registration_form_version == 2
    assert detail.emergency_contact_relationship == "実母"
    assert db_session.query(Worker).count() == 0
    headers = _admin(db_session)
    review = api_client.post(f"/api/line/registration/reviews/{request_id}/choice", json={"decision": "create_new"}, headers=headers).json()
    assert review["after"]["emergency_contact_name"] == "山田 花子"
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    worker = db_session.get(Worker, approved.json()["worker_id"])
    db_session.refresh(worker)
    assert worker.emergency_contact_phone == "09000002222"
    assert worker.emergency_contact_name == "山田 花子"
    assert worker.emergency_contact_relationship == "実母"


def test_old_request_replays_and_can_be_approved_without_new_requirements(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    created = api_client.post("/api/line/registration/sessions", json={"id_token": "test-only"})
    token = created.json()["token"]
    subject = db_session.scalar(select(LineRegistrationSession)).line_user_id
    old = {key: value for key, value in _body().items() if key not in ("email", "nearest_station", "station_walk_minutes", "emergency_contact_phone", "emergency_contact_name", "emergency_contact_relationship")}
    normalized = normalize_line_registration(old, sent=set(old), linked=False)
    request = RegistrationRequest(id=generate_ulid(), request_type="worker", source_type="public_form", status="pending", submitted_at=datetime.now(timezone.utc), failed_attempts=0)
    db_session.add(request)
    db_session.flush()
    db_session.add(WorkerRegistrationRequestDetail(id=generate_ulid(), request_id=request.id, last_name=old["last_name"], first_name=old["first_name"], last_name_furigana=old["last_name_furigana"], first_name_furigana=old["first_name_furigana"], phone=old["phone"], birth_date=normalized.birth_date, zipcode=old["postal_code"], prefecture=old["prefecture"], city_address=old["address1"], building_address=""))
    db_session.add(LineRegistrationContext(id=generate_ulid(), request_id=request.id, line_user_id=subject, is_open=True))
    db_session.add(LineRegistrationSubmitKey(id=generate_ulid(), line_user_id=subject, request_id=request.id, idempotency_key="legacy-key", content_hash=content_hash(normalized.canonical())))
    db_session.commit()
    replay = api_client.post("/api/line/registration/submissions", json=old, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "legacy-key"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["request_id"] == request.id
    headers = _admin(db_session)
    review = api_client.post(f"/api/line/registration/reviews/{request.id}/choice", json={"decision": "create_new"}, headers=headers).json()
    assert review["can_decide"] is True
    approved = api_client.post(f"/api/line/registration/reviews/{request.id}/approve", json={"comparison_ticket": review["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    assert db_session.query(RegistrationRequest).count() == 1


def test_web_new_registration_and_omitted_emergency_fields_keep_existing_values(api_client, db_session):
    headers = _admin(db_session)
    missing = api_client.post("/api/workers", json={"name": "Web新規", "profile": {}}, headers=headers)
    assert missing.status_code == 422
    created = api_client.post("/api/workers", json={"name": "Web新規", "profile": {}, "emergency_contact_phone": "09000002222", "emergency_contact_name": "山田 花子", "emergency_contact_relationship": "実母"}, headers=headers)
    assert created.status_code == 200, created.text
    worker_id = created.json()["id"]
    assert created.json()["emergency_contact_relationship"] == "実母"
    ticket = api_client.get(f"/api/workers/{worker_id}/edit-guard", headers=headers).json()["edit_guard"]
    updated = api_client.put(f"/api/workers/{worker_id}", json={"name": "Web更新", "edit_guard": ticket}, headers=headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["emergency_contact_phone"] == "09000002222"
    assert updated.json()["emergency_contact_name"] == "山田 花子"
    assert updated.json()["emergency_contact_relationship"] == "実母"
