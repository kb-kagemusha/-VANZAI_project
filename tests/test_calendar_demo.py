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


def test_expand_demo_and_archive_only_duplicate_legacy_samples(api_client, db_session, admin_user, client, pdf_root):
    workers = [_worker(db_session, f"ダミー{i}") for i in range(6)]
    ids = []
    for name in ("サンプルイベント", "サンプルイベント２", "サンプルイベント3"):
        ids.append(_create_confirm(api_client, admin_user, [workers[0].id], kind="test", project=name)["document_id"])
    seed(db_session, convert_existing=False)
    result = seed(db_session, per_month=45, prune_legacy_samples=True)
    db_session.commit()
    assert result["created"] == 60 and result["archived"] == 2
    assert db_session.query(OrderRequestDocument).count() == 93  # 履歴を保持
    assert db_session.query(OrderRequestDocument).filter(OrderRequestDocument.deleted_at.is_(None)).count() == 91
    assert sum(db_session.get(OrderRequestDocument, identifier).deleted_at is None for identifier in ids) == 1
    for month in (10, 11):
        count = db_session.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.like(f"{DATASET}:{month}:%"), ~OrderRequestVersion.counterparty_note.like("%:revision")).count()
        assert count == 45
    days = build(db_session, start="2026-10-01", end="2026-11-30", include_test=True)
    assert any(e["unavailable"] for day in days for e in day["events"])
    repeat = seed(db_session, per_month=45, prune_legacy_samples=True)
    assert repeat["created"] == repeat["archived"] == 0


def test_unavailable_is_explicit_and_excludes_common_holidays(api_client, db_session, admin_user, client, pdf_root):
    from src.services import worker_schedule as ws
    workers = [_worker(db_session, f"返事{i}") for i in range(4)]
    # 固定の3勤務日と1休業日。未回答を×に変えない。
    from scripts.seed_calendar_demo import schedule
    sched = schedule("2026-11-01", "2026-11-04")
    sched["work_groups"][0]["excluded_dates"] = ["2026-11-03"]
    source = _create_confirm(api_client, admin_user, [w.id for w in workers], schedule=sched,
        absences={workers[3].id: ["2026-11-02"]})
    version = db_session.get(OrderRequestVersion, source["id"])
    deliveries = {d.worker_id: d for d in db_session.query(OrderRequestDelivery).filter_by(version_id=version.id)}
    for delivery in deliveries.values():
        delivery.send_status = "unknown"
    partial = deliveries[workers[0].id]
    partial.ack_status = "acked"
    ws.append_state(db_session, partial, dates=["2026-11-01"], source="partial_accept", actor=admin_user.username)
    ws.set_application(db_session, series_id=version.series_id, worker_id=partial.worker_id, delivery=partial, ended_reason=None, actor=admin_user.username)
    deliveries[workers[1].id].ack_status = "declined"
    db_session.flush()
    days = {day["date"]: day["events"][0] for day in build(db_session, series_id=version.series_id)}
    assert "2026-11-03" not in days
    ids = lambda event, key: {person["worker_id"] for person in event[key]}
    assert ids(days["2026-11-01"], "ok") == {workers[0].id}
    assert ids(days["2026-11-01"], "unavailable") == {workers[1].id}
    assert ids(days["2026-11-02"], "unavailable") == {workers[0].id, workers[1].id, workers[3].id}
    assert workers[2].id in ids(days["2026-11-02"], "unanswered")
    for event in days.values():
        all_ids = [p["worker_id"] for key in ("ok", "changing", "unanswered", "unavailable") for p in event[key]]
        assert len(all_ids) == len(set(all_ids))


def test_named_workers_receive_test_plans_even_if_line_linked(db_session, admin_user, client, pdf_root):
    from datetime import datetime, timezone
    from src.models.line_order import LineWorkerLink
    named = [_worker(db_session, name) for name in ("テストアカウント", "坂井 貴博")]
    for index, worker in enumerate(named):
        db_session.add(LineWorkerLink(worker_id=worker.id, line_user_id=f"U_demo_{index}", status="active", linked_at=datetime.now(timezone.utc)))
    db_session.flush()
    result = seed(db_session, per_month=45, convert_existing=False)
    assert set(result["requested_worker_days"]) == {"テストアカウント", "坂井 貴博"}
    assert all(count > 0 for count in result["requested_worker_days"].values())
    assert db_session.query(LineWorkerLink).count() == 2
    assert {d.send_status for d in db_session.query(OrderRequestDelivery)} == {"unknown"}
