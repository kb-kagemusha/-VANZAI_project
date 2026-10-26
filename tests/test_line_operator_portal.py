"""Operator session/role isolation, revocation, permissions and lifecycle menus."""
from datetime import timedelta
import hashlib
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.master import User, VanzaiStaff, Worker
from src.models.operator_staff import LineStaffLink
from src.models.line_operator import LineOperatorSession, LineOperatorMenuRelease, LineOperatorMenuState
from src.models.line_order import LineWorkerLink
from src.models.access_policy import RoleAccessPolicy
from src.services import worker_schedule as ws
from src.services.line_operator_menu import reconcile, MenuError
from tests.test_line_daily import _accepted_today, ops_user, pdf_root, line_env, fake_line  # noqa: F401


@pytest.fixture
def operator(db_session, monkeypatch):
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("LINE_OPERATOR_LIFF_ID", "2011980694-Operator")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "2011980694")
    monkeypatch.setattr("src.services.line_operator.line_id_token.verify_id_token", lambda token, channel: "Uoperator")
    staff = VanzaiStaff(id=generate_ulid(), name="運営本人", phone="09011112222", is_active=True)
    db_session.add(staff); db_session.flush()
    user = create_user_with_hashed_password(db=db_session, username="portal-ops", email="portal-ops@test.example", password="test-password", role="ops")
    user.vanzai_staff_id = staff.id
    link = LineStaffLink(id=generate_ulid(), staff_id=staff.id, line_user_id="Uoperator", status="active", linked_at=ws.now_utc())
    db_session.add(link); db_session.commit()
    return staff, user, link


def session(api_client):
    response = api_client.post("/api/line/operator/session", json={"id_token": "verified"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_operator_session_and_minimal_own_profile(api_client, db_session, operator):
    headers = session(api_client)
    result = api_client.get("/api/line/operator/me", headers=headers)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert result.json() == {"name": "運営本人", "phone": "09011112222", "permissions": {"wake": True, "orders": True, "availability": True}}
    token = headers["Authorization"][7:]
    assert db_session.query(LineOperatorSession).one().token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert api_client.get("/api/line/operator/wake-status", headers=headers).json()["total"] == 0


@pytest.mark.parametrize("change", ["worker", "inactive_user", "deleted_user", "inactive_staff", "unmapped", "ambiguous", "unlinked", "expired"])
def test_existing_session_rechecks_current_identity(api_client, db_session, operator, change):
    staff, user, link = operator
    headers = session(api_client)
    if change == "worker": user.role = "worker"
    elif change == "inactive_user": user.is_active = False
    elif change == "deleted_user": user.deleted_at = ws.now_utc()
    elif change == "inactive_staff": staff.is_active = False
    elif change == "unmapped": user.vanzai_staff_id = None
    elif change == "ambiguous":
        other = create_user_with_hashed_password(db=db_session, username="other-login", email="other@test.example", password="test-password", role="admin"); other.vanzai_staff_id = staff.id
    elif change == "unlinked": link.status = "revoked"
    elif change == "expired": db_session.query(LineOperatorSession).one().expires_at = ws.now_utc() - timedelta(seconds=1)
    db_session.commit()
    assert api_client.get("/api/line/operator/me", headers=headers).status_code in (401, 403)


def test_worker_role_never_gets_operator_session(api_client, db_session, operator):
    operator[1].role = "worker"; db_session.commit()
    assert api_client.post("/api/line/operator/session", json={"id_token": "verified"}).status_code == 403
    admin_style = {"Authorization": "Bearer " + create_access_token({"sub": operator[1].username})}
    assert api_client.get("/api/line/operator/me", headers=admin_style).status_code == 401


def test_permissions_are_live_and_each_calendar_kind_is_separate(api_client, db_session, operator):
    headers = session(api_client)
    policy = RoleAccessPolicy(role="ops", display_name="運営", permissions=["availability_read"])
    db_session.add(policy); db_session.commit()
    query = f"?start={ws.today_jst()}&end={ws.today_jst()}"
    assert api_client.get("/api/line/operator/wake-status", headers=headers).status_code == 403
    assert api_client.get("/api/line/operator/calendar" + query + "&kind=orders", headers=headers).status_code == 403
    assert api_client.get("/api/line/operator/calendar" + query + "&kind=availability", headers=headers).status_code == 200
    policy.permissions = ["order_read"]; db_session.commit()
    assert api_client.get("/api/line/operator/calendar" + query + "&kind=orders", headers=headers).status_code == 200
    assert api_client.get("/api/line/operator/calendar" + query + "&kind=availability", headers=headers).status_code == 403
    policy.permissions = []; db_session.commit()
    assert api_client.get("/api/line/operator/calendar" + query + "&kind=orders", headers=headers).status_code == 403


def test_admin_calendar_denies_worker_even_with_availability_permission(api_client, db_session, operator):
    user = operator[1]; user.role = "worker"; db_session.commit()
    headers = {"Authorization": "Bearer " + create_access_token({"sub": user.username})}
    response = api_client.get(f"/api/availability-calendar?date_from={ws.today_jst()}&date_to={ws.today_jst()}", headers=headers)
    assert response.status_code == 403


def test_calendar_ranges_and_no_write_endpoints(api_client, operator):
    headers = session(api_client)
    assert api_client.get("/api/line/operator/calendar?start=2026-10-26&end=2026-10-01", headers=headers).status_code == 400
    assert api_client.get("/api/line/operator/calendar?start=2026-01-01&end=2026-12-31", headers=headers).status_code == 400
    assert api_client.post("/api/line/operator/wake-status", headers=headers, json={}).status_code == 405
    assert api_client.get("/api/line/operator/me?staff_id=someone-else", headers=headers).json()["name"] == "運営本人"


class FakeMenus:
    def __init__(self): self.menu = None; self.calls = []; self.fail = False
    def current(self, subject):
        if self.fail: raise MenuError(503)
        return self.menu
    def call(self, method, path):
        self.calls.append((method, path))
        self.menu = path.rsplit("/", 1)[1] if method == "POST" else None
        return {}


def release(db):
    db.add(LineOperatorMenuRelease(menus={"operator_only": "menu-ops", "operator_dual": "menu-dual", "worker_dual": "menu-worker"}, active=True, created_at=ws.now_utc(), created_by="test")); db.commit()


def test_menu_preserves_native_switch_and_revocation_removes_personal_menu(db_session, operator):
    release(db_session)
    worker = Worker(id=generate_ulid(), name="兼務本人", is_active=True)
    db_session.add(worker); db_session.flush()
    db_session.add(LineWorkerLink(worker_id=worker.id, line_user_id="Uoperator", status="active", linked_at=ws.now_utc()))
    db_session.commit()
    client = FakeMenus()
    assert reconcile(db_session, "Uoperator", client) == "applied"; db_session.commit()
    assert client.menu == "menu-dual"
    client.menu = "menu-worker"; client.calls.clear()
    assert reconcile(db_session, "Uoperator", client) == "applied"; db_session.commit()
    assert client.calls == []
    operator[2].status = "revoked"; db_session.commit()
    reconcile(db_session, "Uoperator", client); db_session.commit()
    assert client.menu is None and client.calls[-1][0] == "DELETE"
    # A stale approval job must re-read current identity, not re-apply the old menu.
    reconcile(db_session, "Uoperator", client, force=True)
    assert client.menu is None


def test_menu_failure_is_durable_and_retry_uses_current_role(db_session, operator):
    release(db_session); client = FakeMenus(); client.fail = True
    assert reconcile(db_session, "Uoperator", client) == "failed"; db_session.commit()
    row = db_session.get(LineOperatorMenuState, "Uoperator")
    assert row.attempts == 1 and row.next_attempt_at is not None
    operator[1].role = "worker"; db_session.commit(); client.fail = False
    reconcile(db_session, "Uoperator", client, force=True)
    assert client.menu is None


def test_wake_and_order_calendar_share_real_accepted_schedule_without_private_fields(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    worker.phone = "09099998888"; db_session.commit()
    headers = session(api_client)
    admin_headers = {"Authorization": "Bearer " + create_access_token({"sub": ops_user.username})}
    original = api_client.get("/api/line-daily/wake-status", headers=admin_headers).json()
    result = api_client.get("/api/line/operator/wake-status", headers=headers).json()
    assert (result["total"], result["reported"]) == (original["total"], original["reported"])
    item = result["items"][0]
    assert item["worker_id"] == worker.id and item["entries"][0]["project_name"]
    assert "phone" not in item and "contacts" not in item and "next_action" not in item
    assert "site_address" not in item["entries"][0]
    day = ws.today_jst()
    calendar = api_client.get(f"/api/line/operator/calendar?start={day}&end={day}&kind=orders", headers=headers)
    assert calendar.status_code == 200, calendar.text
    assert calendar.json()["days"][0]["events"][0]["ok"][0]["worker_id"] == worker.id
    assert "request_conditions" not in calendar.text and "09099998888" not in calendar.text


def test_availability_uses_same_records_and_does_not_expose_notes(api_client, db_session, operator):
    from src.models.transaction import WorkerAvailability
    day = ws.today_jst()
    worker = Worker(name="全件可否確認", is_active=True, phone="090-private")
    db_session.add(worker); db_session.flush()
    db_session.add(WorkerAvailability(worker_id=worker.id, availability_date=day, status="available_all_day", notes="private availability note")); db_session.commit()
    headers = session(api_client)
    result = api_client.get(f"/api/line/operator/calendar?start={day}&end={day}&kind=availability", headers=headers)
    assert result.status_code == 200, result.text
    item = result.json()["workers"][0]
    assert item["name"] == worker.name and item["days"][day.isoformat()]["status"] == "available_all_day"
    assert "private" not in result.text


def test_admin_binding_is_explicit_and_does_not_grant_roles(api_client, db_session, operator):
    staff, user, _ = operator
    unauthorized = {"Authorization": "Bearer " + create_access_token({"sub": user.username})}
    path = f"/api/operator-access/{staff.id}"
    assert api_client.get(path, headers=unauthorized).status_code == 403
    admin = create_user_with_hashed_password(db=db_session, username="mapping-admin", email="mapping@test.example", password="test-password", role="admin")
    db_session.commit()
    headers = {"Authorization": "Bearer " + create_access_token({"sub": admin.username})}
    assert api_client.get(path, headers=headers).json()["user_ids"] == [user.id]
    assert api_client.put(path, headers=headers, json={"user_id": None}).status_code == 200
    assert api_client.post("/api/line/operator/session", json={"id_token": "verified"}).status_code == 403
    assert api_client.put(path, headers=headers, json={"user_id": user.id}).status_code == 200
    assert user.role == "ops"
    user.role = "worker"; db_session.commit()
    assert api_client.put(path, headers=headers, json={"user_id": user.id}).status_code == 409


def test_menu_images_and_actions_fit_without_changing_default():
    from scripts.line.operator_menu import operator_spec, worker_spec, image_for
    import json
    from pathlib import Path
    default = json.loads(Path("scripts/line/rich_menu/a2.json").read_text(encoding="utf-8"))["rich_menu"]
    before = json.dumps(default, sort_keys=True)
    spec, labels = worker_spec(default, "test-operator-alias")
    assert json.dumps(default, sort_keys=True) == before
    assert spec["areas"][0]["action"]["type"] == "richmenuswitch"
    assert [a["action"] for a in spec["areas"][1:]] == [a["action"] for a in default["areas"]]
    for menu, names in [(spec, labels), operator_spec("2011980694-test", True, "test-worker"), operator_spec("2011980694-test", False, "test-worker")]:
        data = image_for(menu, names)
        assert data.startswith(b"\x89PNG") and len(data) < 1024 * 1024
        for area in menu["areas"]:
            b = area["bounds"]
            assert b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["width"] <= 2500 and b["y"] + b["height"] <= 1686


def test_disabled_release_unlinks_owned_menus_and_is_not_automatically_republished(db_session, operator):
    from scripts.line.operator_menu import publish
    release(db_session); client = FakeMenus()
    reconcile(db_session, "Uoperator", client); db_session.commit()
    assert client.menu == "menu-ops"
    db_session.query(LineOperatorMenuRelease).one().active = False; db_session.commit()
    reconcile(db_session, "Uoperator", client, force=True); db_session.commit()
    assert client.menu is None
    assert publish(db_session, client) == {"published": False, "reason": "disabled_by_admin"}


def test_publishing_never_sets_global_default_and_is_idempotent(db_session, operator):
    from scripts.line.operator_menu import publish
    class PublishFake:
        def __init__(self): self.calls = []; self.created = 0
        def content(self, menu_id):
            from pathlib import Path
            return Path("scripts/line/rich_menu/a2.png").read_bytes()
        def call(self, method, path, payload=None, image=None):
            self.calls.append((method, path))
            if method == "GET" and path == "/user/all/richmenu": return {"richMenuId": "existing-default"}
            if method == "GET": return {"size": {"width": 2500, "height": 1686}, "areas": [{"bounds": {"x": 0, "y": 0, "width": 833, "height": 843}, "action": {"type": "postback", "data": "wk_wake"}}]}
            if path == "/richmenu": self.created += 1; return {"richMenuId": f"new-menu-{self.created}"}
            return {}
    client = PublishFake()
    assert publish(db_session, client)["default_unchanged"] is True
    assert client.created == 3
    before = list(client.calls)
    assert publish(db_session, client)["already_published"] is True
    assert client.calls == before
    assert all(method == "GET" for method, path in client.calls if "/user/all/" in path)


def test_follow_does_not_restore_revoked_identity_or_old_operator_menu(db_session, operator, monkeypatch):
    from src.services.line_order import LineOrderService
    release(db_session); client = FakeMenus()
    monkeypatch.setattr("src.services.line_operator_menu.MenuClient", lambda: client)
    reconcile(db_session, "Uoperator", client); db_session.commit()
    service = LineOrderService(db_session)
    for kind in ("unfollow", "follow"):
        assert service.handle_webhook({"events": [{"webhookEventId": f"portal-{kind}", "type": kind, "source": {"type": "user", "userId": "Uoperator"}}]}) is False
    assert db_session.get(LineStaffLink, operator[2].id).status == "revoked"
    assert client.menu is None


def test_invalid_id_token_never_issues_session(api_client, db_session, operator, monkeypatch):
    from src.services.line_id_token import LineIdTokenError
    def invalid(*args): raise LineIdTokenError()
    monkeypatch.setattr("src.services.line_operator.line_id_token.verify_id_token", invalid)
    assert api_client.post("/api/line/operator/session", json={"id_token": "invalid"}).status_code == 401
    assert db_session.query(LineOperatorSession).count() == 0
