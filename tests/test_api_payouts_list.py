"""GET /api/payouts のAPIテスト"""
from datetime import date, datetime, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import PayoutStatus, UserRole
from src.models.master import Supplier
from src.models.transaction import Payout, PayoutDelivery


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
        pdf_object_key="payouts/202601/test.pdf",
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
    assert payload["items"][0]["has_pdf"] is True
    assert payload["items"][0]["pdf_storage_key"] == "payouts/202601/test.pdf"
    assert payload["items"][0]["default_recipient_email"] == "supplier@example.com"


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


def test_list_payouts_includes_latest_delivery_metadata(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_payouts_delivery_meta",
        email="ops_payouts_delivery_meta@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )

    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("8000.00"),
        approved_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add(payout)
    db_session.flush()

    older = PayoutDelivery(
        id=generate_ulid(),
        payout_id=payout.id,
        recipient_email="older@example.com",
        status="sent",
        provider="gmail",
        delivered_by=user.username,
        sent_at=datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc),
    )
    latest = PayoutDelivery(
        id=generate_ulid(),
        payout_id=payout.id,
        recipient_email="latest@example.com",
        status="failed",
        provider="gmail",
        delivered_by=user.username,
        error_message="email send failed",
        sent_at=datetime(2026, 2, 11, 9, 30, tzinfo=timezone.utc),
    )
    db_session.add_all([older, latest])
    db_session.commit()

    response = api_client.get(
        "/api/payouts",
        params={"period_key": "202601", "worker_id": worker.id},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["last_delivery_status"] == "failed"
    assert payload["items"][0]["last_delivery_recipient"] == "latest@example.com"
    assert payload["items"][0]["last_delivered_at"].startswith("2026-02-11T09:30:00")
    assert payload["items"][0]["default_recipient_email"] == worker.email


def test_list_payouts_can_filter_missing_default_recipient(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_payouts_missing_recipient",
        email="ops_payouts_missing_recipient@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    supplier_with_email = Supplier(
        id=generate_ulid(),
        name="Supplier With Email",
        contact_email="available@example.com",
        payout_terms_days=30,
        is_active=True,
    )
    supplier_without_email = Supplier(
        id=generate_ulid(),
        name="Supplier Without Email",
        contact_email=None,
        payout_terms_days=30,
        is_active=True,
    )
    db_session.add_all([supplier_with_email, supplier_without_email])
    db_session.flush()

    payout_with_email = Payout(
        id=generate_ulid(),
        supplier_id=supplier_with_email.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("5000.00"),
        approved_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
    )
    payout_without_email = Payout(
        id=generate_ulid(),
        supplier_id=supplier_without_email.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("7000.00"),
        approved_at=datetime(2026, 2, 11, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([payout_with_email, payout_without_email])
    db_session.commit()

    response = api_client.get(
        "/api/payouts",
        params={"period_key": "202601", "missing_default_recipient_only": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == payout_without_email.id
    assert payload["items"][0]["default_recipient_email"] is None


def test_list_payouts_can_filter_by_delivery_state(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_payouts_delivery_state",
        email="ops_payouts_delivery_state@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )

    unsent_payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("4000.00"),
        approved_at=datetime(2026, 2, 9, 10, 0, tzinfo=timezone.utc),
    )
    failed_latest_payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("5000.00"),
        approved_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
    )
    recovered_payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 2, 28),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("6000.00"),
        approved_at=datetime(2026, 2, 11, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([unsent_payout, failed_latest_payout, recovered_payout])
    db_session.flush()

    db_session.add_all([
        PayoutDelivery(
            id=generate_ulid(),
            payout_id=failed_latest_payout.id,
            recipient_email="failed@example.com",
            status="failed",
            provider="smtp",
            delivered_by=user.username,
            error_message="send failed",
            sent_at=datetime(2026, 2, 12, 9, 0, tzinfo=timezone.utc),
        ),
        PayoutDelivery(
            id=generate_ulid(),
            payout_id=recovered_payout.id,
            recipient_email="failed-first@example.com",
            status="failed",
            provider="smtp",
            delivered_by=user.username,
            error_message="send failed",
            sent_at=datetime(2026, 2, 12, 9, 0, tzinfo=timezone.utc),
        ),
        PayoutDelivery(
            id=generate_ulid(),
            payout_id=recovered_payout.id,
            recipient_email="sent-latest@example.com",
            status="sent",
            provider="smtp",
            delivered_by=user.username,
            sent_at=datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc),
        ),
    ])
    db_session.commit()

    unsent_response = api_client.get(
        "/api/payouts",
        params={"period_key": "202601", "delivery_state": "unsent"},
        headers=_auth_header(user.username),
    )
    assert unsent_response.status_code == 200
    unsent_payload = unsent_response.json()
    assert unsent_payload["total"] == 1
    assert unsent_payload["items"][0]["id"] == unsent_payout.id

    failed_response = api_client.get(
        "/api/payouts",
        params={"period_key": "202601", "delivery_state": "failed"},
        headers=_auth_header(user.username),
    )
    assert failed_response.status_code == 200
    failed_payload = failed_response.json()
    assert failed_payload["total"] == 1
    assert failed_payload["items"][0]["id"] == failed_latest_payout.id
