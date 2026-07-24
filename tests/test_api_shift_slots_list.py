"""GET /api/shift-slots のAPIテスト"""
from datetime import date, time

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import AssignmentStatus, UserRole
from src.models.master import Worker
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


def test_create_shift_slot_requires_shift_write(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_create_shift_slot",
        email="accounting_create_shift_slot@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/shift-slots",
        json={"project_id": project.id, "work_date": "2026-02-15", "required_count": 2},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_shift_slot_succeeds_for_ops(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_shift_slot",
        email="ops_create_shift_slot@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/shift-slots",
        json={
            "project_id": project.id,
            "work_date": "2026-02-15",
            "start_time": "09:00",
            "end_time": "18:00",
            "shift_label": "日勤",
            "required_count": 2,
            "notes": "Created from API test",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project.id
    assert payload["project_name"] == project.name
    assert payload["required_count"] == 2
    assert payload["assigned_count"] == 0
    assert payload["notes"] == "Created from API test"


def test_update_shift_slot_notes_succeeds_for_ops(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_shift_slot_notes",
        email="ops_update_shift_slot_notes@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 2, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=2,
        notes="before",
    )
    db_session.add(shift_slot)
    db_session.commit()

    response = api_client.patch(
        f"/api/shift-slots/{shift_slot.id}/notes",
        json={"notes": "updated notes"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == shift_slot.id
    assert payload["notes"] == "updated notes"


def test_update_shift_slot_succeeds_for_ops(api_client, db_session, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_shift_slot",
        email="ops_update_shift_slot@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 2, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=2,
        notes="before",
    )
    db_session.add(shift_slot)
    db_session.commit()

    response = api_client.put(
        f"/api/shift-slots/{shift_slot.id}",
        json={
            "project_id": project.id,
            "work_date": "2026-02-16",
            "start_time": "10:00",
            "end_time": "19:00",
            "shift_label": "遅番",
            "required_count": 3,
            "notes": "updated notes",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == shift_slot.id
    assert payload["work_date"] == "2026-02-16"
    assert payload["start_time"] == "10:00:00"
    assert payload["end_time"] == "19:00:00"
    assert payload["shift_label"] == "遅番"
    assert payload["required_count"] == 3
    assert payload["notes"] == "updated notes"


def test_update_shift_slot_rejects_required_count_below_assigned(api_client, db_session, client, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_shift_slot_guard",
        email="ops_update_shift_slot_guard@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    project = Project(
        id=generate_ulid(),
        name="Shift Slot Guard Project",
        code="SSG001",
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
        work_date=date(2026, 2, 20),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=2,
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
    other_worker = Worker(id=generate_ulid(), name="Guard Worker", email="guard-worker@example.com")
    second_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=shift_slot.id,
        worker_id=other_worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
    )
    db_session.add_all([assignment, other_worker, second_assignment])
    db_session.commit()

    response = api_client.put(
        f"/api/shift-slots/{shift_slot.id}",
        json={
            "project_id": project.id,
            "work_date": "2026-02-20",
            "start_time": "09:00",
            "end_time": "18:00",
            "shift_label": "日勤",
            "required_count": 1,
            "notes": "updated notes",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "必要人数を確定人数未満にはできません"
