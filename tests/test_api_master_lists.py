"""GET /api/workers, /api/suppliers, /api/clients, /api/sites, /api/project-types, /api/roles のAPIテスト"""
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import Client, ProjectType, Role, Site, Supplier, Worker


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


# ===========================
# /api/workers
# ===========================

def test_list_workers_returns_paginated_items(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers",
        email="ops_workers@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"sort_by": "name", "sort_order": "asc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    ids = [item["id"] for item in payload["items"]]
    assert worker.id in ids


def test_list_workers_filter_by_is_active(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers_active",
        email="ops_workers_active@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    active_worker = Worker(id=generate_ulid(), name="Active Worker", is_active=True)
    inactive_worker = Worker(id=generate_ulid(), name="Inactive Worker", is_active=False)
    db_session.add_all([active_worker, inactive_worker])
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"is_active": "true"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert active_worker.id in item_ids
    assert inactive_worker.id not in item_ids


def test_list_workers_search(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers_search",
        email="ops_workers_search@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    w1 = Worker(id=generate_ulid(), name="Tanaka Taro")
    w2 = Worker(id=generate_ulid(), name="Yamada Hanako")
    db_session.add_all([w1, w2])
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"search": "Tanaka"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert w1.id in item_ids
    assert w2.id not in item_ids


def test_list_workers_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_blocks",
        email="worker_role_blocks@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/workers", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_worker_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_worker",
        email="ops_create_worker@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/workers",
        json={"name": "New Worker", "email": "new-worker@example.com", "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_worker_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_worker",
        email="admin_create_worker@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/workers",
        json={"name": "New Worker", "email": "new-worker@example.com", "phone": "09012345678", "notes": "memo", "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Worker"
    assert payload["email"] == "new-worker@example.com"
    assert payload["notes"] == "memo"


def test_update_worker_succeeds_for_admin(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_update_worker",
        email="admin_update_worker@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "Updated Worker", "email": "updated-worker@example.com", "phone": "08000000000", "introducer_supplier_id": None, "notes": "updated", "is_active": False},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated Worker"
    assert payload["email"] == "updated-worker@example.com"
    assert payload["is_active"] is False


# ===========================
# /api/suppliers
# ===========================

def test_list_suppliers_returns_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_suppliers",
        email="ops_suppliers@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    supplier = Supplier(id=generate_ulid(), name="Test Supplier", payout_terms_days=30, is_active=True)
    db_session.add(supplier)
    db_session.commit()

    response = api_client.get("/api/suppliers", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert supplier.id in item_ids


def test_list_suppliers_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_suppliers",
        email="worker_role_suppliers@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/suppliers", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_supplier_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_supplier",
        email="ops_create_supplier@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/suppliers",
        json={"name": "New Supplier", "payout_terms_days": 30, "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_supplier_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_supplier",
        email="admin_create_supplier@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/suppliers",
        json={"name": "New Supplier", "contact_email": "supplier@example.com", "contact_phone": "0312345678", "payout_terms_days": 30, "default_daily_price": "16500.00", "is_active": True, "notes": "memo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Supplier"
    assert payload["contact_email"] == "supplier@example.com"
    assert payload["default_daily_price"] == "16500.00"


def test_update_supplier_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_update_supplier",
        email="admin_update_supplier@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    supplier = Supplier(id=generate_ulid(), name="Before Supplier", payout_terms_days=70, is_active=True)
    db_session.add(supplier)
    db_session.commit()

    response = api_client.put(
        f"/api/suppliers/{supplier.id}",
        json={"name": "Updated Supplier", "contact_email": "updated-supplier@example.com", "contact_phone": "0399999999", "payout_terms_days": 45, "default_daily_price": "18000.00", "is_active": False, "notes": "updated"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated Supplier"
    assert payload["payout_terms_days"] == 45
    assert payload["is_active"] is False


# ===========================
# /api/clients
# ===========================

def test_list_clients_returns_items(api_client, db_session, client):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_clients",
        email="ops_clients@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/clients", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert client.id in item_ids


def test_list_clients_search(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_clients_search",
        email="ops_clients_search@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    c1 = Client(id=generate_ulid(), name="ABC Company", code="ABC001")
    c2 = Client(id=generate_ulid(), name="XYZ Corp", code="XYZ001")
    db_session.add_all([c1, c2])
    db_session.commit()

    response = api_client.get(
        "/api/clients",
        params={"search": "ABC"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert c1.id in item_ids
    assert c2.id not in item_ids


def test_list_clients_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_clients",
        email="worker_role_clients@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/clients", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_client_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_client",
        email="ops_create_client@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/clients",
        json={"name": "New Client", "code": "NC001", "contact_name": "担当", "contact_email": "new-client@example.com"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_client_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_client",
        email="admin_create_client@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/clients",
        json={"name": "New Client", "code": "NC001", "contact_name": "担当", "contact_email": "new-client@example.com"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Client"
    assert payload["code"] == "NC001"
    assert payload["contact_email"] == "new-client@example.com"


# ===========================
# /api/sites
# ===========================

def test_list_sites_returns_items(api_client, db_session, site):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_sites",
        email="ops_sites@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/sites", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert site.id in item_ids


def test_list_sites_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_sites",
        email="worker_role_sites@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/sites", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_site_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_site",
        email="ops_create_site@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/sites",
        json={"name": "New Site", "code": "NS001", "address": "Tokyo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_site_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_site",
        email="admin_create_site@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/sites",
        json={"name": "New Site", "code": "NS001", "address": "Tokyo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Site"
    assert payload["code"] == "NS001"
    assert payload["address"] == "Tokyo"


# ===========================
# /api/project-types
# ===========================

def test_list_project_types_returns_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_project_types",
        email="ops_project_types@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    pt = ProjectType(id=generate_ulid(), name="General", code="GEN")
    db_session.add(pt)
    db_session.commit()

    response = api_client.get("/api/project-types", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert pt.id in item_ids


def test_list_project_types_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_project_types",
        email="worker_role_project_types@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/project-types", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_project_type_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_project_type",
        email="ops_create_project_type@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/project-types",
        json={"name": "New Type", "code": "NTYPE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_project_type_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_project_type",
        email="admin_create_project_type@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/project-types",
        json={"name": "New Type", "code": "NTYPE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Type"
    assert payload["code"] == "NTYPE"
    assert payload["description"] == "desc"


# ===========================
# /api/roles
# ===========================

def test_list_roles_returns_items(api_client, db_session, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_roles",
        email="ops_roles@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/roles", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert role.id in item_ids


def test_list_roles_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_roles",
        email="worker_role_roles@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/roles", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_role_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_role",
        email="ops_create_role@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/roles",
        json={"name": "New Role", "code": "NROLE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_role_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_role",
        email="admin_create_role@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/roles",
        json={"name": "New Role", "code": "NROLE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Role"
    assert payload["code"] == "NROLE"
    assert payload["description"] == "desc"


# ===========================
# site_manager も MASTER_READ を持つことを確認
# ===========================

def test_master_list_endpoints_accessible_by_site_manager(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="sm_master_access",
        email="sm_master_access@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    for path in ("/api/workers", "/api/suppliers", "/api/clients", "/api/sites", "/api/project-types", "/api/roles"):
        response = api_client.get(path, headers=_auth_header(user.username))
        assert response.status_code == 200, f"{path} returned {response.status_code} for site_manager"
