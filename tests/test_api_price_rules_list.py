"""GET /api/price-rules のAPIテスト"""
from datetime import date

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import PriceRule


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_price_rules_returns_paginated_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_price_rules",
        email="ops_price_rules@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    first = PriceRule(
        id=generate_ulid(),
        name="深夜優先ルール",
        priority=10,
        conditions={"time_range": "night"},
        sales_price=15000,
        outsource_price=10000,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        is_active=True,
    )
    second = PriceRule(
        id=generate_ulid(),
        name="通常ルール",
        priority=20,
        conditions={"default": True},
        sales_price=12000,
        outsource_price=8000,
        is_active=False,
    )
    db_session.add_all([first, second])
    db_session.commit()

    response = api_client.get(
        "/api/price-rules",
        params={"search": "ルール", "sort_by": "priority", "sort_order": "asc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["items"][0]["id"] == first.id
    assert payload["items"][0]["name"] == first.name
    assert payload["items"][0]["priority"] == 10
    assert payload["items"][1]["id"] == second.id
    assert payload["items"][1]["is_active"] is False


def test_list_price_rules_blocks_site_manager(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_price_rules",
        email="site_manager_price_rules@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/price-rules",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403