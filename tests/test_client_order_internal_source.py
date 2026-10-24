"""Client contacts and order source must stay out of all worker-facing documents."""
import json
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from src.api.jwt_auth import create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.master import Client, ClientStaff
from src.models.order_request import OrderRequestVersion
from src.models.transaction import AuditLog
from tests.test_api_order_requests import ops_user, pdf_root, worker_user, _auth, _body, _worker
from tests.test_api_line_order_requests import line_env, fake_line, _link


@pytest.fixture(autouse=True)
def _allow_legacy_free_text_confirm(monkeypatch):
    """このファイルの試験は旧形式（文章の稼働時間）の確定を前提にする。必須化の試験は test_line_daily.py。"""
    monkeypatch.setattr("src.services.order_request_service.REQUIRE_SCHEDULE_ON_CONFIRM", False)


@pytest.fixture
def master_admin(db_session):
    user = create_user_with_hashed_password(db=db_session, username="client_admin", email="client_admin@example.test", password="test-password", role="admin")
    db_session.commit()
    return user


def source_rows(db):
    client = Client(id=generate_ulid(), name="INTERNAL-COMPANY-ONLY", phone="045-991-8877")
    other = Client(id=generate_ulid(), name="OTHER-INTERNAL-COMPANY")
    db.add_all([client, other]); db.flush()
    staff = ClientStaff(id=generate_ulid(), client_id=client.id, name="INTERNAL-CONTACT-ONLY", phone="090-9991-8877", is_active=True)
    db.add(staff); db.commit()
    return client, other, staff


def test_client_company_phone_and_multiple_contacts_created_in_one_transaction(api_client, db_session, master_admin):
    headers = _auth(master_admin.username)
    response = api_client.post("/api/clients", json={"name": "複数担当会社", "phone": "0451111111", "contacts": [{"name": "担当一", "phone": "09011111111"}, {"name": "担当二", "phone": "09022222222"}]}, headers=headers)
    assert response.status_code == 200, response.text
    client_id = response.json()["id"]
    assert response.json()["phone"] == "0451111111"
    contacts = api_client.get(f"/api/clients/{client_id}/staff", headers=headers).json()["items"]
    assert {(row["name"], row["phone"]) for row in contacts} == {("担当一", "09011111111"), ("担当二", "09022222222")}
    first = api_client.get(f"/api/clients/{client_id}/staff?limit=1&offset=0", headers=headers).json()
    second = api_client.get(f"/api/clients/{client_id}/staff?limit=1&offset=1", headers=headers).json()
    assert first["items"][0]["id"] != second["items"][0]["id"] and second["offset"] == 1 and second["total"] == 2
    updated = api_client.patch(f"/api/clients/{client_id}/phone", json={"phone": "0452222222"}, headers=headers)
    assert updated.status_code == 200 and updated.json()["phone"] == "0452222222"
    listed = api_client.get("/api/clients", headers=headers).json()["items"]
    assert next(row for row in listed if row["id"] == client_id)["phone"] == "0452222222"
    invalid = api_client.post("/api/clients", json={"name": "INVALID-CONTACT-COMPANY", "contacts": [{"name": "   ", "phone": "09011111111"}]}, headers=headers)
    assert invalid.status_code == 422
    assert not db_session.query(Client).filter(Client.name == "INVALID-CONTACT-COMPANY").first()
    audit = db_session.query(AuditLog).filter(AuditLog.action == "client_updated", AuditLog.target_id == client_id).one()
    assert "0452222222" not in json.dumps(audit.after_value)


def test_company_phone_edit_is_protected_and_validated(api_client, db_session, master_admin, worker_user):
    client, _, _ = source_rows(db_session)
    worker_account, _ = worker_user
    assert api_client.patch(f"/api/clients/{client.id}/phone", json={"phone": "123"}, headers=_auth(worker_account.username)).status_code == 403
    assert api_client.patch(f"/api/clients/{client.id}/phone", json={"phone": "1" * 21}, headers=_auth(master_admin.username)).status_code == 422
    assert db_session.get(Client, client.id).phone == "045-991-8877"


def test_internal_order_source_is_private_frozen_and_preserved_in_revision(api_client, db_session, ops_user, pdf_root, worker_user, line_env, fake_line, monkeypatch):
    client, other, staff = source_rows(db_session)
    worker = _worker(db_session, "依頼送付先")
    source = {"client_id": client.id, "client_staff_id": staff.id}
    conditions = json.dumps({"format": "additional-request-v1", "project_name": "PUBLIC-EVENT", "hours": "9:00～17:00", "fee": "20,000円"})
    from src.services import order_request_service as module
    render = module.render_order_request_pdf
    captured = []
    def capture(*args, **kwargs):
        captured.append(kwargs)
        return render(*args, **kwargs)
    monkeypatch.setattr(module, "render_order_request_pdf", capture)
    response = api_client.post("/api/order-requests", json=_body([worker.id], request_conditions=conditions, internal_source=source), headers=_auth(ops_user.username))
    assert response.status_code == 200, response.text
    version_id = response.json()["id"]
    private = response.json()["internal_source"]
    assert private["client_name"] == client.name and private["staff_phone"] == staff.phone
    assert api_client.get(f"/api/order-requests/versions/{version_id}", headers=_auth(worker_user[0].username)).status_code == 403
    confirmed = api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops_user.username))
    assert confirmed.status_code == 200, confirmed.text
    version = db_session.get(OrderRequestVersion, version_id)
    public_snapshot = json.dumps(version.snapshot_json, ensure_ascii=False)
    for secret in (client.name, client.phone, staff.name, staff.phone, "internal_source", client.id, staff.id):
        assert secret not in public_snapshot
        assert secret not in json.dumps(captured, ensure_ascii=False, default=str)
        assert secret not in version.request_conditions
    assert captured and captured[0]["contact_name"] == "依頼担当"
    _link(api_client, ops_user, worker.id, "U-INTERNAL-TEST")
    delivery_id = confirmed.json()["deliveries"][0]["id"]
    sent = api_client.post(f"/api/order-requests/deliveries/{delivery_id}/line-send", headers=_auth(ops_user.username))
    assert sent.status_code == 200, sent.text
    messages = fake_line.pushes[0][1]
    for secret in (client.name, client.phone, staff.name, staff.phone, "internal_source"):
        assert secret not in json.dumps(messages, ensure_ascii=False)
    token = messages[0]["text"].split("PDF: ", 1)[1].strip().rsplit("/", 1)[-1]
    pdf = api_client.get(f"/api/line/order-request-files/{token}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert api_client.patch(f"/api/order-requests/versions/{version_id}", json={"internal_source": None}, headers=_auth(ops_user.username)).status_code == 409
    client.name = "RENAMED-INTERNAL-COMPANY"; staff.phone = "09000000000"; db_session.commit()
    assert api_client.get(f"/api/order-requests/versions/{version_id}", headers=_auth(ops_user.username)).json()["internal_source"] == private
    revised = api_client.post(f"/api/order-requests/versions/{version_id}/revise", json={"reason": "確認用改訂"}, headers=_auth(ops_user.username))
    assert revised.status_code == 200 and revised.json()["internal_source"] == private
    event = db_session.query(AuditLog).filter(AuditLog.action == "order_request_internal_source_updated", AuditLog.target_id == version_id).one()
    assert event.actor and staff.phone not in json.dumps(event.after_value)


def test_internal_source_rejects_wrong_company_inactive_deleted_and_missing_contacts(api_client, db_session, ops_user):
    client, other, staff = source_rows(db_session)
    headers = _auth(ops_user.username)
    worker = _worker(db_session, "期間送付先")
    wrong = api_client.post("/api/order-requests", json=_body([worker.id], internal_source={"client_id": other.id, "client_staff_id": staff.id}), headers=headers)
    assert wrong.status_code == 400 and "属する" in wrong.json()["detail"]
    staff.is_active = False; db_session.commit()
    invalid = api_client.post("/api/order-requests", json=_body([worker.id], internal_source={"client_id": client.id, "client_staff_id": staff.id}), headers=headers)
    assert invalid.status_code == 400
    from datetime import datetime, timezone
    staff.is_active = True; staff.deleted_at = datetime.now(timezone.utc); db_session.commit()
    invalid = api_client.post("/api/order-requests", json=_body([worker.id], internal_source={"client_id": client.id, "client_staff_id": staff.id}), headers=headers)
    assert invalid.status_code == 400
    created = api_client.post("/api/order-requests", json=_body([worker.id], internal_source={"client_id": client.id, "client_staff_id": None}), headers=headers)
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]
    before = created.json()["internal_source"]
    rejected = api_client.patch(f"/api/order-requests/versions/{version_id}", json={"internal_source": {"client_id": "missing"}}, headers=headers)
    assert rejected.status_code == 400
    assert api_client.get(f"/api/order-requests/versions/{version_id}", headers=headers).json()["internal_source"] == before
    assert api_client.patch(f"/api/order-requests/versions/{version_id}", json={"internal_source": None}, headers=headers).json()["internal_source"] is None
    client.deleted_at = datetime.now(timezone.utc); db_session.commit()
    invalid = api_client.post("/api/order-requests", json=_body([worker.id], internal_source={"client_id": client.id}), headers=headers)
    assert invalid.status_code == 400


def test_additive_migration_keeps_old_rows_and_adds_legacy_contacts_without_duplicates():
    path = Path(__file__).parents[1] / "alembic/versions/20261014a001_client_phone_order_internal_source.py"
    spec = importlib.util.spec_from_file_location("client_phone_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE clients (id VARCHAR(26) PRIMARY KEY, contact_name VARCHAR(100), contact_email VARCHAR(255), deleted_at DATETIME)"))
        connection.execute(text("CREATE TABLE client_staff (id VARCHAR(26) PRIMARY KEY, client_id VARCHAR(26), name VARCHAR(100), email VARCHAR(255), phone VARCHAR(20), is_active BOOLEAN, created_at DATETIME, updated_at DATETIME, deleted_at DATETIME)"))
        connection.execute(text("CREATE TABLE order_request_versions (id VARCHAR(26) PRIMARY KEY, body TEXT, snapshot_json JSON)"))
        connection.execute(text("INSERT INTO clients VALUES ('company1', '旧担当者', 'old@example.test', NULL), ('company2', '登録済み担当', NULL, NULL)"))
        connection.execute(text("INSERT INTO client_staff (id, client_id, name, phone, is_active) VALUES ('staff2', 'company2', '登録済み担当', '09012345678', true)"))
        connection.execute(text("INSERT INTO order_request_versions VALUES ('version1', :body, :snapshot)"), {"body": "確定済み本文", "snapshot": json.dumps({"fixed": True})})
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(text("SELECT COUNT(*) FROM client_staff")).scalar() == 2
        assert connection.execute(text("SELECT phone FROM client_staff WHERE id='staff2'")).scalar() == "09012345678"
        assert connection.execute(text("SELECT body FROM order_request_versions WHERE id='version1'")).scalar() == "確定済み本文"
        assert {column["name"] for column in inspect(connection).get_columns("order_request_versions")} >= {"internal_client_id", "internal_client_staff_id", "internal_source_snapshot"}
        assert len(inspect(connection).get_foreign_keys("order_request_versions")) == 2
