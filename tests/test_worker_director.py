"""ディレクターのタグ・表示と本人テストアカウントの氏名復元。"""
from datetime import date
import pytest
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.services.audit import AuditService
from src.services.participation_calendar import build, registered_workers
from src.domain.worker_tags import normalize_worker_tags, is_director, reconcile_worker_tags
from scripts.restore_test_account_name import restore
from tests.test_api_order_requests import _worker, _auth, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_api_master_lists import _with_edit_guard
from tests.test_line_daily import _create_confirm


def test_director_tag_is_independent_and_does_not_expire():
    assert normalize_worker_tags(["event_small_d", "director", "event_large_d"]) == ["director", "event_large_d"]
    assert is_director(["director"]) is True
    assert is_director(None) is False
    assert reconcile_worker_tags(["director", "newcomer"], date(2020,1,1), date(2026,10,24))[0] == ["director"]


def test_director_can_be_checked_and_unchecked_in_worker_api(api_client, db_session, admin_user, client, pdf_root):
    auth = _auth(admin_user.username)
    catalog = api_client.get("/api/worker-tags", headers=auth)
    assert any(t["code"] == "director" and t["label"] == "ディレクター可能" for t in catalog.json()["items"])
    response = api_client.post("/api/workers", headers=auth, json={"name":"監督担当", "is_active":True, "tags":["director", "event_medium_d"]})
    assert response.status_code == 200, response.text
    worker_id = response.json()["id"]
    assert response.json()["is_director"] is True
    version = _create_confirm(api_client, admin_user, [worker_id], project="監督の表示確認")
    delivery = db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"]).one()
    delivery.send_status = "unknown"
    db_session.commit()
    assert next(w for w in registered_workers(db_session) if w["worker_id"] == worker_id)["is_director"] is True
    people = [p for day in build(db_session, series_id=db_session.get(OrderRequestVersion, version["id"]).series_id) for e in day["events"] for p in e["unanswered"]]
    assert people and all(p["is_director"] is True for p in people)
    listed = api_client.get("/api/workers?tag=director", headers=auth)
    assert worker_id in [w["id"] for w in listed.json()["items"]]
    response = api_client.get("/api/availability-calendar?date_from=2026-10-01&date_to=2026-10-31", headers=auth)
    assert next(w for w in response.json()["workers"] if w["id"] == worker_id)["is_director"] is True
    response = api_client.put(f"/api/workers/{worker_id}", headers=auth,
        json=_with_edit_guard(api_client, worker_id, auth, {"name":"監督担当", "is_active":True, "tags":["event_medium_d"]}))
    assert response.status_code == 200, response.text
    assert response.json()["is_director"] is False and response.json()["tags"] == ["event_medium_d"]
    people = [p for day in build(db_session, series_id=db_session.get(OrderRequestVersion, version["id"]).series_id) for e in day["events"] for p in e["unanswered"]]
    assert people and all(p["is_director"] is False for p in people)


def test_restore_only_the_audited_account_and_is_idempotent(db_session, admin_user):
    account = _worker(db_session, "高橋 直樹")
    account.furigana = "たかはし なおき"
    account.available_start_date = date(2025,1,1)
    unrelated = _worker(db_session, "高橋 直樹")
    AuditService(db_session).log("calendar_demo_worker_renamed", target_type="worker", target_id=account.id,
        actor=admin_user.username, before_value={"name":"テスト アカウント", "furigana":"てすと あかうんと"},
        after_value={"name":"高橋 直樹", "furigana":"たかはし なおき"})
    db_session.flush()
    assert restore(db_session) == {"restored":True,"name":"テスト アカウント"}
    db_session.expire_all()
    assert db_session.get(Worker, account.id).name == "テスト アカウント"
    assert db_session.get(Worker, account.id).furigana == "てすと あかうんと"
    assert db_session.get(Worker, account.id).available_start_date == date(2025,1,1)
    assert db_session.get(Worker, unrelated.id).name == "高橋 直樹"
    assert restore(db_session) == {"restored":False,"name":"テスト アカウント"}


def test_restore_refuses_unverified_account(db_session, admin_user):
    worker = _worker(db_session, "高橋 直樹")
    with pytest.raises(RuntimeError, match="一意"):
        restore(db_session)
    assert worker.name == "高橋 直樹"
