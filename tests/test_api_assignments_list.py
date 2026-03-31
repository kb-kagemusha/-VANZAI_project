"""GET /api/assignments のAPIテスト"""
from datetime import date, time
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import AssignmentStatus, UserRole
from src.models.transaction import Project, ShiftSlot, Assignment


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_assignments_returns_paginated_items(api_client, db_session, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignments",
        email="ops_assignments@example.com",
        password="secret123",
        role="ops",
    )
    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=generate_ulid(),
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        cancel_reason=None,
        locked_price_sales=Decimal("2000.00"),
        locked_price_outsource=Decimal("1500.00"),
    )
    shift_slot = ShiftSlot(
        id=assignment.shift_slot_id,
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=1,
    )
    db_session.add(shift_slot)
    db_session.add(assignment)
    db_session.commit()

    response = api_client.get(
        "/api/assignments",
        params={"project_id": project.id, "status": AssignmentStatus.CONFIRMED.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == assignment.id
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["worker_name"] == worker.name
    assert payload["items"][0]["shift_label"] == "日勤"
    assert payload["items"][0]["status"] == AssignmentStatus.CONFIRMED.value


def test_list_assignments_restricts_site_manager_scope(api_client, db_session, project, worker, role):
    project.primary_manager_id = worker.id
    db_session.add(project)
    db_session.flush()

    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_assignments",
        email="site_manager_assignments@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = worker.id
    db_session.add(site_manager)

    other_project = Project(
        id=generate_ulid(),
        name="Other Assignment Project",
        code="OAP001",
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
    db_session.commit()

    response = api_client.get(
        "/api/assignments",
        params={"project_id": other_project.id},
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project access denied"