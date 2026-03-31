"""GET /api/shift-slots のAPIテスト"""
from datetime import date, time

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import AssignmentStatus, UserRole
from src.models.transaction import Assignment, Project, ShiftSlot


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_shift_slots_returns_assigned_count(api_client, db_session, client, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_shift_slots",
        email="ops_shift_slots@example.com",
        password="secret123",
        role="ops",
    )
    project = Project(
        id=generate_ulid(),
        name="Shift Slot Project",
        code="SSP001",
        client_id=client.id,
        is_active=True,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    db_session.add(project)
    db_session.flush()

    shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=3,
    )
    db_session.add(shift_slot)
    db_session.flush()

    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
    )
    db_session.add(assignment)
    db_session.commit()

    response = api_client.get(
        "/api/shift-slots",
        params={"project_id": project.id},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == shift_slot.id
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["assigned_count"] == 1
    assert payload["items"][0]["required_count"] == 3


def test_list_shift_slots_blocks_other_project_for_site_manager(api_client, db_session, client, worker):
    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_shift_slots",
        email="site_manager_shift_slots@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = worker.id
    db_session.add(site_manager)

    project_allowed = Project(
        id=generate_ulid(),
        name="Allowed Shift Project",
        code="ASP001",
        client_id=client.id,
        primary_manager_id=worker.id,
        is_active=True,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    project_hidden = Project(
        id=generate_ulid(),
        name="Hidden Shift Project",
        code="HSP001",
        client_id=client.id,
        is_active=True,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    db_session.add_all([project_allowed, project_hidden])
    db_session.commit()

    response = api_client.get(
        "/api/shift-slots",
        params={"project_id": project_hidden.id},
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project access denied"
