"""GET /api/workers, /api/suppliers, /api/clients, /api/sites, /api/project-types, /api/roles のAPIテスト"""
from datetime import date

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.domain.worker_tags import add_months, tokyo_today
from src.models.base import generate_ulid
from src.models.enums import AvailabilityStatus, UserRole
from src.models.master import Client, ProjectType, Role, Site, Supplier, Worker, WorkerAvailabilityPreference


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


# ===========================
# /api/workers
# ===========================

def test_list_workers_returns_paginated_items(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers",
        email="ops_workers@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"sort_by": "name", "sort_order": "asc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    ids = [item["id"] for item in payload["items"]]
    assert worker.id in ids


def test_list_workers_filter_by_is_active(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers_active",
        email="ops_workers_active@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    active_worker = Worker(id=generate_ulid(), name="Active Worker", is_active=True)
    inactive_worker = Worker(id=generate_ulid(), name="Inactive Worker", is_active=False)
    db_session.add_all([active_worker, inactive_worker])
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"is_active": "true"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert active_worker.id in item_ids
    assert inactive_worker.id not in item_ids


def test_list_workers_search(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_workers_search",
        email="ops_workers_search@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    w1 = Worker(id=generate_ulid(), name="Tanaka Taro")
    w2 = Worker(id=generate_ulid(), name="Yamada Hanako")
    db_session.add_all([w1, w2])
    db_session.commit()

    response = api_client.get(
        "/api/workers",
        params={"search": "Tanaka"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert w1.id in item_ids
    assert w2.id not in item_ids


def test_list_workers_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_blocks",
        email="worker_role_blocks@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/workers", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_worker_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_worker",
        email="ops_create_worker@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/workers",
        json={"name": "New Worker", "email": "new-worker@example.com", "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_worker_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_worker",
        email="admin_create_worker@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/workers",
        json={"name": "New Worker", "email": "new-worker@example.com", "phone": "09012345678", "notes": "memo", "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Worker"
    assert payload["email"] == "new-worker@example.com"
    assert payload["notes"] == "memo"


def test_worker_intake_profile_round_trip(api_client, db_session):
    from datetime import date as date_cls

    from src.domain.worker_profile import completed_years

    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_worker_profile",
        email="admin_worker_profile@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()
    headers = _auth_header(user.username)
    birth = date_cls(1998, 1, 15)
    profile = {
        "birth_date": "1998-01-15",
        "marital_status": "yes",
        "address": "東京都渋谷区1-2-3",
        "hometown": "大阪",
        "nearest_station": "渋谷",
        "station_walk_minutes": 8,
        "final_education": "大学卒",
        "licenses_qualifications": "普通自動車",
        "car_drive_ok": True,
        "hiace_drive_ok": False,
        "truck_drive": "2t",
        "work_history": [
            {
                "period_from": "2018-04",
                "period_to": "2022-03",
                "company_name": "株式会社例",
                "employment_type": "正社員",
                "industry": "販売",
                "job_description": "店頭販売",
                "resignation_reason": "転居",
            },
            {
                "period_from": "",
                "company_name": "  ",
            },
        ],
        "ploomx_sales_experience": "半年",
        "smoking_ok": False,
        "lucky_self": "いいと思う",
        "hobbies": "映画",
        "personality_strengths": "継続",
        "personality_weaknesses": "心配性",
        "club_activity": "野球部",
        "motivation": "現場が好き",
        "self_pr": "接客",
        "life_goal": "独立",
        "desired_income": "月収30万円",
        "available_days_per_week": 4,
        "available_weekdays": ["fri", "mon", "mon"],
        "available_time_from": "09:00",
        "available_time_to": "18:00",
        "available_start_date": "2026-11-01",
        "payment_terms_ok": True,
    }

    created = api_client.post(
        "/api/workers",
        json={"name": "Profile Worker", "is_active": True, "profile": profile},
        headers=headers,
    )
    assert created.status_code == 200
    body = created.json()["profile"]
    assert body["age"] == completed_years(birth)
    assert body["birth_date"] == "1998-01-15"
    assert body["marital_status"] == "yes"
    assert body["station_walk_minutes"] == 8
    assert body["truck_drive"] == "2t"
    assert body["work_history"] == [profile["work_history"][0]]
    assert body["available_weekdays"] == ["mon", "fri"]
    assert body["club_activity"] == "野球部"
    assert body["payment_terms_ok"] is True

    kept = api_client.put(
        f"/api/workers/{created.json()['id']}",
        json={"name": "Profile Worker Renamed", "is_active": True},
        headers=headers,
    )
    assert kept.status_code == 200
    assert kept.json()["name"] == "Profile Worker Renamed"
    assert kept.json()["profile"]["address"] == "東京都渋谷区1-2-3"
    assert kept.json()["profile"]["age"] == completed_years(birth)

    future = api_client.post(
        "/api/workers",
        json={"name": "Future Birth", "is_active": True, "profile": {"birth_date": "2999-01-01"}},
        headers=headers,
    )
    assert future.status_code == 422


def test_update_worker_succeeds_for_admin(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_update_worker",
        email="admin_update_worker@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "Updated Worker", "email": "updated-worker@example.com", "phone": "08000000000", "introducer_supplier_id": None, "notes": "updated", "is_active": False},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated Worker"
    assert payload["email"] == "updated-worker@example.com"
    assert payload["is_active"] is False


def test_worker_tags_are_predefined_only(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_worker_tags",
        email="admin_worker_tags@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()
    headers = _auth_header(user.username)

    catalog = api_client.get("/api/worker-tags", headers=headers)
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    codes = [item["code"] for item in items]
    assert codes == [
        "newcomer",
        "food_d",
        "commercial_d",
        "shibuya_smoke_d",
        "event_small_d",
        "event_medium_d",
        "event_large_d",
    ]
    assert items[0]["description"] == "付けてから3ヶ月で外れます"

    created = api_client.post(
        "/api/workers",
        json={"name": "Tagged Worker", "is_active": True, "tags": ["food_d", "newcomer", "newcomer"]},
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json()["tags"] == ["newcomer", "food_d"]
    tagged = db_session.get(Worker, created.json()["id"])
    assert tagged is not None
    assert tagged.newcomer_until == add_months(tokyo_today(), 3)
    kept_until = tagged.newcomer_until

    kept = api_client.put(
        f"/api/workers/{created.json()['id']}",
        json={"name": "Tagged Worker", "is_active": True, "tags": ["newcomer", "food_d"]},
        headers=headers,
    )
    assert kept.status_code == 200
    db_session.expire_all()
    assert db_session.get(Worker, created.json()["id"]).newcomer_until == kept_until

    exclusive = api_client.post(
        "/api/workers",
        json={"name": "Event Size Worker", "is_active": True, "tags": ["event_small_d", "event_medium_d", "food_d"]},
        headers=headers,
    )
    assert exclusive.status_code == 200
    assert exclusive.json()["tags"] == ["food_d", "event_medium_d"]

    rejected = api_client.post(
        "/api/workers",
        json={"name": "Free Tag Worker", "is_active": True, "tags": ["夜勤専門"]},
        headers=headers,
    )
    assert rejected.status_code == 422

    listed = api_client.get("/api/workers", params={"tag": "food_d"}, headers=headers)
    assert listed.status_code == 200
    assert created.json()["id"] in [item["id"] for item in listed.json()["items"]]

    hidden = api_client.get("/api/workers", params={"tag": "commercial_d"}, headers=headers)
    assert hidden.status_code == 200
    assert created.json()["id"] not in [item["id"] for item in hidden.json()["items"]]

    unknown = api_client.get("/api/workers", params={"tag": "regular"}, headers=headers)
    assert unknown.status_code == 422

    tagged.newcomer_until = date(2020, 1, 1)
    db_session.commit()
    expired = api_client.get("/api/workers", params={"tag": "newcomer"}, headers=headers)
    assert expired.status_code == 200
    assert created.json()["id"] not in [item["id"] for item in expired.json()["items"]]
    db_session.expire_all()
    dropped = db_session.get(Worker, created.json()["id"])
    assert dropped is not None
    assert "newcomer" not in (dropped.tags or [])
    assert dropped.newcomer_until is None
    assert "food_d" in dropped.tags


def test_get_worker_availability_preferences_returns_saved_values(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_worker_preferences",
        email="ops_worker_preferences@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.add(
        WorkerAvailabilityPreference(
            id=generate_ulid(),
            worker_id=worker.id,
            weekly_default_statuses={"1": AvailabilityStatus.UNAVAILABLE.value, "6": AvailabilityStatus.CONSULT_REQUIRED.value},
            holiday_default_status=AvailabilityStatus.UNAVAILABLE.value,
            auto_apply_enabled=True,
        )
    )
    db_session.commit()

    response = api_client.get(
        f"/api/workers/{worker.id}/availability-preferences",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == worker.id
    assert payload["weekly_default_statuses"] == {"1": "unavailable", "6": "consult_required"}
    assert payload["holiday_default_status"] == "unavailable"
    assert payload["auto_apply_enabled"] is True


def test_get_worker_availability_preferences_returns_defaults_when_not_saved(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_worker_preferences_default",
        email="ops_worker_preferences_default@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get(
        f"/api/workers/{worker.id}/availability-preferences",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == worker.id
    assert payload["weekly_default_statuses"] == {}
    assert payload["holiday_default_status"] is None
    assert payload["auto_apply_enabled"] is True


def test_get_worker_availability_preferences_blocked_for_worker_role(api_client, db_session, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_preferences_blocked",
        email="worker_preferences_blocked@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get(
        f"/api/workers/{worker.id}/availability-preferences",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


# ===========================
# /api/suppliers
# ===========================

def test_list_suppliers_returns_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_suppliers",
        email="ops_suppliers@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    supplier = Supplier(id=generate_ulid(), name="Test Supplier", payout_terms_days=30, is_active=True)
    db_session.add(supplier)
    db_session.commit()

    response = api_client.get("/api/suppliers", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert supplier.id in item_ids


def test_list_suppliers_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_suppliers",
        email="worker_role_suppliers@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/suppliers", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_supplier_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_supplier",
        email="ops_create_supplier@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/suppliers",
        json={"name": "New Supplier", "payout_terms_days": 30, "is_active": True},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_supplier_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_supplier",
        email="admin_create_supplier@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/suppliers",
        json={"name": "New Supplier", "contact_email": "supplier@example.com", "contact_phone": "0312345678", "payout_terms_days": 30, "default_daily_price": "16500.00", "is_active": True, "notes": "memo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Supplier"
    assert payload["contact_email"] == "supplier@example.com"
    assert payload["default_daily_price"] == "16500.00"


def test_update_supplier_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_update_supplier",
        email="admin_update_supplier@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    supplier = Supplier(id=generate_ulid(), name="Before Supplier", payout_terms_days=70, is_active=True)
    db_session.add(supplier)
    db_session.commit()

    response = api_client.put(
        f"/api/suppliers/{supplier.id}",
        json={"name": "Updated Supplier", "contact_email": "updated-supplier@example.com", "contact_phone": "0399999999", "payout_terms_days": 45, "default_daily_price": "18000.00", "is_active": False, "notes": "updated"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated Supplier"
    assert payload["payout_terms_days"] == 45
    assert payload["is_active"] is False


# ===========================
# /api/clients
# ===========================

def test_list_clients_returns_items(api_client, db_session, client):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_clients",
        email="ops_clients@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/clients", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert client.id in item_ids


def test_list_clients_search(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_clients_search",
        email="ops_clients_search@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    c1 = Client(id=generate_ulid(), name="ABC Company", code="ABC001")
    c2 = Client(id=generate_ulid(), name="XYZ Corp", code="XYZ001")
    db_session.add_all([c1, c2])
    db_session.commit()

    response = api_client.get(
        "/api/clients",
        params={"search": "ABC"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    item_ids = [item["id"] for item in payload["items"]]
    assert c1.id in item_ids
    assert c2.id not in item_ids


def test_list_clients_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_clients",
        email="worker_role_clients@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/clients", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_client_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_client",
        email="ops_create_client@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/clients",
        json={"name": "New Client", "code": "NC001", "contact_name": "担当", "contact_email": "new-client@example.com"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_client_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_client",
        email="admin_create_client@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/clients",
        json={"name": "New Client", "code": "NC001", "contact_name": "担当", "contact_email": "new-client@example.com"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Client"
    assert payload["code"] == "NC001"
    assert payload["contact_email"] == "new-client@example.com"


# ===========================
# /api/sites
# ===========================

def test_list_sites_returns_items(api_client, db_session, site):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_sites",
        email="ops_sites@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/sites", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert site.id in item_ids


def test_list_sites_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_sites",
        email="worker_role_sites@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/sites", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_site_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_site",
        email="ops_create_site@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/sites",
        json={"name": "New Site", "code": "NS001", "address": "Tokyo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_site_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_site",
        email="admin_create_site@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/sites",
        json={"name": "New Site", "code": "NS001", "address": "Tokyo"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Site"
    assert payload["code"] == "NS001"
    assert payload["address"] == "Tokyo"


# ===========================
# /api/project-types
# ===========================

def test_list_project_types_returns_items(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_project_types",
        email="ops_project_types@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    pt = ProjectType(id=generate_ulid(), name="General", code="GEN")
    db_session.add(pt)
    db_session.commit()

    response = api_client.get("/api/project-types", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert pt.id in item_ids


def test_list_project_types_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_project_types",
        email="worker_role_project_types@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/project-types", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_project_type_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_project_type",
        email="ops_create_project_type@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/project-types",
        json={"name": "New Type", "code": "NTYPE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_project_type_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_project_type",
        email="admin_create_project_type@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/project-types",
        json={"name": "New Type", "code": "NTYPE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Type"
    assert payload["code"] == "NTYPE"
    assert payload["description"] == "desc"


# ===========================
# /api/roles
# ===========================

def test_list_roles_returns_items(api_client, db_session, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_roles",
        email="ops_roles@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.get("/api/roles", headers=_auth_header(user.username))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    item_ids = [item["id"] for item in payload["items"]]
    assert role.id in item_ids


def test_list_roles_blocked_for_worker_role(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_role_roles",
        email="worker_role_roles@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.get("/api/roles", headers=_auth_header(user.username))
    assert response.status_code == 403


def test_create_role_requires_master_write(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_role",
        email="ops_create_role@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/roles",
        json={"name": "New Role", "code": "NROLE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_role_succeeds_for_admin(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_create_role",
        email="admin_create_role@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/roles",
        json={"name": "New Role", "code": "NROLE", "description": "desc"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "New Role"
    assert payload["code"] == "NROLE"
    assert payload["description"] == "desc"


# ===========================
# site_manager も MASTER_READ を持つことを確認
# ===========================

def test_master_list_endpoints_accessible_by_site_manager(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="sm_master_access",
        email="sm_master_access@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    db_session.commit()

    for path in ("/api/workers", "/api/suppliers", "/api/clients", "/api/sites", "/api/project-types", "/api/roles"):
        response = api_client.get(path, headers=_auth_header(user.username))
        assert response.status_code == 200, f"{path} returned {response.status_code} for site_manager"
