"""GET /api/payouts のAPIテスト"""
from datetime import date, datetime, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import PayoutStatus, UserRole
from src.models.master import Supplier
from src.models.transaction import Payout


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_payouts_returns_paginated_items_for_supplier(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_payouts",
        email="ops_payouts@example.com",
        password="secret123",
        role="ops",
    )
    supplier = Supplier(
        id=generate_ulid(),
        name="Test Supplier",
        contact_email="supplier@example.com",
        payout_terms_days=70,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()

    payout = Payout(
        id=generate_ulid(),
        supplier_id=supplier.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=3,
        total_amount=Decimal("8000.00"),
        approved_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
        paid_at=None,
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.get(
        "/api/payouts",
        params={"period_key": "202601", "supplier_id": supplier.id},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == payout.id
    assert payload["items"][0]["payee_name"] == supplier.name
    assert payload["items"][0]["payee_type"] == "supplier"
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["version"] == 3
    assert payload["items"][0]["status"] == PayoutStatus.APPROVED.value


def test_list_payouts_blocks_site_manager(api_client, db_session):
    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_payouts",
        email="site_manager_payouts@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/payouts",
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
