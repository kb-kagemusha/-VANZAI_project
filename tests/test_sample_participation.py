import pytest
from scripts.add_sample_participation import build_plan, apply_plan
from tests.test_api_order_requests import _worker, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_line_daily import _create_confirm, _schedule
from src.models.order_request import OrderRequestDocument, OrderRequestDelivery
from src.models.line_daily import WorkerScheduleEntry
from src.models.transaction import Actual, Invoice, Payout
from src.services.wake_test_notifications import update
from src.services import worker_schedule as ws
from datetime import timedelta


def examples(api_client, db_session, admin_user):
    target = _worker(db_session, "真島 サンプル")
    other = _worker(db_session, "ほかの参加者")
    for day in (1, 3, 5):
        _create_confirm(api_client, admin_user, [other.id], kind="test", schedule=_schedule(day, day), project=f"【テスト】確認イベント{day}")
    return target


def test_preview_then_apply_is_test_only_preserves_sources_and_idempotent(api_client, db_session, admin_user, pdf_root):
    target = examples(api_client, db_session, admin_user)
    plan = build_plan(db_session, "真島")
    assert plan["ready"] and len(plan["events"]) == 3
    assert db_session.query(OrderRequestDocument).count() == 3
    originals = [(d.id, d.ack_status, d.send_status) for d in db_session.query(OrderRequestDelivery).all()]
    result = apply_plan(db_session, target.id, plan["token"]); db_session.commit()
    assert len(result["created"]) == 3 and result["line_sent"] is False
    assert db_session.query(OrderRequestDocument).count() == 6
    assert {d.kind for d in db_session.query(OrderRequestDocument)} == {"test"}
    entries = db_session.query(WorkerScheduleEntry).filter_by(worker_id=target.id, status="active").all()
    assert len(entries) == 3 and all(e.is_test for e in entries)
    assert len({e.work_date for e in entries}) == 3
    for did, ack, send in originals:
        delivery = db_session.get(OrderRequestDelivery, did)
        assert (delivery.ack_status, delivery.send_status) == (ack, send)
    assert db_session.query(Actual).count() == db_session.query(Invoice).count() == db_session.query(Payout).count() == 0
    assert apply_plan(db_session, target.id, plan["token"])["already_created"]
    assert db_session.query(OrderRequestDocument).count() == 6


def test_ambiguous_name_changed_preview_and_notifications_on_are_rejected(api_client, db_session, admin_user, pdf_root):
    target = examples(api_client, db_session, admin_user)
    plan = build_plan(db_session, "真島")
    with pytest.raises(ValueError): apply_plan(db_session, target.id, "wrong-token")
    _worker(db_session, "真島 別人")
    assert build_plan(db_session, "真島")["ready"] is False
    update(db_session, admin_user, enabled=True, enabled_until=ws.now_utc() + timedelta(hours=1), revision=0); db_session.commit()
    with pytest.raises(ValueError): apply_plan(db_session, target.id, plan["token"])
    assert db_session.query(OrderRequestDocument).count() == 3
