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
