"""旧サンプルは非表示分も受諾・派生予定から取り除き、他の依頼を保持する。"""
from datetime import datetime, timezone
import pytest
from scripts.remove_legacy_samples import preview, purge
from src.models.order_request import OrderRequestVersion, OrderRequestDocument, OrderRequestDelivery
from src.models.line_daily import WorkerScheduleEntry, OrderRequestWorkerApplication
from src.services import worker_schedule as ws
from src.services.participation_calendar import build
from tests.test_api_order_requests import _worker, pdf_root  # noqa: F401
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_line_daily import _create_confirm, _schedule


def accepted(api_client, db, actor, worker, name, kind="formal"):
    result = _create_confirm(api_client, actor, [worker.id], kind=kind, project=name, schedule=_schedule(-2, 2))
    version = db.get(OrderRequestVersion, result["id"])
    delivery = db.query(OrderRequestDelivery).filter_by(version_id=version.id).one()
    delivery.send_status = "unknown"
    delivery.ack_status = "acked"
    dates = [d["work_date"] for d in ws.version_work_days(version)]
    ws.append_state(db, delivery, dates=dates, source="full_accept", actor=actor.username)
    ws.set_application(db, series_id=version.series_id, worker_id=worker.id, delivery=delivery, ended_reason=None, actor=actor.username)
    ws.rebuild_series(db, version.series_id, actor=actor.username)
    return version, delivery


def test_hidden_and_visible_samples_lose_all_current_acceptance_and_schedule(api_client, db_session, admin_user, client, pdf_root):
    worker = _worker(db_session, "確認用")
    one, delivery = accepted(api_client, db_session, admin_user, worker, "サンプルイベント1")
    two, second = accepted(api_client, db_session, admin_user, worker, "サンプルイベント２", kind="test")
    keep, other = accepted(api_client, db_session, admin_user, worker, "【テスト】11月 20日間の飲食店巡回", kind="test")
    db_session.get(OrderRequestDocument, two.document_id).deleted_at = datetime.now(timezone.utc)
    original_pdf = one.pdf_object_key
    db_session.flush()
    assert len(preview(db_session)) == 2
    assert db_session.query(WorkerScheduleEntry).filter_by(status="active").count() == 15
    result = purge(db_session)
    assert result["matched_documents"] == result["changed_documents"] == 2
    assert result["applications_removed"] == result["participation_states_cleared"] == 2
    assert result["schedule_entries_removed"] == 10 and result["active_entries_remaining"] == 0
    assert db_session.get(OrderRequestDocument, one.document_id).deleted_at is not None
    assert ws.current_state(db_session, delivery).dates == []
    assert ws.current_state(db_session, second).dates == []
    assert delivery.view_revoked is True and second.view_revoked is True
    assert one.status == two.status == "cancelled"
    assert db_session.query(OrderRequestWorkerApplication).filter_by(series_id=one.series_id).one().applied_delivery_id is None
    assert not build(db_session, series_id=one.series_id)
    assert db_session.query(WorkerScheduleEntry).filter_by(status="active").count() == 5
    assert ws.current_state(db_session, other).dates and keep.status == "confirmed"
    assert one.pdf_object_key == original_pdf
    repeat = purge(db_session)
    assert repeat["changed_documents"] == repeat["participation_states_cleared"] == repeat["applications_removed"] == repeat["schedule_entries_removed"] == 0


def test_similar_but_not_exact_sample_name_stops_cleanup(api_client, db_session, admin_user, client, pdf_root):
    worker = _worker(db_session, "確認用")
    version, delivery = accepted(api_client, db_session, admin_user, worker, "サンプルイベントを使う本番案件")
    with pytest.raises(RuntimeError, match="追加文言"):
        purge(db_session)
    assert version.status == "confirmed" and not delivery.view_revoked
    assert ws.current_state(db_session, delivery).dates
