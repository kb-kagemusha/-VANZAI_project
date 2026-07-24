"""GET /api/price-sales と /api/price-outsource のAPIテスト"""
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import PriceOutsource, PriceSales


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_price_sales_returns_paginated_items(api_client, db_session, project, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_price_sales",
        email="ops_price_sales@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    matched = PriceSales(
        id=generate_ulid(),
        project_id=project.id,
        role_id=role.id,
        client_id=project.client_id,
        unit_price=15000,
        unit_type="hourly",
        is_default=False,
    )
    other = PriceSales(
        id=generate_ulid(),
        unit_price=12000,
        unit_type="hourly",
        is_default=True,
    )
    db_session.add_all([matched, other])
    db_session.commit()

    response = api_client.get(
        "/api/price-sales",
        params={"project_id": project.id, "sort_by": "unit_price", "sort_order": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == matched.id
    assert payload["items"][0]["project_id"] == project.id
    assert payload["items"][0]["role_id"] == role.id


def test_list_price_outsource_returns_paginated_items(api_client, db_session, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_price_outsource",
        email="ops_price_outsource@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    matched = PriceOutsource(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        unit_price=9000,
        unit_type="hourly",
        is_default=False,
    )
    other = PriceOutsource(
        id=generate_ulid(),
        unit_price=7000,
        unit_type="hourly",
        is_default=True,
    )
    db_session.add_all([matched, other])
    db_session.commit()

    response = api_client.get(
        "/api/price-outsource",
        params={"worker_id": worker.id, "sort_by": "unit_price", "sort_order": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == matched.id
    assert payload["items"][0]["worker_id"] == worker.id
    assert payload["items"][0]["role_id"] == role.id


def test_list_price_master_endpoints_block_site_manager(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_price_masters",
        email="site_manager_price_masters@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    for path in ("/api/price-sales", "/api/price-outsource"):
        response = api_client.get(path, headers=_auth_header(user.username))
        assert response.status_code == 403


def test_create_price_sales_requires_price_write(api_client, db_session, project, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_price_sales",
        email="ops_create_price_sales@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/price-sales",
        json={"project_id": project.id, "role_id": role.id, "client_id": project.client_id, "unit_price": "15000.00", "unit_type": "hourly", "is_default": False, "notes": "memo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_and_update_price_sales_succeeds_for_admin(api_client, db_session, project, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_price_sales",
        email="admin_create_price_sales@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    create_response = api_client.post(
        "/api/price-sales",
        json={"project_id": project.id, "role_id": role.id, "client_id": project.client_id, "unit_price": "15000.00", "unit_type": "hourly", "is_default": False, "notes": "memo"},
        headers=_auth_header(user.username),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["unit_price"] == "15000.00"

    update_response = api_client.put(
        f"/api/price-sales/{created['id']}",
        json={"project_id": project.id, "role_id": role.id, "client_id": project.client_id, "unit_price": "15500.00", "unit_type": "daily", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "is_default": True, "notes": "updated"},
        headers=_auth_header(user.username),
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["unit_price"] == "15500.00"
    assert updated["unit_type"] == "daily"
    assert updated["is_default"] is True


def test_create_and_update_price_outsource_succeeds_for_admin(api_client, db_session, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_price_outsource",
        email="admin_create_price_outsource@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    create_response = api_client.post(
        "/api/price-outsource",
        json={"project_id": project.id, "worker_id": worker.id, "role_id": role.id, "unit_price": "9000.00", "unit_type": "hourly", "is_default": False, "notes": "memo"},
        headers=_auth_header(user.username),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["unit_price"] == "9000.00"

    update_response = api_client.put(
        f"/api/price-outsource/{created['id']}",
        json={"project_id": project.id, "worker_id": worker.id, "role_id": role.id, "unit_price": "9500.00", "unit_type": "daily", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "is_default": True, "notes": "updated"},
        headers=_auth_header(user.username),
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["unit_price"] == "9500.00"
    assert updated["unit_type"] == "daily"
    assert updated["is_default"] is True