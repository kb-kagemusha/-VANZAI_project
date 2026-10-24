from datetime import datetime, timedelta, timezone

from scripts.repair_archived_demo_schedules import repair
from src.models.transaction import AuditLog
from src.models.line_daily import WorkerScheduleEntry
from src.models.order_request import OrderRequestDocument, OrderRequestVersion, OrderRequestDelivery
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.line_daily import LineDailyService
from src.services.line_worker_portal import LineWorkerPortal
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_line_daily import (
    _create_confirm, _revise_confirm, _schedule, _day, _release, _send_and_accept,
    _worker, _link, ops_user, pdf_root, line_env, fake_line,
)


def test_archived_demo_hidden_and_repaired_without_accepting_current_changes(
    api_client, db_session, ops_user, admin_user, pdf_root, line_env, fake_line,
):
    worker = _worker(db_session, "高橋 直樹")
    _link(api_client, ops_user, worker.id, "U123")
    old = _create_confirm(api_client, ops_user, [worker.id], kind="test", schedule=_schedule(1, 2))
    _send_and_accept(api_client, ops_user, old["deliveries"][0]["id"])
    # 氏名の修正だけでは、受託した版も予定の状態も変わらない。
    worker.name = "テスト アカウント"
    db_session.commit()
    assert {e.status for e in db_session.query(WorkerScheduleEntry)} == {"active"}
    assert ws.get_application(db_session, db_session.get(OrderRequestVersion, old["id"]).series_id, worker.id).applied_version_id == old["id"]
    old_newer = _revise_confirm(api_client, ops_user, old["id"])
    current = _create_confirm(api_client, ops_user, [worker.id], kind="test", schedule=_schedule(3, 4))
    _send_and_accept(api_client, ops_user, current["deliveries"][0]["id"])
    current_newer = _revise_confirm(api_client, ops_user, current["id"])
    for vid in (old["id"], old_newer["id"], current["id"], current_newer["id"]):
        db_session.get(OrderRequestVersion, vid).counterparty_note = "calendar-demo-202610-v1:test"
    doc = db_session.get(OrderRequestDocument, old["document_id"])
    doc.deleted_at = datetime.now(timezone.utc)
    AuditService(db_session).log("calendar_demo_rebalanced", target_type="order_request_document",
        target_id=doc.id, actor=ops_user.username, after_value={"replacement_document_id": current["document_id"]})
    db_session.commit()
    _release(db_session, actions=("wk_orders", "wk_schedule", "web_home", "web_orders"))
    daily, portal = LineDailyService(db_session), LineWorkerPortal(db_session)
    start, end = ws.today_jst(), ws.today_jst() + timedelta(days=6)
    for service in (daily, portal):
        entries = service._entries(worker.id, start, end)
        assert {e.document_id for e in entries} == {current["document_id"]}
        assert {e.status for e in entries} == {"changing"}
    code, messages = daily.orders(worker)
    assert code == "orders_shown"
    assert len(messages[0]["contents"]["contents"]) == 1
    orders = portal.orders(worker)["items"]
    assert len(orders) == 1 and orders[0]["changing"] is True
    estimate = portal.home(worker, _day(1)[:7])["estimate"]
    assert estimate["work_days"] == 0  # テストは正式合計と分離
    assert estimate["test"]["work_days"] == sum(_day(i)[:7] == _day(1)[:7] for i in (3, 4))
    old_delivery = db_session.get(OrderRequestDelivery, old["deliveries"][0]["id"])
    assert ws.pdf_viewable(db_session, old_delivery) is False
    snapshot = db_session.get(OrderRequestVersion, old["id"]).snapshot_json
    state_id = old_delivery.current_participation_state_id
    assert repair(db_session)["stale_schedule_entries"] == 2
    assert repair(db_session, apply=True)["schedule_entries_removed"] == 2
    assert repair(db_session, apply=True)["schedule_entries_removed"] == 0
    # 受諾/PDF/送付時氏名は保存し、有効な改訂への確認を勝手に代行しない。
    assert old_delivery.ack_status == "acked" and old_delivery.current_participation_state_id == state_id
    assert old_delivery.worker_name_snapshot == "高橋 直樹"
    assert db_session.get(OrderRequestVersion, old["id"]).snapshot_json == snapshot
    assert ws.get_application(db_session, db_session.get(OrderRequestVersion, old["id"]).series_id, worker.id).applied_version_id == old["id"]
    assert ws.get_application(db_session, db_session.get(OrderRequestVersion, current["id"]).series_id, worker.id).applied_version_id == current["id"]
    assert {e.status for e in db_session.query(WorkerScheduleEntry).filter_by(document_id=doc.id)} == {"cancelled"}
    assert {e.status for e in db_session.query(WorkerScheduleEntry).filter_by(document_id=current["document_id"])} == {"changing"}

    audits = db_session.query(AuditLog).filter_by(action="archived_demo_schedules_repaired").all()
    assert len(audits) == 1 and len(audits[0].target_id) <= 26
