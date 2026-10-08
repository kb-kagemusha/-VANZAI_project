"""GET/POST /api/worker-availability のAPIテスト"""
from datetime import date

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import Worker
from src.models.transaction import WorkerAvailability


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def test_worker_can_upsert_and_list_own_availability(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_availability",
        email="worker_availability@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    upsert_response = api_client.post(
        "/api/worker-availability",
        json={
            "availability_date": "2026-04-10",
            "status": "available_all_day",
            "notes": "終日で対応可能",
        },
        headers=_auth_header(user.username),
    )

    assert upsert_response.status_code == 200
    upsert_payload = upsert_response.json()
    assert upsert_payload["worker_id"] == worker.id
    assert upsert_payload["status"] == "available_all_day"

    list_response = api_client.get(
        "/api/worker-availability",
        params={"availability_date_from": "2026-04-01", "availability_date_to": "2026-04-30"},
        headers=_auth_header(user.username),
    )

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["notes"] == "終日で対応可能"


def test_worker_availability_is_scoped_to_self(api_client, db_session, worker):
    other_worker = Worker(
        id=generate_ulid(),
        name="Other Availability Worker",
        email="other-availability@example.com",
    )
    db_session.add(other_worker)
    db_session.flush()

    entry = WorkerAvailability(
        id=generate_ulid(),
        worker_id=other_worker.id,
        availability_date=date(2026, 4, 12),
        status="unavailable",
        notes="別件あり",
    )
    db_session.add(entry)

    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_availability_self_scope",
        email="worker_availability_self_scope@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    response = api_client.get(
        "/api/worker-availability",
        params={"availability_date_from": "2026-04-01", "availability_date_to": "2026-04-30"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0