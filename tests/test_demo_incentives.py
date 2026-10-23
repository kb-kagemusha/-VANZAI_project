"""インセンティブ入力例はテストだけを改訂し、元の履歴・回答・配置・入力済み金額を保持。"""
import copy
from decimal import Decimal
from datetime import date, datetime, timezone
import json
import pytest
from scripts.enable_demo_incentives import apply, preview, fingerprint
from scripts.seed_calendar_demo import schedule
from src.models.order_request import OrderRequestVersion, OrderRequestDelivery, OrderRequestDocument
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoice
from src.services.order_request_service import OrderRequestService
from src.services.order_billing import OrderBillingService
from src.services.participation_calendar import build
from src.services import worker_schedule as ws
from tests.test_api_order_requests import _worker, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401


def demo(db, actor, client, workers, month, index, kind="test"):
    first = f"2026-{month:02d}-{1+index*4:02d}"
    last = f"2026-{month:02d}-{3+index*4:02d}"
    conditions = {"format":"additional-request-v1", "project_name":f"【テスト】{month}月 デモ{index}", "categories":["フェス系"],
        "schedule":schedule(first,last), "incentive_enabled":False}
    service = OrderRequestService(db)
    version = service.create_draft(actor=actor, kind=kind, work_date_label="", site_name="会場", site_id=None, site_address=None,
        request_conditions=json.dumps(conditions, ensure_ascii=False), body="", contact_name="担当者", contact_desk="", counterparty_note=f"calendar-demo-fixture:{month}:{index}",
        worker_ids=[w.id for w in workers], phone_first=False, phone_contacted_at=None, phone_note=None, tracker_user_id=None,
        follow_up_due_on=date(2026,12,31), internal_source={"client_id":client.id,"client_staff_id":None}, internal_source_set=True, allow_partial_accept=True)
    service.confirm(version, actor=actor)
    dates = [d["work_date"] for d in ws.version_work_days(version)]
    for i, delivery in enumerate(db.query(OrderRequestDelivery).filter_by(version_id=version.id)):
        delivery.send_status = "unknown"
        delivery.ack_reminded_at = datetime.now(timezone.utc)
        if i < 2:
            delivery.ack_status = "acked"
            selected = dates if i == 0 else dates[::2]
            ws.append_state(db, delivery, dates=selected, source="full_accept" if i == 0 else "partial_accept", actor=actor.username)
            ws.set_application(db, series_id=version.series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor.username)
        elif i == 2:
            delivery.ack_status = "declined"
            delivery.decline_reason = "日程が合わない"
    ws.rebuild_series(db, version.series_id, actor=actor.username)
    return version


def test_eight_incentive_examples_preserve_answers_history_and_protect_amounts(db_session, admin_user, client, pdf_root):
    workers = [_worker(db_session, f"対象{i}") for i in range(4)]
    sources = [demo(db_session, admin_user, client, workers, month, i) for month in (10,11) for i in range(5)]
    formal = demo(db_session, admin_user, client, workers, 10, 6, kind="formal")
    # 変更確認待ちも含めて保持できることを確認する。
    pending = OrderRequestService(db_session).revise(sources[1], actor=admin_user, reason="変更確認待ちの例")
    OrderRequestService(db_session).confirm(pending, actor=admin_user)
    for d in db_session.query(OrderRequestDelivery).filter_by(version_id=pending.id):
        d.send_status = "unknown"
    OrderBillingService(db_session).save_amount(sources[0].id, billing_month="202610", amount=Decimal("10000"), expected_revision=0, reason="入力済みは保持", actor=admin_user, client_id=client.id)
    db_session.flush()
    originals = {v.id:(copy.deepcopy(v.snapshot_json),v.pdf_object_key,v.request_conditions) for v in db_session.query(OrderRequestVersion)}
    before = {v.series_id:fingerprint(db_session,v.series_id) for v in sources+[formal]}
    previewed = preview(db_session)
    assert len(previewed["planned"]) == 8 and {r["kind"] for r in previewed["planned"]} == {"test"}
    result = apply(db_session)
    assert result["revised"] == result["enabled_demo_count"] == 8
    assert db_session.query(OrderRequestDocument).count() == 11
    assert db_session.query(OrderRequestVersion).count() == len(originals)+8
    assert all(fingerprint(db_session,series_id) == old for series_id,old in before.items())
    for identifier, old in originals.items():
        v = db_session.get(OrderRequestVersion, identifier)
        assert (v.snapshot_json,v.pdf_object_key,v.request_conditions) == old
    rows = OrderBillingService(db_session).rows(include_test=True)
    enabled = [row for row in rows if row["incentive_enabled"]]
    assert len(enabled) == 8 and all(r["is_test"] and r["incentive_note"] and r["incentive_amount"] is None for r in enabled)
    assert all(not r["incentive_enabled"] for r in rows if r["version_id"] in (formal.id,sources[0].id))
    assert db_session.query(OrderBillingAmount).count() == 1 and db_session.query(OrderBillingInvoice).count() == 0
    assert not any(r["incentive_enabled"] for r in OrderBillingService(db_session).rows())
    assert apply(db_session)["revised"] == 0
    assert db_session.query(OrderRequestVersion).count() == len(originals)+8


def test_insufficient_eligible_sources_does_not_start_revisions(db_session, admin_user, client, pdf_root):
    worker = _worker(db_session, "対象")
    source = demo(db_session, admin_user, client, [worker], 10, 0)
    before = db_session.query(OrderRequestVersion).count()
    with pytest.raises(RuntimeError, match="8件分"):
        apply(db_session)
    assert db_session.query(OrderRequestVersion).count() == before
    assert json.loads(source.request_conditions)["incentive_enabled"] is False
