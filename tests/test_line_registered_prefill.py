from datetime import datetime, timezone
from src.models.base import generate_ulid
from src.models.master import Worker, RegistrationRequest
from src.models.line_order import LineWorkerLink
from tests.test_line_registration_station import _enable
from tests.registration_test_helpers import complete_registered_worker


def linked_form(client, db, monkeypatch):
    _enable(monkeypatch)
    worker = complete_registered_worker(Worker(name="山田 太郎", is_active=True))
    other = complete_registered_worker(Worker(name="他の 人", is_active=True))
    db.add_all([worker, other]); db.flush()
    db.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-station-test", status="active", linked_at=datetime.now(timezone.utc)))
    db.commit()
    token = client.post("/api/line/registration/sessions", json={"id_token":"test-only"}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    form = client.get("/api/line/registration/form", headers=auth)
    assert form.status_code == 200
    return worker, auth, form


def test_form_only_returns_authenticated_linked_worker(api_client, db_session, monkeypatch):
    worker, auth, form = linked_form(api_client, db_session, monkeypatch)
    assert form.headers["cache-control"] == "no-store"
    assert form.json()["registered"]["last_name"] == "山田"
    assert form.json()["registered"]["first_name"] == "太郎"
    assert "他の" not in form.text
    assert worker.id not in form.text
    assert api_client.get("/api/line/registration/form").status_code == 401


def test_ticket_is_required_and_stale_input_is_rejected(api_client, db_session, monkeypatch):
    worker, auth, form = linked_form(api_client, db_session, monkeypatch)
    header = {**auth, "Idempotency-Key":"prefill-key"}
    assert api_client.post("/api/line/registration/submissions",json={"phone":"09000007777"},headers=header).status_code == 409
    header["X-Registration-Form-Ticket"] = form.json()["form_ticket"]
    worker.phone = "09000008888"; db_session.commit()
    assert api_client.post("/api/line/registration/submissions",json={"phone":"09000007777"},headers=header).status_code == 409
    assert db_session.query(RegistrationRequest).count() == 0


def test_partial_update_and_replay_after_master_change(api_client, db_session, monkeypatch):
    worker, auth, form = linked_form(api_client, db_session, monkeypatch)
    header = {**auth, "Idempotency-Key":"prefill-saved", "X-Registration-Form-Ticket":form.json()["form_ticket"]}
    body = {"phone":"09000007777"}
    first = api_client.post("/api/line/registration/submissions",json=body,headers=header)
    assert first.status_code == 200, first.text
    worker.phone = "09000008888"; db_session.commit()
    replay = api_client.post("/api/line/registration/submissions",json=body,headers=header)
    assert replay.status_code == 200 and replay.json()["request_id"] == first.json()["request_id"]


def test_missing_registered_field_requires_completion(api_client, db_session, monkeypatch):
    worker, auth, form = linked_form(api_client, db_session, monkeypatch)
    worker.email = None; db_session.commit()
    form = api_client.get("/api/line/registration/form",headers=auth).json()
    header = {**auth, "Idempotency-Key":"prefill-missing", "X-Registration-Form-Ticket":form["form_ticket"]}
    bad = api_client.post("/api/line/registration/submissions",json={"phone":"09000007777"},headers=header)
    assert bad.status_code == 422 and "メール" in bad.json()["detail"]
    good = api_client.post("/api/line/registration/submissions",json={"email":"completed@example.com"},headers=header)
    assert good.status_code == 200, good.text
