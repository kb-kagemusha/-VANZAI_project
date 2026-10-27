from datetime import datetime, timedelta, timezone
import pytest
from src.models.line_daily import OrderRequestApplicationEnd, WorkerScheduleEntry
from src.models.order_request import OrderRequestVersion
from src.services import worker_schedule as ws
from src.services.participation_calendar import build
from tests.test_line_daily import _worker, _link, _auth, _create_confirm, _revise_confirm, _schedule, _send_and_accept, ops_user, pdf_root, line_env, fake_line


@pytest.mark.parametrize("ending,reason", [("cancel","document_ended"),("remove","removed_from_recipients")])
@pytest.mark.parametrize("hour,minute,kept_offsets", [(8,59,[1]),(9,0,[1,2]),(18,0,[1,2])])
def test_endings_keep_started_days_and_rebuild_without_schedule_rows(api_client, db_session, ops_user, pdf_root, line_env, fake_line, monkeypatch, ending, reason, hour, minute, kept_offsets):
    base = ws.today_jst()
    dates = [(base+timedelta(days=i)).isoformat() for i in (1,2,3)]
    worker, other = _worker(db_session,"参加者"), _worker(db_session,"別の参加者")
    _link(api_client, ops_user, worker.id,"U123")
    v1 = _create_confirm(api_client, ops_user, [worker.id,other.id], schedule=_schedule(1,3))
    first = next(d for d in v1["deliveries"] if d["worker_id"] == worker.id)
    _send_and_accept(api_client,ops_user,first["id"])
    version = db_session.get(OrderRequestVersion,v1["id"])
    original_snapshot, pdf = version.snapshot_json, version.pdf_object_key
    moment = datetime.combine(base+timedelta(days=2),datetime.min.time(),tzinfo=ws.JST).replace(hour=hour,minute=minute)
    monkeypatch.setattr(ws,"now_utc",lambda:moment.astimezone(timezone.utc))
    if ending == "cancel":
        response = api_client.post(f"/api/order-requests/versions/{v1['id']}/cancel",json={"reason":"中止"},headers=_auth(ops_user.username))
        assert response.status_code == 200,response.text
    else:
        _revise_confirm(api_client,ops_user,v1["id"],worker_ids=[other.id])
    db_session.expire_all()
    history = db_session.query(OrderRequestApplicationEnd).filter_by(worker_id=worker.id).one()
    kept = [(base+timedelta(days=i)).isoformat() for i in kept_offsets]
    assert history.retained_dates == kept and history.accepted_dates == dates
    assert history.ended_reason == reason and history.source_delivery_id == first["id"]
    app = ws.get_application(db_session,version.series_id,worker.id)
    assert app.applied_delivery_id is None and app.ended_reason == reason
    rows = db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).all()
    assert {r.work_date.isoformat() for r in rows if r.status == "active"} == set(kept)
    assert {r.status_reason for r in rows if r.status == "cancelled"} == {reason}
    # 派生行を失っても、終了時に残すと決めた日だけを原資料から再生成できる。
    db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).delete(synchronize_session=False)
    db_session.flush()
    later = moment + timedelta(days=10)
    monkeypatch.setattr(ws,"now_utc",lambda:later.astimezone(timezone.utc))
    for _ in range(2):
        ws.rebuild(db_session,version.series_id,worker.id,actor="test")
    rows = db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).all()
    assert {r.work_date.isoformat() for r in rows} == set(kept)
    assert {r.status for r in rows} == {"active"}
    calendar = build(db_session,series_id=version.series_id)
    actual = {d["date"] for d in calendar for e in d["events"] for p in e["ok"] if p["worker_id"] == worker.id}
    assert actual == set(kept)
    assert not any(p["worker_id"] == worker.id for d in calendar for e in d["events"] for p in e["changing"])
    assert version.snapshot_json == original_snapshot and version.pdf_object_key == pdf
    assert db_session.query(OrderRequestApplicationEnd).filter_by(worker_id=worker.id).count() == 1


def test_application_end_migration_is_empty_and_downgrade_preserves_history():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text, inspect
    file=Path(__file__).resolve().parents[1]/"alembic/versions/20261024c001_application_end_history.py"
    spec=importlib.util.spec_from_file_location("end_history_migration",file)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)): migration.upgrade()
        assert connection.execute(text("SELECT count(*) FROM order_request_application_ends")).scalar() == 0
        assert len(inspect(connection).get_foreign_keys("order_request_application_ends")) == 5
        with Operations.context(MigrationContext.configure(connection)): migration.downgrade()
        assert "order_request_application_ends" not in inspect(connection).get_table_names()
    engine.dispose()


def test_removed_then_added_back_does_not_duplicate_frozen_days(api_client,db_session,ops_user,pdf_root,line_env,fake_line,monkeypatch):
    base=ws.today_jst()
    worker,other=_worker(db_session,"再参加"),_worker(db_session,"別の参加者")
    _link(api_client,ops_user,worker.id,"U123")
    first=_create_confirm(api_client,ops_user,[worker.id,other.id],schedule=_schedule(1,3))
    old=next(d for d in first["deliveries"] if d["worker_id"]==worker.id)
    _send_and_accept(api_client,ops_user,old["id"])
    moment=datetime.combine(base+timedelta(days=2),datetime.min.time(),tzinfo=ws.JST).replace(hour=8)
    monkeypatch.setattr(ws,"now_utc",lambda:moment.astimezone(timezone.utc))
    removed=_revise_confirm(api_client,ops_user,first["id"],worker_ids=[other.id])
    added=_revise_confirm(api_client,ops_user,removed["id"],worker_ids=[worker.id,other.id])
    mine=next(d for d in added["deliveries"] if d["worker_id"]==worker.id)
    _send_and_accept(api_client,ops_user,mine["id"])
    rows=db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id,status="active").all()
    assert len(rows)==3 and len({r.work_date for r in rows})==3
    day1=(base+timedelta(days=1)).isoformat()
    assert next(r for r in rows if r.work_date.isoformat()==day1).version_id==first["id"]
    future_old=db_session.query(WorkerScheduleEntry).filter_by(delivery_id=old["id"],status="cancelled").all()
    assert len(future_old)==2 and {r.status_reason for r in future_old}=={"removed_from_recipients"}
