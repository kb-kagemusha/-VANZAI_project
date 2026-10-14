"""GET/PUT /api/worker-availability/preferences のAPIテスト"""
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.enums import AuditAction, UserRole
from src.services.audit import AuditLog


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_worker_can_upsert_and_get_availability_preferences(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_pref",
        email="worker_pref@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    update_response = api_client.put(
        "/api/worker-availability/preferences",
        json={
            "weekly_default_statuses": {"0": "unavailable", "6": "unavailable"},
            "holiday_default_status": "unavailable",
            "auto_apply_enabled": True,
        },
        headers=_auth_header(user.username),
    )

    assert update_response.status_code == 200
    assert update_response.json()["weekly_default_statuses"] == {"0": "unavailable", "6": "unavailable"}

    get_response = api_client.get(
        "/api/worker-availability/preferences",
        headers=_auth_header(user.username),
    )
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["worker_id"] == worker.id
    assert payload["holiday_default_status"] == "unavailable"
    assert payload["auto_apply_enabled"] is True

    audit_log = db_session.query(AuditLog).filter(AuditLog.action == AuditAction.STAFF_AVAILABILITY_PREFERENCES_UPDATED.value).one()
    assert audit_log.actor == user.username


def test_worker_get_preferences_defaults_when_not_saved(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_pref_default",
        email="worker_pref_default@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    response = api_client.get(
        "/api/worker-availability/preferences",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == worker.id
    assert payload["weekly_default_statuses"] == {}
    assert payload["holiday_default_status"] is None
    assert payload["auto_apply_enabled"] is True