"""GET /api/invoices のAPIテスト"""
from datetime import date, datetime, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import InvoiceStatus, UserRole
from src.models.transaction import Invoice


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_invoices_returns_paginated_items(api_client, db_session, project, client):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_invoices",
        email="ops_invoices@example.com",
        password="secret123",
        role="ops",
    )
    invoice = Invoice(
        id=generate_ulid(),
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 1, 31),
        status=InvoiceStatus.ISSUED.value,
        version=2,
        subtotal=Decimal("10000.00"),
        tax_amount=Decimal("1000.00"),
        total_amount=Decimal("11000.00"),
        pdf_object_key="invoices/202601/test.pdf",
        issued_at=datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(invoice)
    db_session.commit()

    response = api_client.get(
        "/api/invoices",
        params={"period_key": "202601", "client_id": client.id},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == invoice.id
    assert payload["items"][0]["client_name"] == client.name
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["version"] == 2
    assert payload["items"][0]["status"] == InvoiceStatus.ISSUED.value
    assert payload["items"][0]["has_pdf"] is True


def test_list_invoices_blocks_site_manager(api_client, db_session):
    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_invoices",
        email="site_manager_invoices@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/invoices",
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
