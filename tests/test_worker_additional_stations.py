"""Multiple stations survive both registration paths, review and concurrent edits."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.domain.line_registration_input import LineRegistrationInputError, normalize_line_registration
from src.domain.worker_edit_guard import WorkerEditGuardError, issue_worker_edit_guard, verify_worker_edit_guard
from src.models.base import generate_ulid
from src.models.line_order import LineWorkerLink
from src.models.master import Worker, WorkerRegistrationRequestDetail
from src.models.transaction import AuditLog
from tests.registration_test_helpers import complete_registered_worker, submission_headers
from tests.test_api_master_lists import _with_edit_guard
from tests.test_line_registration_station import _admin, _body, _enable, _submit

STATIONS = [
    {"nearest_station": "代々木駅", "station_walk_minutes": 0},
    {"nearest_station": "新宿三丁目駅", "station_walk_minutes": None},
]


def test_admin_create_edit_omit_clear_and_validation(api_client, db_session):
    headers = _admin(db_session)
    profile = {"nearest_station": "新宿駅", "station_walk_minutes": 8, "additional_stations": STATIONS}
    created = api_client.post("/api/workers", json={"name": "複数駅", "profile": profile, "emergency_contact_phone": "09012345678", "emergency_contact_name": "連絡先", "emergency_contact_relationship": "家族"}, headers=headers)
    assert created.status_code == 200, created.text
    worker_id = created.json()["id"]
    assert created.json()["profile"]["additional_stations"] == STATIONS
    listed = api_client.get("/api/workers", headers=headers).json()["items"]
    assert next(row for row in listed if row["id"] == worker_id)["profile"]["additional_stations"] == STATIONS
    for extra in ({}, {"additional_stations": None}, {"additional_stations": STATIONS[:1]}, {"additional_stations": []}):
        updated = api_client.put(f"/api/workers/{worker_id}", headers=headers, json=_with_edit_guard(
            api_client, worker_id, headers, {"name": "複数駅", "profile": {**profile, **extra} if extra else {"nearest_station": "新宿駅", "station_walk_minutes": 8}},
        ))
        assert updated.status_code == 200, updated.text
        assert updated.json()["profile"]["additional_stations"] == (extra.get("additional_stations") if extra.get("additional_stations") is not None else STATIONS)
        assert updated.json()["profile"]["nearest_station"] == "新宿駅"
    invalid = api_client.post("/api/workers", headers=headers, json={"name": "不正", "profile": {"additional_stations": [{"nearest_station": "", "station_walk_minutes": 301}]}})
    assert invalid.status_code == 422
    assert any("additional_stations" in error["loc"] for error in invalid.json()["detail"])
    logs = db_session.query(AuditLog).filter_by(action="worker_updated", target_id=worker_id).all()
    assert len(logs) == 4
    assert any(log.before_value["profile"]["additional_stations"] == STATIONS and log.after_value["profile"]["additional_stations"] == STATIONS[:1] for log in logs)
    assert any(log.before_value["profile"]["additional_stations"] == STATIONS[:1] and log.after_value["profile"]["additional_stations"] == [] for log in logs)


def test_legacy_station_reads_without_migration_of_its_value(api_client, db_session, worker):
    worker.nearest_station, worker.station_walk_minutes = "既存駅", 12
    db_session.commit()
    headers = _admin(db_session)
    result = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=headers).json()["worker"]["profile"]
    assert result["additional_stations"] == []
    assert (result["nearest_station"], result["station_walk_minutes"]) == ("既存駅", 12)


@pytest.mark.parametrize("raw", ['{}', 'null', '[null]', '[{"nearest_station":"   "}]', '[{"nearest_station":"駅","station_walk_minutes":-1}]', '[{"nearest_station":"駅","station_walk_minutes":true}]'])
def test_invalid_additional_station_rejected(raw):
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration({"additional_stations": raw}, sent={"additional_stations"}, linked=True)


def test_line_new_registration_approval_and_replay(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    body = {**_body(), "additional_stations": json.dumps(STATIONS)}
    token, submitted = _submit(api_client, body)
    assert submitted.status_code == 200, submitted.text
    request_id = submitted.json()["request_id"]
    assert db_session.query(Worker).count() == 0
    assert db_session.query(WorkerRegistrationRequestDetail).filter_by(request_id=request_id).one().additional_stations == STATIONS
    replay = api_client.post("/api/line/registration/submissions", json=body, headers=submission_headers(api_client, token, "station-key"))
    assert replay.status_code == 200 and replay.json()["saved"] is True
    changed = api_client.post("/api/line/registration/submissions", json={**body, "additional_stations": "[]"}, headers=submission_headers(api_client, token, "station-key"))
    assert changed.status_code == 409
    headers = _admin(db_session)
    review = api_client.post(f"/api/line/registration/reviews/{request_id}/choice", json={"decision": "create_new"}, headers=headers)
    assert review.status_code == 200, review.text
    assert json.loads(review.json()["after"]["additional_stations"]) == STATIONS
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review.json()["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    worker = db_session.get(Worker, approved.json()["worker_id"])
    assert worker.additional_stations == STATIONS
    assert worker.nearest_station == "新宿駅"


@pytest.mark.parametrize("submitted_extra", [None, "[]"])
def test_line_existing_preserves_omitted_or_clears_explicit_stations(api_client, db_session, monkeypatch, worker, submitted_extra):
    _enable(monkeypatch)
    complete_registered_worker(worker)
    worker.additional_stations = STATIONS
    db_session.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-station-test", status="active", linked_at=datetime.now(timezone.utc)))
    db_session.commit()
    body = {"station_walk_minutes": "0"}
    if submitted_extra is not None:
        body["additional_stations"] = submitted_extra
    token, submitted = _submit(api_client, body)
    assert submitted.status_code == 200, submitted.text
    form = api_client.get("/api/line/registration/form", headers={"Authorization": f"Bearer {token}"})
    assert json.loads(form.json()["registered"]["additional_stations"]) == STATIONS
    request_id = submitted.json()["request_id"]
    headers = _admin(db_session)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers).json()
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    db_session.refresh(worker)
    assert worker.additional_stations == (STATIONS if submitted_extra is None else [])


def test_additional_station_concurrent_edit_blocks_line_and_admin(api_client, db_session, monkeypatch, worker):
    _enable(monkeypatch)
    complete_registered_worker(worker)
    worker.additional_stations = STATIONS
    db_session.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-station-test", status="active", linked_at=datetime.now(timezone.utc)))
    db_session.commit()
    guard = issue_worker_edit_guard(worker, "editor")
    _, submitted = _submit(api_client, {"station_walk_minutes": "0"})
    assert submitted.status_code == 200, submitted.text
    headers = _admin(db_session)
    request_id = submitted.json()["request_id"]
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers).json()
    worker.additional_stations = STATIONS[:1]
    db_session.commit()
    with pytest.raises(WorkerEditGuardError):
        verify_worker_edit_guard(guard, worker, "editor")
    blocked = api_client.post(f"/api/line/registration/reviews/{request_id}/approve", json={"comparison_ticket": review["comparison_ticket"]}, headers=headers)
    assert blocked.status_code == 409
    assert worker.additional_stations == STATIONS[:1]


def test_migration_preserves_existing_worker_and_pending_application():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261015a001_worker_additional_stations.py"
    spec = importlib.util.spec_from_file_location("additional_station_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("workers", "worker_registration_request_details"):
            connection.execute(text(f"CREATE TABLE {table} (id TEXT PRIMARY KEY, nearest_station TEXT, station_walk_minutes INTEGER)"))
            connection.execute(text(f"INSERT INTO {table} VALUES ('existing', 'old-station', 8)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        for table in ("workers", "worker_registration_request_details"):
            row = connection.execute(text(f"SELECT nearest_station, station_walk_minutes, additional_stations FROM {table}" )).one()
            assert tuple(row) == ("old-station", 8, None)
    engine.dispose()
