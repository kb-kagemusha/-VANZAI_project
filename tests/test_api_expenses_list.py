"""GET /api/expenses のAPIテスト"""
from datetime import date, datetime, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import ExpenseStatus, UserRole
from src.models.transaction import Expense


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_expenses_returns_paginated_items(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_expenses",
        email="ops_expenses@example.com",
        password="secret123",
        role="ops",
    )
    expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2026, 1, 20),
        category="transport",
        amount=Decimal("1200.00"),
        description="Train fare",
        receipt_file_key="receipts/202601/receipt.jpg",
        status=ExpenseStatus.APPROVED.value,
        approved_by="accounting_user",
        approved_at=datetime(2026, 1, 21, 9, 0, tzinfo=timezone.utc),
        target_invoice=True,
        target_payout=False,
    )
    db_session.add(expense)
    db_session.commit()

    response = api_client.get(
        "/api/expenses",
        params={"project_id": project.id, "status": ExpenseStatus.APPROVED.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == expense.id
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["worker_name"] == worker.name
    assert payload["items"][0]["has_receipt"] is True
    assert payload["items"][0]["status"] == ExpenseStatus.APPROVED.value


def test_list_expenses_blocks_site_manager(api_client, db_session):
    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_expenses",
        email="site_manager_expenses@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/expenses",
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
