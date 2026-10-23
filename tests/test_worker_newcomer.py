"""稼働開始日による新人表示と、同一イベントの日別人数差。"""
from datetime import date
import pytest
from src.domain.worker_tags import is_newcomer_from_start
from src.api.schemas import WorkerListItem, WorkerProfile
from src.services.participation_calendar import build, registered_workers
from scripts.enrich_calendar_demo import enrich, DATASET, NEW_WORKERS, DAILY_COUNTS
from scripts.seed_calendar_demo import seed, rebalance_demo
from src.models.master import Worker
from src.models.order_request import OrderRequestVersion, OrderRequestDocument, OrderRequestDelivery
from tests.test_api_order_requests import _worker, _auth, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401


@pytest.mark.parametrize("start,today,expected", [
    (None, date(2026,10,24), False),
    (date(2026,10,25), date(2026,10,24), False),
    (date(2026,10,24), date(2026,10,24), True),
    (date(2026,7,25), date(2026,10,24), True),
    (date(2026,7,24), date(2026,10,24), False),
    (date(2026,1,31), date(2026,4,29), True),
    (date(2026,1,31), date(2026,4,30), False),
    (date(2023,11,30), date(2024,2,28), True),
    (date(2023,11,30), date(2024,2,29), False),
])
def test_three_calendar_months(start, today, expected):
    assert is_newcomer_from_start(start, today) is expected


def test_worker_api_uses_start_date_not_manual_tag(api_client, db_session, admin_user, monkeypatch):
    monkeypatch.setattr("src.domain.worker_tags.tokyo_today", lambda: date(2026,10,24))
    monkeypatch.setattr("src.services.participation_calendar.tokyo_today", lambda: date(2026,10,24))
    recent = _worker(db_session, "新人")
    recent.available_start_date = date(2026,10,1)
    recent.tags = []
    old = _worker(db_session, "ベテラン")
    old.available_start_date = date(2025,10,1)
    old.tags = ["newcomer"]
    db_session.commit()
    response = api_client.get("/api/workers", headers=_auth(admin_user.username))
    assert response.status_code == 200, response.text
    flags = {w["id"]:w["is_newcomer"] for w in response.json()["items"]}
    assert flags[recent.id] is True and flags[old.id] is False
    rows = {w["worker_id"]: w for w in registered_workers(db_session)}
    assert rows[recent.id]["is_newcomer"] is True
    response = api_client.get("/api/availability-calendar?date_from=2026-10-01&date_to=2026-10-31", headers=_auth(admin_user.username))
    assert response.status_code == 200, response.text
    flags = {w["id"]:w["is_newcomer"] for w in response.json()["workers"]}
    assert flags[recent.id] is True and flags[old.id] is False
    # プロフィール更新直後も保存済みの日付だけで判定する。
    item = WorkerListItem(id="w", name="氏名", is_active=True, profile=WorkerProfile(available_start_date=date(2026,7,24)))
    assert item.model_dump()["is_newcomer"] is False


def test_newcomer_demo_has_daily_variation_without_overlap(db_session, admin_user, client, pdf_root):
    original_workers = [_worker(db_session, f"ダミー{i}") for i in range(20)]
    original_workers[0].available_start_date = date(2020,1,1)
    seed(db_session, per_month=45, convert_existing=False, include_long_events=True)
    rebalance_demo(db_session)
    originals = db_session.query(OrderRequestVersion).filter(OrderRequestVersion.counterparty_note.in_(("calendar-demo-202610-v2:10:46", "calendar-demo-202610-v2:11:46"))).all()
    pdfs = {v.id:v.pdf_object_key for v in originals}
    before_documents = db_session.query(OrderRequestDocument).filter(OrderRequestDocument.deleted_at.is_(None)).count()
    result = enrich(db_session, today=date(2026,10,24))
    db_session.flush()
    assert result["workers_added"] == 5 and result["events_replaced"] == 2
    assert result["newcomers"] == 5 and result["max_events_per_worker_day"] == 1
    assert result["daily_ok_counts"] == [list(DAILY_COUNTS)*2]*2
    assert db_session.query(OrderRequestDocument).filter(OrderRequestDocument.deleted_at.is_(None)).count() == before_documents
    assert original_workers[0].available_start_date == date(2020,1,1)
    assert all(w.available_start_date is not None for w in db_session.query(Worker))
    assert all(db_session.get(OrderRequestVersion, vid).pdf_object_key == key for vid,key in pdfs.items())
    new_ids = {w.id for w in db_session.query(Worker).filter(Worker.name.in_([name for name,_ in NEW_WORKERS]))}
    calendar = build(db_session, start="2026-10-10", end="2026-10-29", test_only=True)
    replacement = db_session.query(OrderRequestVersion).filter_by(counterparty_note=f"{DATASET}:10").one()
    events = [e for day in calendar for e in day["events"] if e["series_id"] == replacement.series_id]
    assert len(events[0]["ok"]) == 8 and len(events[1]["ok"]) == 4
    assert len(events[1]["unavailable"]) == 4
    assert new_ids.issubset({p["worker_id"] for e in events for p in e["ok"]})
    assert {d.send_status for d in db_session.query(OrderRequestDelivery).filter_by(version_id=replacement.id)} == {"unknown"}
    from scripts.repair_demo_schedule_gaps import comparison, target_series
    expected, actual = comparison(db_session, target_series(db_session))
    assert expected == actual
    repeat = enrich(db_session, today=date(2026,10,24))
    assert repeat["workers_added"] == repeat["events_replaced"] == repeat["start_dates_filled"] == 0

