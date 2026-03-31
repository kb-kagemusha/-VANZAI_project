"""POST /api/audit/search のAPIテスト"""
from datetime import date, datetime, timezone

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.enums import AuditAction, UserRole
from src.services.audit import AuditService


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_search_audit_logs_returns_paginated_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_audit",
        email="ops_audit@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    audit_service = AuditService(db_session)

    first = audit_service.log(
        AuditAction.IMPORT_BATCH_CREATED,
        target_type="import_batch",
        target_id="batch-1",
        actor="ops_audit",
        actor_role=UserRole.OPS.value,
        extra_metadata={"period_key": "202601", "file_name": "actuals.csv", "count": 10},
    )
    first.created_at = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

    second = audit_service.log(
        AuditAction.CLOSING_HARD_CLOSED,
        target_type="closing",
        target_id="closing-202601",
        actor="admin",
        actor_role=UserRole.ADMIN.value,
        reason="monthly close approved",
        extra_metadata={"period_key": "202601", "project_id": "proj-1"},
    )
    second.created_at = datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc)

    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["offset"] == 0
    assert payload["limit"] == 10
    assert len(payload["items"]) == 2
    assert payload["items"][0]["id"] == second.id
    assert payload["items"][0]["action"] == AuditAction.CLOSING_HARD_CLOSED.value
    assert payload["items"][0]["project_id"] == "proj-1"
    assert payload["items"][0]["reason"] == "monthly close approved"
    assert payload["items"][0]["details_summary"] == "monthly close approved"
    assert payload["items"][1]["id"] == first.id
    assert payload["items"][1]["project_id"] is None
    assert payload["items"][1]["details"]["file_name"] == "actuals.csv"
    assert payload["items"][1]["details_summary"] == "period_key=202601, file_name=actuals.csv, count=10"


def test_search_audit_logs_filters_by_actor_action_and_date(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_audit",
        email="accounting_audit@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    audit_service = AuditService(db_session)

    matched = audit_service.log(
        AuditAction.IMPORT_BATCH_COMPLETED,
        target_type="import_batch",
        target_id="batch-match",
        actor="ops_user",
        extra_metadata={"period_key": "202602"},
    )
    matched.created_at = datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc)

    non_matching_action = audit_service.log(
        AuditAction.CLOSING_SOFT_CLOSED,
        target_type="closing",
        target_id="closing-x",
        actor="ops_user",
        extra_metadata={"period_key": "202602"},
    )
    non_matching_action.created_at = datetime(2026, 2, 10, 11, 0, tzinfo=timezone.utc)

    non_matching_actor = audit_service.log(
        AuditAction.IMPORT_BATCH_COMPLETED,
        target_type="import_batch",
        target_id="batch-other",
        actor="other_user",
        extra_metadata={"period_key": "202602"},
    )
    non_matching_actor.created_at = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={
            "action_type": AuditAction.IMPORT_BATCH_COMPLETED.value,
            "actor": "ops_user",
            "date_from": date(2026, 2, 1).isoformat(),
            "date_to": date(2026, 2, 28).isoformat(),
            "limit": 5,
            "offset": 0,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == matched.id


def test_search_audit_logs_blocks_site_manager(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_audit",
        email="site_manager_audit@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={"limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_search_audit_logs_surfaces_release_reason_and_deadline(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_audit_release",
        email="admin_audit_release@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    audit_service = AuditService(db_session)

    released = audit_service.log(
        AuditAction.CLOSING_SOFT_RELEASED,
        target_type="closing",
        target_id="closing-release-1",
        actor="admin_audit_release",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={
            "project_id": "proj-1",
            "period_key": "202601",
            "approver_id": "admin2",
            "reason": "CSV再取込",
            "reclose_deadline": "2026-02-07T00:00:00+00:00",
            "release_count": 1,
        },
    )
    released.created_at = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item = next(entry for entry in payload["items"] if entry["id"] == released.id)
    assert item["details"]["approver_id"] == "admin2"
    assert item["details"]["reclose_deadline"] == "2026-02-07T00:00:00+00:00"
    assert item["details_summary"] == "reason=CSV再取込, approver_id=admin2, reclose_deadline=2026-02-07T00:00:00+00:00"


def test_search_audit_logs_filters_by_action_group(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_audit_group",
        email="admin_audit_group@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    audit_service = AuditService(db_session)

    executed = audit_service.log(
        AuditAction.CLOSING_SOFT_CLOSED,
        target_type="closing",
        target_id="closing-execute-1",
        actor="admin_audit_group",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    executed.created_at = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)

    released = audit_service.log(
        AuditAction.CLOSING_SOFT_RELEASED,
        target_type="closing",
        target_id="closing-release-2",
        actor="admin_audit_group",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601", "reason": "再取込"},
    )
    released.created_at = datetime(2026, 1, 11, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "closing_release", "target_type": "closing", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == released.id
    assert payload["items"][0]["action"] == AuditAction.CLOSING_SOFT_RELEASED.value


def test_search_audit_logs_filters_by_billing_action_groups(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_audit_billing_groups",
        email="admin_audit_billing_groups@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    audit_service = AuditService(db_session)

    invoice_log = audit_service.log(
        AuditAction.INVOICE_ISSUED,
        target_type="invoices",
        target_id="invoice-1",
        actor="admin_audit_billing_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    invoice_log.created_at = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)

    payout_log = audit_service.log(
        AuditAction.PAYOUT_APPROVED,
        target_type="payouts",
        target_id="payout-1",
        actor="admin_audit_billing_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    payout_log.created_at = datetime(2026, 1, 21, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    invoice_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "invoice_all", "target_type": "invoice", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert invoice_response.status_code == 200
    invoice_payload = invoice_response.json()
    assert invoice_payload["total"] == 1
    assert invoice_payload["items"][0]["id"] == invoice_log.id
    assert invoice_payload["items"][0]["action"] == AuditAction.INVOICE_ISSUED.value

    payout_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "payout_all", "target_type": "payout", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert payout_response.status_code == 200
    payout_payload = payout_response.json()
    assert payout_payload["total"] == 1
    assert payout_payload["items"][0]["id"] == payout_log.id
    assert payout_payload["items"][0]["action"] == AuditAction.PAYOUT_APPROVED.value


def test_search_audit_logs_filters_by_operations_action_groups(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_audit_ops_groups",
        email="admin_audit_ops_groups@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    audit_service = AuditService(db_session)

    import_log = audit_service.log(
        AuditAction.IMPORT_BATCH_COMPLETED,
        target_type="import_batch",
        target_id="batch-1",
        actor="admin_audit_ops_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    import_log.created_at = datetime(2026, 1, 22, 12, 0, tzinfo=timezone.utc)

    actual_log = audit_service.log(
        AuditAction.ACTUAL_INVALIDATED,
        target_type="actuals",
        target_id="actual-1",
        actor="admin_audit_ops_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    actual_log.created_at = datetime(2026, 1, 23, 12, 0, tzinfo=timezone.utc)

    assignment_log = audit_service.log(
        AuditAction.ASSIGNMENT_STATUS_CHANGED,
        target_type="assignments",
        target_id="assignment-1",
        actor="admin_audit_ops_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    assignment_log.created_at = datetime(2026, 1, 24, 12, 0, tzinfo=timezone.utc)

    price_log = audit_service.log(
        AuditAction.PRICE_RULE_CHANGED,
        target_type="price_rules",
        target_id="price-rule-1",
        actor="admin_audit_ops_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601"},
    )
    price_log.created_at = datetime(2026, 1, 25, 12, 0, tzinfo=timezone.utc)

    price_resolved_log = audit_service.log(
        AuditAction.PRICE_RESOLVED,
        target_type="price_sales",
        target_id="price-sales-1",
        actor="admin_audit_ops_groups",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601", "method": "project_price"},
    )
    price_resolved_log.created_at = datetime(2026, 1, 26, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    import_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "import_all", "target_type": "import_batch", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["total"] == 1
    assert import_payload["items"][0]["id"] == import_log.id
    assert import_payload["items"][0]["action"] == AuditAction.IMPORT_BATCH_COMPLETED.value

    actual_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "actual_all", "target_type": "actual", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert actual_response.status_code == 200
    actual_payload = actual_response.json()
    assert actual_payload["total"] == 1
    assert actual_payload["items"][0]["id"] == actual_log.id
    assert actual_payload["items"][0]["action"] == AuditAction.ACTUAL_INVALIDATED.value

    assignment_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "assignment_all", "target_type": "assignment", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert assignment_response.status_code == 200
    assignment_payload = assignment_response.json()
    assert assignment_payload["total"] == 1
    assert assignment_payload["items"][0]["id"] == assignment_log.id
    assert assignment_payload["items"][0]["action"] == AuditAction.ASSIGNMENT_STATUS_CHANGED.value

    price_response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "action_group": "price_all", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert price_response.status_code == 200
    price_payload = price_response.json()
    assert price_payload["total"] == 2
    assert {item["id"] for item in price_payload["items"]} == {price_log.id, price_resolved_log.id}
    assert {item["action"] for item in price_payload["items"]} == {
        AuditAction.PRICE_RULE_CHANGED.value,
        AuditAction.PRICE_RESOLVED.value,
    }


def test_search_audit_logs_filters_by_project_id(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_audit_project",
        email="admin_audit_project@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    audit_service = AuditService(db_session)

    matched = audit_service.log(
        AuditAction.CLOSING_HARD_CLOSED,
        target_type="closing",
        target_id="closing-project-match",
        actor="admin_audit_project",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601", "project_id": "proj-match"},
    )
    matched.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

    target_project = audit_service.log(
        AuditAction.ASSIGNMENT_STATUS_CHANGED,
        target_type="project",
        target_id="proj-match",
        actor="admin_audit_project",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601", "status": "active"},
    )
    target_project.created_at = datetime(2026, 1, 15, 13, 0, tzinfo=timezone.utc)

    other = audit_service.log(
        AuditAction.CLOSING_HARD_CLOSED,
        target_type="closing",
        target_id="closing-project-other",
        actor="admin_audit_project",
        actor_role=UserRole.ADMIN.value,
        extra_metadata={"period_key": "202601", "project_id": "proj-other"},
    )
    other.created_at = datetime(2026, 1, 16, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    response = api_client.post(
        "/api/audit/search",
        json={"period_key": "202601", "project_id": "proj-match", "limit": 10, "offset": 0},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["items"][0]["id"] == target_project.id
    assert payload["items"][0]["project_id"] == "proj-match"
    assert payload["items"][1]["id"] == matched.id
    assert payload["items"][1]["project_id"] == "proj-match"