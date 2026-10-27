"""Missing day only, no assumed worker replies, explicit invitation, same-case totals."""
from datetime import datetime, time, timedelta
import pytest
from src.models.line_daily import WorkerScheduleEntry, WakeContactLog
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.models.staffing_replacement import StaffingVacancy, StaffingRecruitment
from src.services import worker_schedule as ws, staffing_replacement as replacements, order_staffing
from src.services.line_order import LineOrderService
from src.services.participation_calendar import build
from tests.test_api_line_order_requests import _worker, _link, _auth, ops_user, pdf_root, line_env, fake_line  # noqa: F401
from tests.test_line_daily import _create_confirm, _schedule, _day
from tests.test_line_operator_portal import operator, session as operator_session  # noqa: F401


def source(api,db,actor,*,kind="formal"):
    worker=_worker(db,"欠員元の方")
    version=_create_confirm(api,actor,[worker.id],kind=kind,schedule=_schedule(1,2))
    delivery=db.query(OrderRequestDelivery).filter_by(version_id=version["id"]).one()
    LineOrderService(db).accept_delivery(delivery,None,actor="test")
    db.commit()
    entry=db.query(WorkerScheduleEntry).filter_by(worker_id=worker.id,work_date=datetime.fromisoformat(_day(1)).date(),status="active").one()
    return worker,version,entry


def test_one_missing_day_is_excluded_without_changing_answer_or_other_day(api_client,db_session,ops_user,pdf_root):
    worker,version,entry=source(api_client,db_session,ops_user)
    preview=replacements.preview(db_session,entry.id)
    result=replacements.create(db_session,entry.id,preview["guard"],"欠勤を確認",ops_user)
    db_session.commit()
    rows=db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).order_by(WorkerScheduleEntry.work_date).all()
    assert [r.status for r in rows] == ["cancelled","active"]
    assert rows[0].status_reason == "staffing_vacancy"
    delivery=db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"]).one()
    assert set(ws.current_state(db_session,delivery).dates) == {_day(1),_day(2)}
    event=build(db_session,series_id=entry.series_id)[0]["events"][0]
    assert not event["ok"] and len(event["unavailable"]) == 1 and event["vacancies"][0]["id"] == result["id"]
    restored=replacements.cancel(db_session,result["id"],"本人と確認し復帰",0,ops_user)
    db_session.commit()
    assert restored["status"] == "cancelled"
    assert db_session.get(WorkerScheduleEntry,entry.id).status == "active"


def test_replacement_reply_stays_pending_until_selected_and_joins_original_case(api_client,db_session,ops_user,pdf_root,line_env,fake_line):
    original,version,entry=source(api_client,db_session,ops_user)
    candidates=[_worker(db_session,f"代替候補{i}") for i in range(3)]
    for i,w in enumerate(candidates): _link(api_client,ops_user,w.id,f"Ureplacement{i}",event_id=f"repl-link-{i}")
    item=replacements.create(db_session,entry.id,replacements.preview(db_session,entry.id)["guard"],"欠員",ops_user)
    deadline=datetime.combine(entry.work_date,time(8,0),tzinfo=ws.JST)
    item=replacements.recruit(db_session,item["id"],[w.id for w in candidates],deadline,0,ops_user)
    db_session.commit()
    assert item["status"] == "recruiting" and not fake_line.pushes
    campaign_version=db_session.get(OrderRequestVersion,item["recruitment_version_id"])
    assert {d["work_date"] for d in ws.version_work_days(campaign_version)} == {_day(1)}
    assert all(d.ack_status == "unacked" for d in db_session.query(OrderRequestDelivery).filter_by(version_id=campaign_version.id))
    sent=replacements.send(db_session,item["id"],campaign_version.id,1,ops_user)
    db_session.commit()
    assert sent["sent"] == 3 and len(fake_line.pushes) == 3
    assert "人数調整で見送り" in fake_line.pushes[0][1][0]["text"]
    for w in candidates:
        delivery=db_session.query(OrderRequestDelivery).filter_by(version_id=campaign_version.id,worker_id=w.id).one()
        LineOrderService(db_session).accept_delivery(delivery,None,actor="test")
    db_session.commit()
    event=build(db_session,series_id=entry.series_id)[0]["events"][0]
    assert len(event["pending"]) == 3 and not event["ok"]
    order_staffing.decide(db_session,campaign_version.id,{_day(1):[candidates[0].id]},[],"",0,ops_user)
    db_session.commit()
    assert replacements.detail(db_session,item["id"])["status"] == "filled"
    event=build(db_session,series_id=entry.series_id)[0]["events"][0]
    assert [p["worker_id"] for p in event["ok"]] == [candidates[0].id]
    assert original.id not in [p["worker_id"] for p in event["ok"]]
    assert event["replacement_version_ids"] == [campaign_version.id]
    from src.services.order_billing import OrderBillingService
    assert campaign_version.id not in {v.id for v,d in OrderBillingService(db_session).eligible()}


def test_past_start_is_blocked_and_test_absence_keeps_context(api_client,db_session,ops_user,pdf_root,monkeypatch):
    worker,version,entry=source(api_client,db_session,ops_user,kind="test")
    preview=replacements.preview(db_session,entry.id)
    item=replacements.create(db_session,entry.id,preview["guard"],"テスト欠員",ops_user)
    db_session.commit()
    assert db_session.query(WakeContactLog).one().is_test is True
    replacements.cancel(db_session,item["id"],"確認用の復帰",0,ops_user); db_session.commit()
    monkeypatch.setattr(ws,"now_utc",lambda:datetime.combine(entry.work_date,time(23),tzinfo=ws.JST))
    with pytest.raises(Exception,match="勤務開始後"):
        replacements.preview(db_session,entry.id)


def test_line_operator_uses_same_actions_and_rechecks_revoked_write_permission(api_client,db_session,ops_user,pdf_root,operator):
    from src.models.access_policy import RoleAccessPolicy
    worker,version,entry=source(api_client,db_session,ops_user)
    headers=operator_session(api_client)
    endpoint="/api/line/operator/staffing-replacements"
    preview=api_client.get(f"{endpoint}/entries/{entry.id}",headers=headers)
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    policy=RoleAccessPolicy(role="ops",display_name="運営",permissions=["order_read","wake_status_read"])
    db_session.add(policy); db_session.commit()
    body={"entry_id":entry.id,"guard":preview.json()["guard"],"reason":"欠勤を確認"}
    assert api_client.post(endpoint,json=body,headers=headers).status_code == 403
    assert db_session.query(StaffingVacancy).count() == 0
    assert api_client.post("/api/order-requests",json={"worker_ids":[worker.id]},headers=_auth(ops_user.username)).status_code == 403
    policy.permissions=["order_read","order_write","wake_status_read"]; db_session.commit()
    created=api_client.post(endpoint,json=body,headers=headers)
    assert created.status_code == 200,created.text
    assert created.json()["status"] == "open"
    # A management JWT never becomes a LINE operator session.
    assert api_client.get(endpoint+f"?date={_day(1)}",headers=_auth(ops_user.username)).status_code == 401


def test_recruitment_does_not_send_when_test_switch_is_off(api_client,db_session,ops_user,pdf_root,line_env,fake_line):
    worker,version,entry=source(api_client,db_session,ops_user,kind="test")
    candidate=_worker(db_session,"候補者")
    _link(api_client,ops_user,candidate.id,"Utest-replacement")
    item=replacements.create(db_session,entry.id,replacements.preview(db_session,entry.id)["guard"],"欠員の確認",ops_user)
    item=replacements.recruit(db_session,item["id"],[candidate.id],datetime.combine(entry.work_date,time(8),tzinfo=ws.JST),0,ops_user)
    db_session.commit()
    assert replacements.invitation_preview(db_session,item["id"])["notifications_enabled"] is False
    result=replacements.send(db_session,item["id"],item["recruitment_version_id"],1,ops_user)
    assert result["sent"] == 0 and not fake_line.pushes


def test_parent_cancel_stops_related_recruitment_and_preserves_history(api_client,db_session,ops_user,pdf_root,line_env,fake_line):
    from src.services.order_request_service import OrderRequestService
    worker,version,entry=source(api_client,db_session,ops_user)
    candidate=_worker(db_session,"代替者")
    _link(api_client,ops_user,candidate.id,"Ucancel-related")
    item=replacements.create(db_session,entry.id,replacements.preview(db_session,entry.id)["guard"],"欠員",ops_user)
    item=replacements.recruit(db_session,item["id"],[candidate.id],datetime.combine(entry.work_date,time(8),tzinfo=ws.JST),0,ops_user)
    child=db_session.get(OrderRequestVersion,item["recruitment_version_id"])
    delivery=db_session.query(OrderRequestDelivery).filter_by(version_id=child.id).one()
    LineOrderService(db_session).accept_delivery(delivery,None,actor="test")
    order_staffing.decide(db_session,child.id,{_day(1):[candidate.id]},[],"",0,ops_user)
    db_session.commit()
    OrderRequestService(db_session).cancel(db_session.get(OrderRequestVersion,version["id"]),actor=ops_user,reason="案件の中止")
    db_session.commit()
    assert db_session.get(OrderRequestVersion,child.id).status == "cancelled"
    assert not replacements.detail(db_session,item["id"])["source_active"]
    assert db_session.query(WorkerScheduleEntry).filter_by(worker_id=candidate.id,status="active").count() == 0
    assert db_session.query(StaffingVacancy).count() == 1
