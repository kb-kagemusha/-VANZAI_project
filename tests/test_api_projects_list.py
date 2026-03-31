"""GET /api/projects のAPIテスト"""
from datetime import date

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import ProjectType
from src.models.transaction import Project


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_list_projects_returns_paginated_items(api_client, db_session, client, site):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_projects",
        email="ops_projects@example.com",
        password="secret123",
        role="ops",
    )
    project_type = ProjectType(
        id=generate_ulid(),
        name="Event",
        code="EVENT",
    )
    db_session.add(project_type)
    db_session.flush()

    project = Project(
        id=generate_ulid(),
        name="Project List Test",
        code="PLT001",
        client_id=client.id,
        site_id=site.id,
        project_type_id=project_type.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        is_active=True,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    db_session.add(project)
    db_session.commit()

    response = api_client.get(
        "/api/projects",
        params={"client_id": client.id, "search": "Project List"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == project.id
    assert payload["items"][0]["client_name"] == client.name
    assert payload["items"][0]["site_name"] == site.name
    assert payload["items"][0]["project_type_name"] == project_type.name


def test_list_projects_limits_site_manager_scope(api_client, db_session, client, worker):
    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_projects",
        email="site_manager_projects@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = worker.id
    db_session.add(site_manager)

    project_allowed = Project(
        id=generate_ulid(),
        name="Allowed Project",
        code="AP001",
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
        name="Hidden Project",
        code="HP001",
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
        "/api/projects",
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == project_allowed.id


def test_create_project_requires_project_write(api_client, db_session, client):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_create_project",
        email="accounting_create_project@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/projects",
        json={"name": "New Project", "client_id": client.id},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_project_succeeds_for_ops(api_client, db_session, client, site, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_project",
        email="ops_create_project@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    project_type = ProjectType(
        id=generate_ulid(),
        name="Campaign",
        code="CAMPAIGN",
    )
    db_session.add(project_type)
    db_session.commit()

    response = api_client.post(
        "/api/projects",
        json={
            "name": "Created Project",
            "code": "CP001",
            "client_id": client.id,
            "site_id": site.id,
            "project_type_id": project_type.id,
            "primary_manager_id": worker.id,
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
            "notes": "Created from API test",
            "is_active": True,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Created Project"
    assert payload["client_name"] == client.name
    assert payload["site_name"] == site.name
    assert payload["project_type_name"] == project_type.name
    assert payload["primary_manager_id"] == worker.id
    assert payload["notes"] == "Created from API test"


def test_update_project_notes_succeeds_for_ops(api_client, db_session, client):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_project_notes",
        email="ops_update_project_notes@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    project = Project(
        id=generate_ulid(),
        name="Project Notes Target",
        code="PNT001",
        client_id=client.id,
        is_active=True,
        notes="before",
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    db_session.add(project)
    db_session.commit()

    response = api_client.patch(
        f"/api/projects/{project.id}/notes",
        json={"notes": "updated notes"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == project.id
    assert payload["notes"] == "updated notes"


def test_update_project_succeeds_for_ops(api_client, db_session, client, site, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_project",
        email="ops_update_project@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    project_type = ProjectType(
        id=generate_ulid(),
        name="Renovation",
        code="RENOVATION",
    )
    project = Project(
        id=generate_ulid(),
        name="Project Update Target",
        code="PUT001",
        client_id=client.id,
        is_active=True,
        notes="before",
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_calc_mode="store_minutes",
    )
    db_session.add_all([project_type, project])
    db_session.commit()

    response = api_client.put(
        f"/api/projects/{project.id}",
        json={
            "name": "Project Update Result",
            "code": "PUT002",
            "client_id": client.id,
            "site_id": site.id,
            "project_type_id": project_type.id,
            "primary_manager_id": worker.id,
            "secondary_manager_id": worker.id,
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "notes": "updated body",
            "is_active": False,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == project.id
    assert payload["name"] == "Project Update Result"
    assert payload["code"] == "PUT002"
    assert payload["site_id"] == site.id
    assert payload["site_name"] == site.name
    assert payload["project_type_id"] == project_type.id
    assert payload["project_type_name"] == project_type.name
    assert payload["primary_manager_id"] == worker.id
    assert payload["secondary_manager_id"] == worker.id
    assert payload["notes"] == "updated body"
    assert payload["is_active"] is False
