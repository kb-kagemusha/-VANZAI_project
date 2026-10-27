"""Client registration details survive saving, listing and phone editing."""
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.master import Client, ClientStaff
from src.models.transaction import AuditLog


@pytest.fixture
def admin_headers(db_session):
    user = create_user_with_hashed_password(db=db_session, username="client_admin", email="client@example.com", password="test-password", role="admin")
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


def test_client_details_roundtrip(api_client, db_session, admin_headers):
    response = api_client.post("/api/clients", headers=admin_headers, json={
        "name": "試験会社", "postal_code": "1500043", "address": "東京都渋谷区道玄坂1-2 試験ビル",
        "notes": " 社内のみの連絡事項 ", "contact_name": "担当一",
        "contacts": [{"name": "担当一", "role": " 営業部長 "}, {"name": "担当二", "role": "課長"}],
    })
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["postal_code"] == "1500043"
    assert saved["notes"] == "社内のみの連絡事項"
    company = db_session.get(Client, saved["id"])
    assert company.address == "東京都渋谷区道玄坂1-2 試験ビル"
    staff = db_session.query(ClientStaff).filter_by(client_id=company.id).all()
    assert {item.name: item.role for item in staff} == {"担当一": "営業部長", "担当二": "課長"}
    listed = api_client.get("/api/clients", headers=admin_headers).json()["items"][0]
    assert listed["postal_code"] == saved["postal_code"]
    assert listed["notes"] == saved["notes"]
    assert {contact["name"]: contact["role"] for contact in listed["contacts"]} == {"担当一": "営業部長", "担当二": "課長"}
    phone = api_client.patch(f"/api/clients/{company.id}/phone", headers=admin_headers, json={"phone": "0312345678"})
    assert phone.status_code == 200
    assert phone.json()["notes"] == saved["notes"]
    assert phone.json()["postal_code"] == saved["postal_code"]
    changed = api_client.put(f"/api/clients/{company.id}/staff/{staff[0].id}", headers=admin_headers, json={"name": staff[0].name, "role": "本部長", "is_active": True})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "本部長"
    log = db_session.query(AuditLog).filter_by(target_type="client", target_id=company.id, action="client_created").first()
    assert log.after_value["notes"] == saved["notes"]


def test_legacy_client_registration_still_accepts_missing_details(api_client, admin_headers):
    response = api_client.post("/api/clients", headers=admin_headers, json={"name": "旧形式"})
    assert response.status_code == 200
    assert response.json()["notes"] is None
    assert response.json()["postal_code"] is None


@pytest.mark.parametrize("details", [{"postal_code": "123-4567"}, {"postal_code": "123"}, {"contacts": [{"name": "担当", "role": "x" * 101}]}])
def test_client_rejects_invalid_details(api_client, db_session, admin_headers, details):
    response = api_client.post("/api/clients", headers=admin_headers, json={"name": "不正入力", **details})
    assert response.status_code == 422
    assert db_session.query(Client).count() == 0


def test_postal_migration_preserves_existing_company_data():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261020a001_client_postal_code.py"
    spec = importlib.util.spec_from_file_location("client_postal_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE clients (id TEXT PRIMARY KEY, address TEXT, notes TEXT)"))
        connection.execute(text("INSERT INTO clients VALUES ('legacy', 'existing address', 'existing memo')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        row = connection.execute(text("SELECT address, notes, postal_code FROM clients")).one()
        assert tuple(row) == ("existing address", "existing memo", None)
    engine.dispose()


def test_company_edit_preserves_contacts_and_audits_changes(api_client, db_session, admin_headers):
    response = api_client.post("/api/clients", headers=admin_headers, json={
        "name": "変更前", "phone": "0311111111", "address": "旧住所", "notes": "メモ",
        "contacts": [{"name": "担当", "role": "部長", "phone": "09011111111"}],
    })
    client_id = response.json()["id"]
    result = api_client.patch(f"/api/clients/{client_id}", headers=admin_headers, json={
        "name": " 変更後 ", "postal_code": "1234567", "address": "新住所", "notes": None,
    })
    assert result.status_code == 200, result.text
    assert result.json()["name"] == "変更後"
    assert result.json()["phone"] == "0311111111"
    assert result.json()["notes"] is None
    assert result.json()["postal_code"] == "1234567"
    contact = db_session.query(ClientStaff).filter_by(client_id=client_id).one()
    assert (contact.name, contact.role, contact.phone) == ("担当", "部長", "09011111111")
    listed = api_client.get("/api/clients", headers=admin_headers).json()["items"][0]
    assert listed["name"] == "変更後" and listed["address"] == "新住所"
    log = db_session.query(AuditLog).filter_by(target_type="client", target_id=client_id, action="client_updated").one()
    assert log.before_value == {"name": "変更前", "postal_code": None, "address": "旧住所", "notes": "メモ"}
    assert log.after_value == {"name": "変更後", "postal_code": "1234567", "address": "新住所", "notes": None}
    assert log.actor == "client_admin"


@pytest.mark.parametrize("details", [{"name": " "}, {"name": None}, {"postal_code": "123-4567"}, {"contacts": [{"name": " "}]}])
def test_company_edit_rejects_invalid_values(api_client, db_session, admin_headers, details):
    company = Client(id="company", name="変更不可")
    db_session.add(company)
    db_session.commit()
    result = api_client.patch("/api/clients/company", headers=admin_headers, json=details)
    assert result.status_code == 422
    db_session.refresh(company)
    assert company.name == "変更不可"


def test_company_edit_rejects_duplicate_code(api_client, db_session, admin_headers):
    db_session.add_all([Client(id="first", name="企業一", code="FIRST"), Client(id="second", name="企業二", code="SECOND")])
    db_session.commit()
    result = api_client.patch("/api/clients/second", headers=admin_headers, json={"code": " first ", "name": "変わらない"})
    assert result.status_code == 409
    db_session.expire_all()
    assert db_session.get(Client, "second").name == "企業二"


def test_company_edit_checks_permission_and_deleted_record(api_client, db_session, admin_headers):
    from datetime import datetime, timezone
    company = Client(id="deleted", name="削除済み", deleted_at=datetime.now(timezone.utc))
    db_session.add(company)
    user = create_user_with_hashed_password(db=db_session, username="read_only", email="readonly@example.com", password="test-password", role="ops")
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}
    assert api_client.patch("/api/clients/deleted", headers=headers, json={"name": "拒否"}).status_code == 403
    assert api_client.patch("/api/clients/deleted", headers=admin_headers, json={"name": "拒否"}).status_code == 404
    assert api_client.patch("/api/clients/missing", headers=admin_headers, json={"name": "拒否"}).status_code == 404


def test_company_and_contacts_save_together_without_replacing_untouched_rows(api_client, db_session, admin_headers):
    company = Client(id="combined", name="変更前", contact_name="担当一", contact_email="old@example.com")
    one = ClientStaff(id="one", client_id=company.id, name="担当一", role="課長", email="old@example.com", is_active=False, notes="保持するメモ")
    two = ClientStaff(id="two", client_id=company.id, name="担当二", is_active=True)
    db_session.add_all([company, one, two]); db_session.commit()
    result = api_client.patch("/api/clients/combined", headers=admin_headers, json={"name": "変更後", "contacts": [
        {"id": "one", "name": "担当一改", "role": "部長", "email": "new@example.com"},
        {"name": "担当三", "role": "主任", "phone": "09033333333"},
    ]})
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved["name"] == "変更後"
    assert saved["contact_name"] == "担当一改" and saved["contact_email"] == "new@example.com"
    rows = {row["name"]: row for row in saved["contacts"]}
    assert set(rows) == {"担当一改", "担当二", "担当三"}
    assert rows["担当一改"]["id"] == "one"
    assert rows["担当一改"]["is_active"] is False and rows["担当一改"]["notes"] == "保持するメモ"
    assert rows["担当二"]["id"] == "two"
    assert rows["担当三"]["phone"] == "09033333333"
    logs = db_session.query(AuditLog).filter_by(action="client_staff_updated", target_id="one").all()
    assert logs[0].before_value["role"] == "課長" and logs[0].after_value["role"] == "部長"
    assert db_session.query(AuditLog).filter_by(action="client_staff_created", target_id=rows["担当三"]["id"]).count() == 1
    # Saving again with returned IDs does not duplicate newly created contacts.
    again = api_client.patch("/api/clients/combined", headers=admin_headers, json={"contacts": [{"id": rows["担当三"]["id"], "name": "担当三"}]})
    assert again.status_code == 200 and len(again.json()["contacts"]) == 3


@pytest.mark.parametrize("contacts", [[{"id": "foreign", "name": "他社"}], [{"id": "one", "name": "変更"}, {"id": "one", "name": "重複"}], [{"id": "deleted", "name": "削除済み"}]])
def test_invalid_contact_rejects_whole_company_update(api_client, db_session, admin_headers, contacts):
    from datetime import datetime, timezone
    db_session.add_all([Client(id="combined", name="変更前"), Client(id="other", name="他社")])
    db_session.flush()
    db_session.add_all([ClientStaff(id="one", client_id="combined", name="担当一"), ClientStaff(id="foreign", client_id="other", name="他社担当"), ClientStaff(id="deleted", client_id="combined", name="削除済み", deleted_at=datetime.now(timezone.utc))])
    db_session.commit()
    response = api_client.patch("/api/clients/combined", headers=admin_headers, json={"name": "保存されない", "contacts": contacts})
    assert response.status_code in (404, 422)
    db_session.expire_all()
    assert db_session.get(Client, "combined").name == "変更前"
    assert db_session.get(ClientStaff, "one").name == "担当一"
    assert db_session.query(AuditLog).count() == 0


def test_failed_commit_rolls_back_company_contact_and_audit(api_client, db_session, admin_headers, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    db_session.add(Client(id="combined", name="変更前")); db_session.flush()
    db_session.add(ClientStaff(id="one", client_id="combined", name="担当一")); db_session.commit()

    def fail_commit():
        db_session.flush()
        raise IntegrityError("simulated commit failure", None, Exception("test constraint failure"))

    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = api_client.patch("/api/clients/combined", headers=admin_headers, json={"name": "反映しない", "contacts": [
        {"id": "one", "name": "改名しない"}, {"name": "追加しない"},
    ]})
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(Client, "combined").name == "変更前"
    assert db_session.get(ClientStaff, "one").name == "担当一"
    assert db_session.query(ClientStaff).count() == 1
    assert db_session.query(AuditLog).count() == 0


def test_list_contacts_stays_scoped_to_company_page_and_excludes_deleted(api_client, db_session, admin_headers):
    from datetime import datetime, timezone
    db_session.add_all([Client(id="a", name="A社"), Client(id="b", name="B社"), Client(id="legacy", name="C社", contact_name="旧担当", contact_email="legacy@example.com")])
    db_session.flush()
    db_session.add_all([
        ClientStaff(id="a1", client_id="a", name="担当一", role="部長", phone="0311111111", email="first@example.com", is_active=True),
        ClientStaff(id="a2", client_id="a", name="担当二", role="課長", is_active=False),
        ClientStaff(id="a3", client_id="a", name="削除済み", deleted_at=datetime.now(timezone.utc)),
        ClientStaff(id="b1", client_id="b", name="他社担当"),
    ])
    db_session.commit()
    result = api_client.get("/api/clients", headers=admin_headers, params={"limit": 1, "offset": 0, "sort_by": "name", "sort_order": "asc"})
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total"] == 3 and len(page["items"]) == 1
    contacts = {contact["id"]: contact for contact in page["items"][0]["contacts"]}
    assert set(contacts) == {"a1", "a2"}
    assert contacts["a1"] == {"id": "a1", "name": "担当一", "role": "部長", "phone": "0311111111", "email": "first@example.com", "is_active": True}
    assert contacts["a2"]["is_active"] is False
    second = api_client.get("/api/clients", headers=admin_headers, params={"limit": 1, "offset": 1, "sort_by": "name", "sort_order": "asc"}).json()["items"][0]
    assert [contact["name"] for contact in second["contacts"]] == ["他社担当"]
    legacy = api_client.get("/api/clients", headers=admin_headers, params={"search": "C社"}).json()["items"][0]
    assert legacy["contacts"] == [] and legacy["contact_name"] == "旧担当"
