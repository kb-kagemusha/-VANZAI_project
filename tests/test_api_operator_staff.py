import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.master import VanzaiStaff, User
from src.models.operator_staff import LineStaffLink, LineStaffLinkCode
from src.models.transaction import AuditLog


@pytest.fixture
def admin(db_session):
    user = create_user_with_hashed_password(db=db_session, username="operator_admin", email="operator_admin@example.test", password="test-password", role="admin")
    db_session.commit()
    return user


def auth(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user.username})}


def body():
    return {"name": "運営試験", "phone": "09011112222", "can_drive": True, "smoking_area_ok": False, "emergency_contact_name": "家族", "emergency_contact_phone": "09033334444", "management_roles": ["現場管理", "基礎管理"]}


def create(api_client, admin):
    result = api_client.post("/api/operator-staff", json=body(), headers=auth(admin))
    assert result.status_code == 201, result.text
    return result.json()


def webhook(api_client, event, signature=True):
    event["source"].setdefault("type", "user")
    content = json.dumps({"events": [event]}).encode()
    sig = base64.b64encode(hmac.new(b"test-operator-secret", content, hashlib.sha256).digest()).decode() if signature else "bad"
    return api_client.post("/api/line/webhook", content=content, headers={"x-line-signature": sig, "Content-Type": "application/json"})


@pytest.fixture
def fake_line(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-operator-secret")
    class Fake:
        def profile_name(self, user_id): return "運営LINE名"
        def reply_text(self, *args): pass
    fake = Fake()
    monkeypatch.setattr("src.services.line_order.build_line_client", lambda: fake)
    return fake


def test_profile_persists_fields_but_never_grants_login_privileges(api_client, db_session, admin):
    data = create(api_client, admin)
    assert data["management_roles"] == ["現場管理", "基礎管理"]
    assert data["can_drive"] is True and data["smoking_area_ok"] is False
    assert not data["line_linked"]
    assert db_session.query(User).count() == 1
    result = api_client.get("/api/operator-staff", headers=auth(admin))
    assert result.json()["items"][0]["emergency_contact_name"] == "家族"
    assert db_session.query(AuditLog).filter_by(action="operator_staff_created").count() == 1


def test_profile_revision_prevents_stale_update_and_legacy_master_edit_keeps_new_fields(api_client, db_session, admin):
    data = create(api_client, admin)
    changed = {**body(), "name": "変更後", "profile_revision": 1}
    response = api_client.put(f"/api/operator-staff/{data['id']}", json=changed, headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["profile_revision"] == 2
    assert api_client.put(f"/api/operator-staff/{data['id']}", json=changed, headers=auth(admin)).status_code == 409
    response = api_client.put(f"/api/vanzai-staff/{data['id']}", json={"name": "旧画面変更", "role": "プレイングマネージャー"}, headers=auth(admin))
    assert response.status_code == 200
    staff = db_session.get(VanzaiStaff, data["id"]); db_session.refresh(staff)
    assert staff.profile_revision == 3 and staff.can_drive is True
    assert staff.management_roles == ["現場管理", "基礎管理"]


@pytest.mark.parametrize("role", ["worker", "ops", "accounting", "site_manager"])
def test_operator_contact_and_role_management_is_admin_only(api_client, db_session, role):
    user = create_user_with_hashed_password(db=db_session, username=role, email=f"{role}@example.test", password="test-password", role=role)
    db_session.commit()
    assert api_client.get("/api/operator-staff", headers=auth(user)).status_code == 403
    assert api_client.post("/api/operator-staff", json=body(), headers=auth(user)).status_code == 403


def test_signed_personal_code_links_operator_separately_and_deduplicates(api_client, db_session, admin, fake_line):
    staff = create(api_client, admin)
    issued = api_client.post(f"/api/operator-staff/{staff['id']}/line-code", headers=auth(admin)).json()
    assert issued["code"].startswith("OPS-")
    code = db_session.query(LineStaffLinkCode).one()
    assert code.code_hash != issued["code"]
    event = {"webhookEventId": "staff-test-1", "type": "message", "replyToken": "test", "source": {"userId": "U-operator"}, "message": {"type": "text", "text": issued["code"]}}
    assert webhook(api_client, event, signature=False).status_code == 400
    assert db_session.query(LineStaffLink).count() == 0
    assert webhook(api_client, event).status_code == 200
    assert webhook(api_client, event).status_code == 200
    assert db_session.query(LineStaffLink).count() == 1
    result = api_client.get("/api/operator-staff", headers=auth(admin)).json()["items"][0]
    assert result["line_linked"] and result["line_display_name"] == "運営LINE名"
    assert "line_user_id" not in result
    assert api_client.post(f"/api/operator-staff/{staff['id']}/line-code", headers=auth(admin)).status_code == 409
    assert api_client.post(f"/api/operator-staff/{staff['id']}/line-revoke", json={"reason": "解除試験"}, headers=auth(admin)).status_code == 200
    assert db_session.query(LineStaffLink).one().status == "revoked"


def test_expired_reissued_or_inactive_code_cannot_link(api_client, db_session, admin, fake_line):
    staff = create(api_client, admin)
    first = api_client.post(f"/api/operator-staff/{staff['id']}/line-code", headers=auth(admin)).json()
    second = api_client.post(f"/api/operator-staff/{staff['id']}/line-code", headers=auth(admin)).json()
    def event(code, event_id):
        return {"webhookEventId": event_id, "type": "message", "source": {"userId": "U-operator"}, "message": {"type": "text", "text": code}}
    assert webhook(api_client, event(first["code"], "old")).status_code == 200
    assert db_session.query(LineStaffLink).count() == 0
    profile = db_session.get(VanzaiStaff, staff["id"]); profile.is_active = False; db_session.commit()
    assert webhook(api_client, event(second["code"], "inactive")).status_code == 200
    assert db_session.query(LineStaffLink).count() == 0


def test_unfollow_revokes_operator_notification_destination(api_client, db_session, admin, fake_line):
    staff = create(api_client, admin)
    code = api_client.post(f"/api/operator-staff/{staff['id']}/line-code", headers=auth(admin)).json()["code"]
    webhook(api_client, {"webhookEventId": "link", "type": "message", "source": {"userId": "U-operator"}, "message": {"type": "text", "text": code}})
    webhook(api_client, {"webhookEventId": "unfollow", "type": "unfollow", "source": {"userId": "U-operator"}})
    assert db_session.query(LineStaffLink).one().status == "revoked"


def test_unknown_roles_rejected(api_client, admin):
    assert api_client.post("/api/operator-staff", json={**body(), "management_roles": ["unknown"]}, headers=auth(admin)).status_code == 422
