"""GET /api/dashboard のAPIテスト"""
from datetime import date, time

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import AssignmentStatus, UserRole
from src.models.master import Client, Role, Site, Worker
from src.models.transaction import Assignment, Project, ShiftSlot


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_requires_authentication(api_client):
    response = api_client.get("/api/dashboard")

    assert response.status_code == 401


def test_dashboard_scopes_site_manager_projects(api_client, db_session):
    client = Client(id=generate_ulid(), name="Client A", code="CA001")
    site = Site(id=generate_ulid(), name="Site A", code="SA001")
    role = Role(id=generate_ulid(), name="Guard", code="GUARD")
    manager_worker = Worker(id=generate_ulid(), name="Manager", email="manager@example.com")
    assigned_worker = Worker(id=generate_ulid(), name="Assigned Worker", email="assigned@example.com")
    other_worker = Worker(id=generate_ulid(), name="Other Worker", email="other@example.com")
    db_session.add_all([client, site, role, manager_worker, assigned_worker, other_worker])
    db_session.flush()

    managed_project = Project(
        id=generate_ulid(),
        name="Managed Project",
        code="MP001",
        client_id=client.id,
        site_id=site.id,
        primary_manager_id=manager_worker.id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
    )
    other_project = Project(
        id=generate_ulid(),
        name="Other Project",
        code="OP001",
        client_id=client.id,
        site_id=site.id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
    )
    db_session.add_all([managed_project, other_project])
    db_session.flush()

    managed_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=managed_project.id,
        work_date=date(2026, 3, 10),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
    )
    other_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=other_project.id,
        work_date=date(2026, 3, 11),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
    )
    db_session.add_all([managed_slot, other_slot])
    db_session.flush()

    db_session.add_all(
        [
            Assignment(
                id=generate_ulid(),
                shift_slot_id=managed_slot.id,
                worker_id=assigned_worker.id,
                role_id=role.id,
                status=AssignmentStatus.CONFIRMED.value,
            ),
            Assignment(
                id=generate_ulid(),
                shift_slot_id=other_slot.id,
                worker_id=other_worker.id,
                role_id=role.id,
                status=AssignmentStatus.CONFIRMED.value,
            ),
        ]
    )

    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_dashboard",
        email="site_manager_dashboard@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = manager_worker.id
    db_session.commit()

    response = api_client.get(
        "/api/dashboard",
        params={"period_key": "202603"},
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assignment_variance = next(
        item for item in payload["unprocessed_items"] if item["item_type"] == "assignment_variance"
    )
    missing_price = next(
        item for item in payload["unprocessed_items"] if item["item_type"] == "missing_price"
    )
    assert assignment_variance["count"] == 1
    assert missing_price["count"] == 2
    assert all(detail["project_name"] == "Managed Project" for detail in assignment_variance["details"])
    assert all(detail["project_name"] == "Managed Project" for detail in missing_price["details"])


def test_dashboard_returns_open_closing_rows_for_unclosed_projects(api_client, db_session):
    client = Client(id=generate_ulid(), name="Client Open", code="CO001")
    site = Site(id=generate_ulid(), name="Site Open", code="SO001")
    db_session.add_all([client, site])
    db_session.flush()

    project = Project(
        id=generate_ulid(),
        name="Open Dashboard Project",
        code="ODP001",
        client_id=client.id,
        site_id=site.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
    )
    db_session.add(project)

    admin_user = create_user_with_hashed_password(
        db=db_session,
        username="admin_dashboard_open",
        email="admin_dashboard_open@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/dashboard",
        params={"period_key": "202601"},
        headers=_auth_header(admin_user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    unclosed = next(item for item in payload["unprocessed_items"] if item["item_type"] == "unclosed_projects")
    row = next(item for item in payload["closing_status"] if item["project_id"] == project.id)
    assert unclosed["count"] >= 1
    assert row["status"] == "open"
    assert row["release_count"] == 0
    assert row["reclose_deadline"] is None