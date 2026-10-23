"""ダミー投入の二重化・LINE送信・正式請求への混入を防止する。"""
from datetime import date

from scripts.seed_calendar_demo import seed, DATASET
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.models.transaction import WorkerAvailability, Invoice, Actual
from src.services.order_billing import OrderBillingService
from src.services.participation_calendar import build
from tests.test_api_order_requests import _worker, _auth, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_line_daily import _create_confirm
from src.services.document_storage import DocumentStorage


def test_calendar_demo_is_test_only_idempotent_and_visible_in_all_calendars(api_client, db_session, admin_user, client, pdf_root):
    workers = [_worker(db_session, f"ダミー{i}") for i in range(8)]
    db_session.add(WorkerAvailability(worker_id=workers[0].id, availability_date=date(2026, 10, 1), status="unavailable", notes="元の入力"))
    db_session.flush()
    result = seed(db_session, convert_existing=False)
    db_session.commit()
    assert result["created"] == 30
    assert db_session.query(OrderRequestDocument).count() == 30

    assert {d.kind for d in db_session.query(OrderRequestDocument)} == {"test"}
    assert db_session.query(OrderRequestVersion).count() == 36
    assert not OrderBillingService(db_session).rows()
    assert len(OrderBillingService(db_session).rows(include_test=True)) == 30
    assert not build(db_session, start="2026-10-01", end="2026-10-31")
    days = build(db_session, start="2026-10-01", end="2026-10-31", include_test=True)
    assert len({e["series_id"] for day in days for e in day["events"]}) == 15
    assert any(e["changing"] for day in days for e in day["events"])
    assert any(e["ok"] for day in days for e in day["events"])
    assert any(e["unanswered"] for day in days for e in day["events"])
    assert all(e["categories"] for day in days for e in day["events"])
    assert {d.send_status for d in db_session.query(OrderRequestDelivery)} == {"unknown"}
    assert db_session.query(Invoice).count() == db_session.query(Actual).count() == 0
    original = db_session.query(WorkerAvailability).filter_by(worker_id=workers[0].id, availability_date=date(2026, 10, 1)).one()
    assert original.notes == "元の入力" and original.status == "unavailable"
    auth = _auth(admin_user.username)
    url = "/api/availability-calendar?date_from=2026-10-01&date_to=2026-10-31"
    ordinary = api_client.get(url, headers=auth)
    assert ordinary.status_code == 200, ordinary.text
    assert not any(day["order_events"] for w in ordinary.json()["workers"] for day in w["days"].values())
    included = api_client.get(url + "&include_test=true", headers=auth)
    assert included.status_code == 200, included.text
    assert any(day["order_events"] for w in included.json()["workers"] for day in w["days"].values())
    repeat = seed(db_session, convert_existing=False)
    assert repeat["created"] == repeat["availability_created"] == 0
    assert db_session.query(OrderRequestDocument).count() == 30


def test_existing_sample_reclassification_preserves_original_pdf(api_client, db_session, admin_user, client, pdf_root):
    worker = _worker(db_session, "ダミー")
    source = _create_confirm(api_client, admin_user, [worker.id], project="【サンプル】秋の催事")
    version = db_session.get(OrderRequestVersion, source["id"])
    original_key = version.pdf_object_key
    original_pdf = DocumentStorage().read_bytes(original_key)
    result = seed(db_session)
    db_session.commit()
    assert result["converted"] == 1
    assert db_session.get(OrderRequestDocument, source["document_id"]).kind == "test"
    assert version.pdf_object_key != original_key
    assert DocumentStorage().read_bytes(original_key) == original_pdf
