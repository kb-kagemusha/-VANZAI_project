"""GET /api/actuals のAPIテスト"""
from datetime import date, datetime, time, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import ActualStatus, UserRole
from src.models.transaction import Actual, ImportBatch, Project


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def _create_import_batch(db_session, project_id: str, period_key: str = "202601") -> ImportBatch:
    batch = ImportBatch(
        id=generate_ulid(),
        submitted_by="tester",
        submit_channel="api_test",
        file_name="actuals.csv",
        file_hash="hash-actuals-001",
        project_id=project_id,
        period_key=period_key,
        mode="replace_scope",
        scope_type="project_month",
        status="completed",
        count_success=1,
        count_error=0,
        count_skip=0,
        count_superseded=0,
        has_row_count_warning=False,
        has_total_time_warning=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def _create_actual(
    db_session,
    project,
    worker,
    role,
    import_batch,
    *,
    work_date: date,
    status: str = ActualStatus.ACTIVE.value,
    needs_review: bool = False,
    review_reason: str | None = None,
) -> Actual:
    actual = Actual(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=None,
        import_batch_id=import_batch.id,
        work_date=work_date,
        period_key=work_date.strftime("%Y%m"),
        status=status,
        start_time=time(9, 0),
        end_time=time(18, 0),
        break_minutes_input=60,
        hours_input=Decimal("8.00"),
        calc_minutes_total=540,
        calc_minutes_break=60,
        calc_minutes_billable=480,
        calc_minutes_night=0,
        calc_rounding_unit=15,
        calc_rounding_method="ceil",
        calc_break_rule="auto",
        applied_price_sales=Decimal("2000.00"),
        applied_price_outsource=Decimal("1500.00"),
        external_row_key=f"row-{generate_ulid()}",
        needs_review=needs_review,
        review_reason=review_reason,
    )
    db_session.add(actual)
    db_session.flush()
    return actual


def test_list_actuals_returns_paginated_items(api_client, db_session, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_actuals",
        email="ops_actuals@example.com",
        password="secret123",
        role="ops",
    )
    batch = _create_import_batch(db_session, project.id)
    actual = _create_actual(
        db_session,
        project,
        worker,
        role,
        batch,
        work_date=date(2026, 1, 15),
        needs_review=True,
        review_reason="variance_detected",
    )
    db_session.commit()

    response = api_client.get(
        "/api/actuals",
        params={"period_key": "202601", "needs_review": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["offset"] == 0
    assert payload["limit"] == 50
    assert payload["items"][0]["id"] == actual.id
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["worker_name"] == worker.name
    assert payload["items"][0]["needs_review"] is True
    assert payload["items"][0]["review_reason"] == "variance_detected"
    assert payload["items"][0]["import_batch_file_name"] == "actuals.csv"


def test_list_actuals_restricts_site_manager_scope(api_client, db_session, project, worker, role):
    project.primary_manager_id = worker.id
    db_session.add(project)
    db_session.flush()

    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_actuals",
        email="site_manager_actuals@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = worker.id
    db_session.add(site_manager)

    other_project = Project(
        id=generate_ulid(),
        name="Other Project",
        code="OP001",
        client_id=project.client_id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
        night_calc_mode="store_minutes",
        is_active=True,
    )
    db_session.add(other_project)
    db_session.flush()

    batch = _create_import_batch(db_session, project.id)
    _create_actual(db_session, project, worker, role, batch, work_date=date(2026, 1, 15))
    db_session.commit()

    response = api_client.get(
        "/api/actuals",
        params={"project_id": other_project.id},
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project access denied"