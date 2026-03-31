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