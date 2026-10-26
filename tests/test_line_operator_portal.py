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


@pytest.mark.parametrize("view,start,expected", [("worker", "menu-dual", "menu-worker"), ("operator", "menu-worker", "menu-dual")])
def test_fresh_switch_uses_intent_when_line_still_returns_previous_menu(db_session, operator, monkeypatch, view, start, expected):
    from src.services.line_order import LineOrderService
    release(db_session)
    worker = Worker(name="兼務本人", is_active=True)
    db_session.add(worker); db_session.flush()
    db_session.add(LineWorkerLink(worker_id=worker.id, line_user_id="Uoperator", status="active", linked_at=ws.now_utc()))
    db_session.commit()
    client = FakeMenus(); client.menu = start
    monkeypatch.setattr("src.services.line_operator_menu.MenuClient", lambda: client)
    event = {"webhookEventId": "switch-1", "type": "postback", "timestamp": int(ws.now_utc().timestamp() * 1000),
             "source": {"type": "user", "userId": "Uoperator"}, "postback": {"data": f"op_menu:{view}"}}
    service = LineOrderService(db_session)
    assert service.handle_webhook({"events": [event]}) is False
    assert client.menu == expected
    # Duplicate delivery cannot replay an old choice over a newer menu.
    client.menu = start; client.calls.clear()
    assert service.handle_webhook({"events": [event]}) is False
    assert client.menu == start and client.calls == []
    for i, extra in enumerate([{"timestamp": int((ws.now_utc() - timedelta(minutes=2)).timestamp() * 1000)},
                               {"deliveryContext": {"isRedelivery": True}}]):
        assert service.handle_webhook({"events": [{**event, **extra, "webhookEventId": f"delayed-{i}"}]}) is False
        assert client.menu == start
    worker.is_active = False; db_session.commit()
    reconcile(db_session, "Uoperator", client, requested_view="worker"); db_session.commit()
    assert client.menu == "menu-ops"
    operator[2].status = "revoked"; db_session.commit()
    reconcile(db_session, "Uoperator", client, requested_view="worker")
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
    # The list never carries phone numbers or contact notes; the phone comes only from "私が連絡します".
    assert "phone" not in item and "contacts" not in item and item["next_action"]["step"]
    assert "09099998888" not in api_client.get("/api/line/operator/wake-status", headers=headers).text
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
    from scripts.line.operator_menu import operator_image
    dual, _ = operator_spec("2011980694-test", True, "test-worker")
    only, _ = operator_spec("2011980694-test", False, "test-worker")
    modes = [a["action"]["uri"].rsplit("m=", 1)[1] for a in only["areas"]]
    assert modes == ["wake", "today", "calendar", "orders", "availability"]
    assert len(dual["areas"]) == 6 and dual["areas"][5]["action"] == {"type": "richmenuswitch", "richMenuAliasId": "test-worker", "data": "op_menu:worker"}
    from pathlib import Path as _P
    entry_source = _P("apps/admin-web/src/pages/PublicLineOperatorEntry.tsx").read_text(encoding="utf-8")
    assert all(f'"{mode}"' in entry_source for mode in modes)
    for flag in (True, False):
        data = operator_image(flag)
        assert data.startswith(b"\x89PNG") and len(data) < 1024 * 1024
        from PIL import Image
        from io import BytesIO
        assert Image.open(BytesIO(data)).size == (2500, 1686)
    assert image_for(spec, labels).startswith(b"\x89PNG")
    for menu in (spec, dual, only):
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


def _second_operator(api_client, db_session, monkeypatch, role="ops"):
    staff = VanzaiStaff(id=generate_ulid(), name="運営二人目", phone="09033334444", is_active=True)
    db_session.add(staff); db_session.flush()
    user = create_user_with_hashed_password(db=db_session, username="portal-ops-2", email="portal-ops-2@test.example", password="test-password", role=role)
    user.vanzai_staff_id = staff.id
    db_session.add(LineStaffLink(id=generate_ulid(), staff_id=staff.id, line_user_id="Uoperator2", status="active", linked_at=ws.now_utc()))
    db_session.commit()
    monkeypatch.setattr("src.services.line_operator.line_id_token.verify_id_token", lambda token, channel: "Uoperator2")
    headers = session(api_client)
    monkeypatch.setattr("src.services.line_operator.line_id_token.verify_id_token", lambda token, channel: "Uoperator")
    return headers


def test_orders_list_receipt_status_and_operator_pdf_link(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    from src.models.line_operator import LineOperatorFileToken
    from src.models.order_request import OrderRequestDelivery
    worker, version = _accepted_today(api_client, db_session, ops_user)
    headers = session(api_client)
    day = ws.today_jst()
    result = api_client.get(f"/api/line/operator/orders?start={day}&end={day + timedelta(days=30)}", headers=headers)
    assert result.status_code == 200, result.text
    item = next(row for row in result.json()["items"] if row["version_id"] == version["id"])
    assert [row["worker_id"] for row in item["acked"]] == [worker.id] and item["has_pdf"] is True
    assert "counterparty_note" not in result.text and "request_conditions" not in result.text
    calendar = api_client.get(f"/api/line/operator/calendar?start={day}&end={day}&kind=orders", headers=headers).json()
    assert calendar["days"][0]["events"][0]["version_id"] == version["id"]
    acked_before = db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"]).one().acked_at
    link = api_client.post(f"/api/line/operator/orders/{version['id']}/pdf-link", headers=headers)
    assert link.status_code == 200, link.text
    url = link.json()["url"]
    assert url.startswith("https://") and link.json()["expires_minutes"] == 10
    path = url[url.index("/api/"):]
    pdf = api_client.get(path)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["cache-control"] == "no-store"
    db_session.expire_all()
    # Opening as an operator never changes the worker's receipt state.
    assert db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"]).one().acked_at == acked_before
    row = db_session.query(LineOperatorFileToken).one()
    assert row.token_hash != path.rsplit("/", 1)[1]
    # Permission is checked again when the link is opened.
    db_session.add(RoleAccessPolicy(role="ops", display_name="運営", permissions=["wake_status_read"])); db_session.commit()
    assert api_client.get(path).status_code == 403
    assert api_client.get(f"/api/line/operator/orders?start={day}&end={day}", headers=headers).status_code == 403
    db_session.query(RoleAccessPolicy).filter_by(role="ops").delete(); db_session.commit()
    row = db_session.query(LineOperatorFileToken).one(); row.expires_at = ws.now_utc() - timedelta(seconds=1); db_session.commit()
    assert api_client.get(path).status_code == 404
    assert api_client.get("/api/line/operator/order-files/not-a-token").status_code == 404
    assert api_client.post("/api/line/operator/orders/unknown/pdf-link", headers=headers).status_code == 404


def test_site_manager_defaults_cover_operator_menu_but_not_billing(db_session):
    from src.models.enums import Permission
    from src.services.auth import has_permission
    user = User(username="sm", email="sm@test.example", role="site_manager", is_active=True)
    assert has_permission(user, Permission.ORDER_READ) and has_permission(user, Permission.WAKE_STATUS_READ)
    assert not has_permission(user, Permission.ORDER_WRITE) and not has_permission(user, Permission.INVOICE_READ)


def test_republish_replaces_personal_menus_and_removes_old_ones(db_session, operator, monkeypatch):
    from scripts.line.operator_menu import republish
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "true")
    release(db_session)
    class RepublishFake(FakeMenus):
        def __init__(self):
            super().__init__(); self.created = 0; self.deleted = []
        def content(self, menu_id):
            from pathlib import Path
            return Path("scripts/line/rich_menu/a2.png").read_bytes()
        def call(self, method, path, payload=None, image=None):
            self.calls.append((method, path))
            if method == "GET" and path == "/user/all/richmenu": return {"richMenuId": "existing-default"}
            if method == "GET" and path == "/richmenu/alias/list": return {"aliases": [{"richMenuAliasId": "old-alias", "richMenuId": "menu-dual"}, {"richMenuAliasId": "other", "richMenuId": "unrelated"}]}
            if method == "GET": return {"size": {"width": 2500, "height": 1686}, "areas": [{"bounds": {"x": 0, "y": 0, "width": 833, "height": 843}, "action": {"type": "postback", "data": "wk_wake"}}]}
            if method == "POST" and path == "/richmenu": self.created += 1; return {"richMenuId": f"new-{self.created}"}
            if method == "POST" and path.startswith("/user/"): self.menu = path.rsplit("/", 1)[1]
            if method == "DELETE": self.deleted.append(path)
            return {}
    client = RepublishFake(); client.menu = "menu-ops"
    result = republish(db_session, client)
    assert result["republished"] is True and result["created"] == 3 and result["old_menus_removed"] == 3
    rows = db_session.query(LineOperatorMenuRelease).all()
    assert [r.active for r in sorted(rows, key=lambda r: r.created_at)] == [False, True]
    assert client.menu == "new-1"  # the operator-only person now has the new operator menu
    assert "/richmenu/alias/old-alias" in client.deleted and "/richmenu/alias/other" not in client.deleted
    assert {"/richmenu/menu-ops", "/richmenu/menu-dual", "/richmenu/menu-worker"} <= set(client.deleted)
    assert all(method == "GET" for method, path in client.calls if "/user/all/" in path)


def test_test_orders_are_shown_only_when_asked_and_marked(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    from tests.test_line_daily import _create_confirm, _link, _schedule, _send_and_accept, _worker
    worker = _worker(db_session, "テスト稼働者")
    version = _create_confirm(api_client, ops_user, [worker.id], kind="test", schedule=_schedule(0, 2))
    _link(api_client, ops_user, worker.id, "U-test")
    _send_and_accept(api_client, ops_user, version["deliveries"][0]["id"], "U-test")
    headers = session(api_client)
    day = ws.today_jst()
    assert api_client.get("/api/line/operator/wake-status", headers=headers).json()["total"] == 0
    wake = api_client.get("/api/line/operator/wake-status?include_test=true", headers=headers).json()
    assert wake["total"] == 1 and wake["items"][0]["is_test"] is True and wake["items"][0]["entries"][0]["is_test"] is True
    # The admin screen still shows formal orders only.
    admin = api_client.get("/api/line-daily/wake-status", headers={"Authorization": "Bearer " + create_access_token({"sub": ops_user.username})}).json()
    assert admin["total"] == 0
    # The list itself has no claim/phone endpoints any more; claiming happens from the LINE alert.
    assert api_client.post("/api/line/operator/wake-contacts/claim", headers=headers, json={"day": day.isoformat(), "worker_id": worker.id}).status_code in (404, 405)
    plain = api_client.get(f"/api/line/operator/calendar?start={day}&end={day}&kind=orders", headers=headers).json()
    assert all(not e.get("is_test") for d in plain["days"] for e in d["events"])
    marked = api_client.get(f"/api/line/operator/calendar?start={day}&end={day}&kind=orders&include_test=true", headers=headers).json()
    assert any(e["is_test"] and e["version_id"] == version["id"] for d in marked["days"] for e in d["events"])
    query = f"/api/line/operator/orders?start={day}&end={day + timedelta(days=5)}"
    assert all(i["version_id"] != version["id"] for i in api_client.get(query, headers=headers).json()["items"])
    item = next(i for i in api_client.get(query + "&include_test=true", headers=headers).json()["items"] if i["version_id"] == version["id"])
    assert item["is_test"] is True and [r["worker_id"] for r in item["acked"]] == [worker.id]


# ---- 起床の監視（0.54.0、DEC-126） ---------------------------------------------------------------

def _texts(messages):
    import json
    return json.dumps(messages, ensure_ascii=False)


def test_wake_monitor_reminds_worker_then_alerts_operators_and_renotifies(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    from datetime import datetime, time
    from src.models.line_daily import WakeMonitorSend
    from src.services.wake_monitor import WakeMonitorService
    from tests.test_line_daily import _postback
    worker, _ = _accepted_today(api_client, db_session, ops_user)  # 09:00 start, worker LINE U123
    worker.phone = "09099998888"; db_session.commit()
    second = _second_operator(api_client, db_session, monkeypatch)
    del second
    day = ws.today_jst()
    at = lambda h, m: datetime.combine(day, time(h, m))
    fake_line.pushes.clear()
    service = WakeMonitorService(db_session, fake_line)
    assert service.run(at(5, 59))["worker_reminder"] == 0
    assert service.run(at(6, 0))["worker_reminder"] == 1; db_session.commit()
    assert fake_line.pushes[-1][0] == "U123" and "wk_wake" in _texts(fake_line.pushes[-1][1])
    assert service.run(at(6, 5)) == {"worker_reminder": 0, "operator_alert": 0, "operator_reported": 0}
    assert service.run(at(6, 15))["operator_alert"] == 2; db_session.commit()
    alert = [p for p in fake_line.pushes if p[0] in ("Uoperator", "Uoperator2")]
    assert {p[0] for p in alert} == {"Uoperator", "Uoperator2"}
    body = _texts(alert[0][1])
    assert "起床報告がまだ" in body and "駅前イベント" in body and f"wa_claim:{worker.id}:{day.isoformat()}" in body
    assert "09099998888" not in body  # the phone appears only after claiming
    assert service.run(at(6, 20))["operator_alert"] == 0
    assert service.run(at(6, 25))["operator_alert"] == 2; db_session.commit()
    assert "2回目" in _texts(fake_line.pushes[-1][1])
    # Claim from the LINE alert: phone + result buttons to the claimer, a notice to the other operator.
    fake_line.pushes.clear(); fake_line.messages.clear()
    assert _postback(api_client, f"wa_claim:{worker.id}:{day.isoformat()}", "Uoperator").status_code == 200
    reply = _texts(fake_line.messages[-1][1])
    assert "tel:09099998888" in reply and "wa_res:" in reply
    assert [p[0] for p in fake_line.pushes] == ["Uoperator2"] and "運営本人さんが連絡します" in _texts(fake_line.pushes[0][1])
    # The other operator is told it is being handled and may take over.
    assert _postback(api_client, f"wa_claim:{worker.id}:{day.isoformat()}", "Uoperator2").status_code == 200
    assert "対応中" in _texts(fake_line.messages[-1][1]) and "wa_take:" in _texts(fake_line.messages[-1][1])
    db_session.expire_all()
    assert WakeMonitorService(db_session, fake_line).run(at(6, 35))["operator_alert"] == 0  # claimed: no more re-notify
    assert _postback(api_client, f"wa_res:{worker.id}:{day.isoformat()}:confirmed_awake", "Uoperator").status_code == 200
    assert "記録しました：電話で起床を確認" in _texts(fake_line.messages[-1][1])
    headers = session(api_client)
    row = api_client.get("/api/line/operator/wake-status", headers=headers).json()["items"][0]
    assert row["alerted"] is True and row["reminded"] is True and row["deadline"] == "06:00" and row["next_action"]["step"] == "resolved"
    assert db_session.query(WakeMonitorSend).filter_by(kind="worker_reminder").count() == 1


def test_wake_monitor_tells_operators_when_report_arrives_and_stops_at_start(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    from datetime import datetime, time
    from src.services.wake_monitor import WakeMonitorService
    from tests.test_line_daily import _postback, _release
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    day = ws.today_jst()
    at = lambda h, m: datetime.combine(day, time(h, m))
    service = WakeMonitorService(db_session, fake_line)
    service.run(at(6, 15)); db_session.commit()  # late first run: reminder and alert together
    _release(db_session)
    assert _postback(api_client, "wk_wake").status_code == 200
    db_session.expire_all()
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run(at(6, 20))["operator_reported"] == 1; db_session.commit()
    assert fake_line.pushes[0][0] == "Uoperator" and "起床報告が届きました" in _texts(fake_line.pushes[0][1])
    assert WakeMonitorService(db_session, fake_line).run(at(6, 21))["operator_reported"] == 0


def test_wake_monitor_skips_after_start_and_without_alert_permission(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    from datetime import datetime, time
    from src.services.wake_monitor import WakeMonitorService
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    day = ws.today_jst()
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run(datetime.combine(day, time(9, 0))) == {"worker_reminder": 0, "operator_alert": 0, "operator_reported": 0}
    db_session.add(RoleAccessPolicy(role="ops", display_name="運営", permissions=["wake_status_read"])); db_session.commit()
    WakeMonitorService(db_session, fake_line).run(datetime.combine(day, time(6, 15))); db_session.commit()
    assert all(to != "Uoperator" for to, _ in fake_line.pushes)


def test_wake_alert_buttons_reject_non_operators(api_client, db_session, operator, ops_user, pdf_root, line_env, fake_line):
    from tests.test_line_daily import _postback
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    fake_line.messages.clear()
    assert _postback(api_client, f"wa_claim:{worker.id}:{ws.today_jst().isoformat()}", "U123").status_code == 200
    assert "運営スタッフだけ" in _texts(fake_line.messages[-1][1])
