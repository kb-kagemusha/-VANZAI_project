"""GET /api/expenses のAPIテスト"""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import ExpenseStatus, UserRole
from src.models.master import Worker
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


def test_list_expenses_scopes_worker_to_own_records(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_expenses",
        email="worker_expenses@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)

    other_worker = Worker(
        id=generate_ulid(),
        name="Other Expense Worker",
        email="other_expense_worker@example.com",
    )
    db_session.add(other_worker)
    db_session.flush()

    own_expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2026, 1, 20),
        category="transport",
        amount=Decimal("1200.00"),
        status=ExpenseStatus.PENDING.value,
        target_invoice=False,
        target_payout=True,
    )
    other_expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=other_worker.id,
        expense_date=date(2026, 1, 21),
        category="meal",
        amount=Decimal("800.00"),
        status=ExpenseStatus.PENDING.value,
        target_invoice=False,
        target_payout=True,
    )
    db_session.add_all([own_expense, other_expense])
    db_session.commit()

    response = api_client.get("/api/expenses", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == own_expense.id


def test_worker_can_submit_expense_with_receipt(api_client, db_session, assignment, project, worker, monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPT_STORAGE_ROOT", str(tmp_path))

    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_expense_submit",
        email="worker_expense_submit@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    response = api_client.post(
        "/api/expenses",
        data={
            "project_id": project.id,
            "expense_date": "2026-01-15",
            "category": "transport",
            "amount": "1250.00",
            "description": "電車移動",
        },
        files={"receipt": ("receipt.png", b"fake-image-bytes", "image/png")},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project.id
    assert payload["worker_id"] == worker.id
    assert payload["status"] == ExpenseStatus.PENDING.value
    assert payload["has_receipt"] is True

    expense = db_session.get(Expense, payload["id"])
    assert expense is not None
    assert expense.receipt_file_key is not None
    assert Path(tmp_path, *expense.receipt_file_key.split("/")).exists()


def test_accounting_can_approve_expense(api_client, db_session, project, worker):
    expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2026, 1, 20),
        category="transport",
        amount=Decimal("2000.00"),
        status=ExpenseStatus.PENDING.value,
        target_invoice=False,
        target_payout=True,
    )
    db_session.add(expense)
    accounting_user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_expense_approve",
        email="accounting_expense_approve@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        f"/api/expenses/{expense.id}/approve",
        headers=_auth_header(accounting_user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ExpenseStatus.APPROVED.value
    assert payload["approved_by"] == accounting_user.username
    assert payload["reject_reason"] is None


def test_accounting_can_reject_expense(api_client, db_session, project, worker):
    expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2026, 1, 20),
        category="meal",
        amount=Decimal("5000.00"),
        status=ExpenseStatus.PENDING.value,
        target_invoice=False,
        target_payout=True,
    )
    db_session.add(expense)
    accounting_user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_expense_reject",
        email="accounting_expense_reject@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        f"/api/expenses/{expense.id}/reject",
        json={"reject_reason": "領収書不足"},
        headers=_auth_header(accounting_user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ExpenseStatus.REJECTED.value
    assert payload["approved_by"] == accounting_user.username
    assert payload["reject_reason"] == "領収書不足"


def test_worker_can_download_own_receipt(api_client, db_session, project, worker, monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPT_STORAGE_ROOT", str(tmp_path))
    receipt_key = "receipts/202601/expense_download.png"
    receipt_path = Path(tmp_path, *receipt_key.split("/"))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(b"receipt-bytes")

    expense = Expense(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        expense_date=date(2026, 1, 20),
        category="transport",
        amount=Decimal("1000.00"),
        status=ExpenseStatus.PENDING.value,
        receipt_file_key=receipt_key,
        target_invoice=False,
        target_payout=True,
    )
    db_session.add(expense)
    worker_user = create_user_with_hashed_password(
        db=db_session,
        username="worker_receipt_download",
        email="worker_receipt_download@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    worker_user.worker_id = worker.id
    db_session.add(worker_user)
    db_session.commit()

    response = api_client.get(
        f"/api/expenses/{expense.id}/receipt",
        headers=_auth_header(worker_user.username),
    )

    assert response.status_code == 200
    assert response.content == b"receipt-bytes"
    assert "attachment;" in response.headers["content-disposition"].lower()
