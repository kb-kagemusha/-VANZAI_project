"""DESIGN_SPEC §5/16, DEC-056: role and account authorization boundaries."""
import pytest
from src.api.jwt_auth import create_user_with_hashed_password
from src.models.master import User
from src.models.transaction import AuditLog


def login(api, db, name, role):
    user = create_user_with_hashed_password(db, name, name + "@example.com", "password123", role)
    tokens = api.post("/api/auth/token", data={"username": name, "password": "password123"}).json()
    return user, {"Authorization": "Bearer " + tokens["access_token"]}


@pytest.mark.parametrize("role", ["ops", "accounting", "site_manager", "worker"])
def test_nonadmins_cannot_manage_ids_or_permissions(api_client, db_session, role):
    _, headers = login(api_client, db_session, "member", role)
    for method, url, body in [
        ("get", "/api/access/users", None), ("get", "/api/access/roles", None),
        ("post", "/api/access/users", {"username": "new", "display_name": "New", "email": "new@example.com", "password": "password123", "role": "admin"}),
        ("put", "/api/access/users/unknown", {"role": "admin", "is_active": True, "reason": "test"}),
        ("put", "/api/access/roles/ops", {"permissions": [], "reason": "test"}),
    ]:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        assert getattr(api_client, method)(url, **kwargs).status_code == 403


def test_admin_creates_id_without_exposing_password_and_duplicates_rejected(api_client, db_session):
    _, headers = login(api_client, db_session, "admin", "admin")
    payload = {"username": "manager", "display_name": "現場管理者", "email": "manager@example.com", "password": "password123", "role": "site_manager"}
    result = api_client.post("/api/access/users", headers=headers, json=payload)
    assert result.status_code == 201
    assert "password" not in result.text
    assert api_client.post("/api/access/users", headers=headers, json=payload).status_code == 409
    assert api_client.post("/api/auth/token", data={"username": "manager", "password": "password123"}).status_code == 200
    log = db_session.query(AuditLog).filter_by(action="USER_CREATED").one()
    assert "password" not in str(log.after_value)


def test_role_change_and_disable_apply_to_existing_token(api_client, db_session):
    admin, headers = login(api_client, db_session, "admin", "admin")
    target, target_headers = login(api_client, db_session, "operator", "ops")
    assert api_client.get("/api/invoices", headers=target_headers).status_code == 200
    url = "/api/access/users/" + target.id
    assert api_client.put(url, headers=headers, json={"role": "site_manager", "is_active": True, "reason": "現場担当へ"}).status_code == 200
    assert api_client.get("/api/invoices", headers=target_headers).status_code == 403
    assert api_client.put(url, headers=headers, json={"role": "site_manager", "is_active": False, "reason": "退職"}).status_code == 200
    assert api_client.get("/api/projects", headers=target_headers).status_code == 403
    assert api_client.post("/api/auth/token", data={"username": "operator", "password": "password123"}).status_code == 401
    assert api_client.put("/api/access/users/" + admin.id, headers=headers, json={"role": "ops", "is_active": True, "reason": "test"}).status_code == 409


def test_admin_configures_role_and_api_enforces_with_same_token(api_client, db_session):
    _, headers = login(api_client, db_session, "admin", "admin")
    _, member = login(api_client, db_session, "manager", "site_manager")
    assert api_client.get("/api/invoices", headers=member).status_code == 403
    result = api_client.put("/api/access/roles/site_manager", headers=headers, json={"permissions": ["project_read", "invoice_read"], "reason": "請求の閲覧を許可"})
    assert result.status_code == 200
    assert api_client.get("/api/invoices", headers=member).status_code == 200
    assert api_client.get("/api/shift-slots", headers=member).status_code == 403
    me = api_client.get("/api/auth/me", headers=member).json()
    assert set(me["permissions"]) == {"project_read", "invoice_read"}
    assert api_client.put("/api/access/roles/admin", headers=headers, json={"permissions": [], "reason": "test"}).status_code == 422
    assert api_client.put("/api/access/roles/ops", headers=headers, json={"permissions": ["unknown"], "reason": "test"}).status_code == 422
    assert db_session.query(AuditLog).filter_by(action="ROLE_PERMISSIONS_CHANGED").count() == 1


def test_site_manager_reads_all_projects_without_worker_link_and_no_money(api_client, db_session, project):
    _, headers = login(api_client, db_session, "manager", "site_manager")
    result = api_client.get("/api/projects", headers=headers)
    assert result.status_code == 200
    assert project.id in [row["id"] for row in result.json()["items"]]
    for path in ["/api/invoices", "/api/payouts", "/api/price-sales", "/api/aggregation/sales?year=2026&month=10", "/api/aggregation/outsource?year=2026&month=10", "/api/ocr/images", "/api/order-requests"]:
        assert api_client.get(path, headers=headers).status_code == 403, path


def test_financial_aggregations_require_login(api_client):
    for path in ["/api/aggregation/sales", "/api/aggregation/outsource"]:
        assert api_client.get(path + "?year=2026&month=10").status_code == 401


def test_role_policy_requires_read_permission_for_writes(api_client, db_session):
    _, headers = login(api_client, db_session, "admin", "admin")
    response = api_client.put("/api/access/roles/ops", headers=headers,
                              json={"permissions": ["invoice_issue"], "reason": "test"})
    assert response.status_code == 422


def test_visible_projects_do_not_expand_csv_submission(api_client, db_session, project):
    from src.services.auth import can_access_project, can_submit_project_csv
    user, _ = login(api_client, db_session, "manager", "site_manager")
    assert can_access_project(db_session, user, project.id)
    assert not can_submit_project_csv(db_session, user, project.id)


def test_assignment_prices_are_redacted_without_price_permission(api_client, db_session, assignment):
    assignment.locked_price_sales = 2345
    assignment.locked_price_outsource = 1234
    db_session.commit()
    _, manager = login(api_client, db_session, "manager", "site_manager")
    result = api_client.get("/api/assignments", headers=manager)
    assert result.status_code == 200
    row = result.json()["items"][0]
    assert row["locked_price_sales"] is None
    assert row["locked_price_outsource"] is None


def test_disabled_account_cannot_refresh_session(api_client, db_session):
    user, _ = login(api_client, db_session, "member", "ops")
    tokens = api_client.post("/api/auth/token", data={"username": "member", "password": "password123"}).json()
    user.is_active = False
    db_session.commit()
    response = api_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_admin_creates_custom_role_assigns_it_and_enforces_permissions(api_client, db_session, project):
    _, admin = login(api_client, db_session, "admin", "admin")
    role_response = api_client.post("/api/access/roles", headers=admin, json={
        "display_name": "案件閲覧担当", "permissions": ["project_read", "dashboard_read"], "reason": "案件の確認を分担"})
    assert role_response.status_code == 201
    role = role_response.json()["role"]
    assert role not in {"admin", "ops", "accounting", "site_manager", "worker"}
    account = api_client.post("/api/access/users", headers=admin, json={
        "username": "custom_member", "display_name": "確認担当", "email": "custom@example.com",
        "password": "password123", "role": role})
    assert account.status_code == 201
    token = api_client.post("/api/auth/token", data={"username": "custom_member", "password": "password123"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    me = api_client.get("/api/auth/me", headers=headers).json()
    assert me["role_name"] == "案件閲覧担当"
    assert me["can_use_admin_console"] is True
    projects = api_client.get("/api/projects", headers=headers)
    assert projects.status_code == 200
    assert project.id in {item["id"] for item in projects.json()["items"]}
    assert api_client.get("/api/dashboard", headers=headers).status_code == 200
    for path in ["/api/invoices", "/api/payouts", "/api/access/users", "/api/access/roles"]:
        assert api_client.get(path, headers=headers).status_code == 403
    assert api_client.post("/api/access/roles", headers=headers, json={"display_name": "無許可", "permissions": [], "reason": "test"}).status_code == 403
    assert db_session.query(AuditLog).filter_by(action="ROLE_CREATED").count() == 1
    changed = api_client.put("/api/access/roles/" + role, headers=admin,
                             json={"permissions": ["invoice_read"], "reason": "請求の確認へ変更"})
    assert changed.status_code == 200
    assert api_client.get("/api/invoices", headers=headers).status_code == 200
    assert api_client.get("/api/projects", headers=headers).status_code == 403


def test_custom_role_can_be_assigned_to_existing_id_and_read_operational_lists(api_client, db_session):
    _, admin = login(api_client, db_session, "admin", "admin")
    target, member = login(api_client, db_session, "member", "ops")
    permissions = ["project_read", "shift_read", "assignment_read", "actual_read", "expense_read"]
    created = api_client.post("/api/access/roles", headers=admin, json={"display_name": "運用閲覧専用", "permissions": permissions, "reason": "閲覧を分担"})
    assert created.status_code == 201
    role = created.json()["role"]
    updated = api_client.put("/api/access/users/" + target.id, headers=admin,
                             json={"role": role, "is_active": True, "reason": "閲覧専用へ変更"})
    assert updated.status_code == 200
    assert updated.json()["role_name"] == "運用閲覧専用"
    for path in ["/api/projects", "/api/shift-slots", "/api/assignments", "/api/actuals", "/api/expenses"]:
        assert api_client.get(path, headers=member).status_code == 200, path
    assert api_client.get("/api/invoices", headers=member).status_code == 403


def test_custom_roles_reject_duplicate_reserved_and_unknown_names(api_client, db_session):
    _, headers = login(api_client, db_session, "admin", "admin")
    body = {"display_name": "閲覧担当", "permissions": [], "reason": "test"}
    assert api_client.post("/api/access/roles", headers=headers, json=body).status_code == 201
    assert api_client.post("/api/access/roles", headers=headers, json=body).status_code == 409
    for name in ["admin", "全体管理者", "worker", "   "]:
        assert api_client.post("/api/access/roles", headers=headers, json={**body, "display_name": name}).status_code == 422
    assert api_client.post("/api/access/users", headers=headers, json={"username": "invalid", "display_name": "Invalid", "email": "invalid@example.com", "password": "password123", "role": "unknown"}).status_code == 422


@pytest.mark.parametrize("role", ["admin", "ops", "accounting", "site_manager", "custom"])
def test_rename_role_preserves_ids_permissions_and_updates_names(api_client, db_session, role):
    from src.services.auth import get_user_permissions
    _, admin = login(api_client, db_session, "administrator", "admin")
    if role == "custom":
        role = api_client.post("/api/access/roles", headers=admin, json={
            "display_name": "旧担当名", "permissions": ["project_read"], "reason": "test"}).json()["role"]
    target, member = login(api_client, db_session, "member", role if role in {"admin", "ops", "accounting", "site_manager"} else "ops")
    target.role = role
    db_session.commit()
    before = api_client.get("/api/auth/me", headers=member).json()
    permissions = get_user_permissions(target, db_session)
    response = api_client.patch("/api/access/roles/" + role + "/name", headers=admin,
                                json={"display_name": " 新しい担当名 "})
    assert response.status_code == 200
    assert response.json() == {"role": role, "display_name": "新しい担当名"}
    after = api_client.get("/api/auth/me", headers=member).json()
    assert after["role_name"] == "新しい担当名"
    assert after["role"] == before["role"]
    assert after["permissions"] == before["permissions"]
    db_session.refresh(target)
    assert get_user_permissions(target, db_session) == permissions
    account = next(u for u in api_client.get("/api/access/users", headers=admin).json()["items"] if u["id"] == target.id)
    assert account["role_name"] == "新しい担当名"
    policy = next(r for r in api_client.get("/api/access/roles", headers=admin).json()["roles"] if r["role"] == role)
    assert policy["display_name"] == "新しい担当名"
    assert policy["editable"] == (role != "admin")
    log = db_session.query(AuditLog).filter_by(action="ROLE_NAME_CHANGED").one()
    assert log.before_value == {"display_name": before["role_name"]}
    assert log.after_value == {"display_name": "新しい担当名"}
    assert log.reason is None


def test_rename_role_preserves_override_and_rejects_bad_names(api_client, db_session):
    from src.models.access_policy import RoleAccessPolicy
    _, admin = login(api_client, db_session, "admin", "admin")
    api_client.put("/api/access/roles/ops", headers=admin, json={"permissions": ["invoice_read"], "reason": "test"})
    url = "/api/access/roles/ops/name"
    body = {"display_name": "会計補助", "reason": "test"}
    assert api_client.patch(url, headers=admin, json=body).status_code == 200
    assert api_client.patch(url, headers=admin, json=body).status_code == 200
    for name in ["", "  ", "admin", "全体管理者", "現場管理者", "x" * 101]:
        assert api_client.patch(url, headers=admin, json={**body, "display_name": name}).status_code == 422
    assert api_client.patch(url, headers=admin, json={**body, "reason": "  "}).status_code == 200
    assert api_client.patch(url, headers=admin, json={**body, "permissions": []}).status_code == 422
    assert api_client.patch("/api/access/roles/accounting/name", headers=admin, json=body).status_code == 409
    assert api_client.patch("/api/access/roles/unknown/name", headers=admin, json=body).status_code == 404
    assert api_client.patch("/api/access/roles/worker/name", headers=admin, json=body).status_code == 404
    assert db_session.get(RoleAccessPolicy, "ops").permissions == ["invoice_read"]
    assert db_session.query(AuditLog).filter_by(action="ROLE_NAME_CHANGED").count() == 1
    assert api_client.post("/api/access/roles", headers=admin, json={**body, "permissions": []}).status_code == 409


@pytest.mark.parametrize("role", ["ops", "accounting", "site_manager", "worker"])
def test_rename_role_requires_admin(api_client, db_session, role):
    _, headers = login(api_client, db_session, "member", role)
    assert api_client.patch("/api/access/roles/ops/name", headers=headers,
                            json={"display_name": "無許可", "reason": "test"}).status_code == 403
