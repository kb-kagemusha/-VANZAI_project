from datetime import datetime, timezone

from scripts.repair_demo_schedule_gaps import comparison, repair, target_series
from src.models.line_daily import WorkerScheduleEntry
from src.models.order_request import OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion
from src.models.transaction import AuditLog
from src.services import worker_schedule as ws
from src.services.line_worker_portal import LineWorkerPortal
from tests.test_api_order_requests import _worker, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_line_daily import _create_confirm, _revise_confirm, _schedule, _release


def test_restore_missing_twenty_day_and_partial_schedules_without_changing_answers(
    api_client, db_session, admin_user, client, pdf_root,
):
    worker = _worker(db_session, "テスト アカウント")
    old = _create_confirm(api_client, admin_user, [worker.id], kind="test", schedule=_schedule(1, 20))
    changing = _create_confirm(api_client, admin_user, [worker.id], kind="test", schedule=_schedule(21, 24))
    latest = _revise_confirm(api_client, admin_user, changing["id"])
    formal = _create_confirm(api_client, admin_user, [worker.id], schedule=_schedule(25, 25))
    archived = _create_confirm(api_client, admin_user, [worker.id], kind="test", schedule=_schedule(26, 26))
    protected = []
    for index, info in enumerate((old, changing, formal, archived)):
        version = db_session.get(OrderRequestVersion, info["id"])
        version.counterparty_note = "calendar-demo-202610-v4:regression"
        delivery = db_session.query(OrderRequestDelivery).filter_by(version_id=version.id).one()
        delivery.ack_status, delivery.send_status = "acked", "unknown"
        selected = delivery.offered_dates[::2] if index == 1 else delivery.offered_dates
        state = ws.append_state(db_session, delivery, dates=selected, source="partial_accept" if index == 1 else "full_accept", actor=admin_user.username)
        ws.set_application(db_session, series_id=version.series_id, worker_id=worker.id, delivery=delivery, ended_reason=None, actor=admin_user.username)
        protected.append((version, delivery, state.id, list(state.dates), version.snapshot_json, version.pdf_object_key))
    db_session.get(OrderRequestVersion, latest["id"]).counterparty_note = "calendar-demo-202610-v4:regression:revision"
    db_session.get(OrderRequestDocument, archived["document_id"]).deleted_at = datetime.now(timezone.utc)
    db_session.flush()
    assert db_session.query(WorkerScheduleEntry).count() == 0  # 元の投入漏れを再現
    assert repair(db_session) == {"demo_series": 2, "missing_worker_days": 22, "unexpected_worker_days": 0}
    result = repair(db_session, apply=True)
    assert result["missing_worker_days"] == 22 and result["remaining_missing_worker_days"] == 0
    assert comparison(db_session, target_series(db_session))[0] == comparison(db_session, target_series(db_session))[1]
    rows = db_session.query(WorkerScheduleEntry).all()
    assert len(rows) == 22
    assert sum(r.status == "active" for r in rows) == 20
    assert sum(r.status == "changing" for r in rows) == 2
    assert {r.document_id for r in rows} == {old["document_id"], changing["document_id"]}
    for version, delivery, state_id, dates, snapshot, pdf in protected:
        assert ws.get_application(db_session, version.series_id, worker.id).applied_version_id == version.id
        assert delivery.current_participation_state_id == state_id and ws.current_state(db_session, delivery).dates == dates
        assert delivery.ack_status == "acked" and version.snapshot_json == snapshot and version.pdf_object_key == pdf
    _release(db_session, actions=("web_home", "web_orders"))
    orders = LineWorkerPortal(db_session).orders(worker)["items"]
    assert {o["document_number"]: o["work_days"] for o in orders} == {old["document_number"]: 20, changing["document_number"]: 2}
    assert repair(db_session, apply=True)["missing_worker_days"] == 0
    audits = db_session.query(AuditLog).filter_by(action="demo_schedule_gaps_repaired").all()
    assert len(audits) == 1 and len(audits[0].target_id) <= 26
