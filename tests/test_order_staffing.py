"""Daily operator selection: pending schedules, capacity, closure, and no test pushes."""
from datetime import date, timedelta
import pytest
from src.models.order_staffing import StaffingDecision, StaffingNotice
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.models.line_daily import WorkerScheduleEntry, WakeTestNotificationSetting
from src.services import order_staffing as staffing, worker_schedule as ws
from src.services.line_order import LineOrderService
from src.services.line_messaging import LineCallResult
from tests.test_api_line_order_requests import _auth, _worker, _link, ops_user, pdf_root, line_env, fake_line  # noqa: F401
from tests.test_line_daily import _payload, _schedule, _day


def create(api, actor, workers, *, kind="formal"):
    body = _payload([w.id for w in workers], kind=kind, schedule=_schedule(1, 2))
    body["requires_operator_confirmation"] = True
    headers = _auth(actor.username)
    result = api.post("/api/order-requests", json=body, headers=headers)
    assert result.status_code == 200, result.text
    result = api.post(f"/api/order-requests/versions/{result.json()['id']}/confirm", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def accept(db, version, workers):
    service = LineOrderService(db)
    # The test models an invitation already delivered to all recipients.
    for delivery in db.query(OrderRequestDelivery).filter_by(version_id=version["id"]):
        delivery.send_status = "accepted"
    for worker in workers:
        delivery = db.query(OrderRequestDelivery).filter_by(version_id=version["id"], worker_id=worker.id).one()
        outcome, reply = service.accept_delivery(delivery, None, actor="test-reply")
        assert outcome == "acked" and "結果連絡" in reply
    db.commit()


def test_pending_then_daily_selection_and_stale_write(api_client, db_session, ops_user, pdf_root):
    workers = [_worker(db_session, f"候補{i}") for i in range(3)]
    version = create(api_client, ops_user, workers)
    accept(db_session, version, workers)
    rows = db_session.query(WorkerScheduleEntry).all()
    assert len(rows) == 6 and all(r.status == "pending" for r in rows)
    from src.services.line_worker_portal import estimate_for
    assert estimate_for(db_session, rows)["work_days"] == 0
    from src.services.participation_calendar import build
    event = build(db_session, series_id=db_session.get(OrderRequestVersion,version["id"]).series_id)[0]["events"][0]
    assert not event["ok"] and len(event["pending"]) == 3
    capacities = {_day(1): 1, _day(2): 2}
    staffing.save_limits(db_session,version["id"],capacities,0,ops_user); db_session.commit()
    too_many = api_client.post(f"/api/order-staffing/{version['id']}/decisions", json={"revision":1,"selected":{_day(1):[w.id for w in workers[:2]]}}, headers=_auth(ops_user.username))
    assert too_many.status_code == 409
    result = staffing.decide(db_session,version["id"],{_day(1):[workers[0].id], _day(2):[workers[1].id]},[],"",1,ops_user)
    db_session.commit()
    assert result["days"][0]["closed"] and not result["days"][1]["closed"]
    assert result["days"][0]["confirmed"] == 1
    assert db_session.query(StaffingNotice).count() == 4 # 2 confirmed, 2 closure for the filled day only
    assert db_session.query(WorkerScheduleEntry).filter_by(status="active").count() == 2
    event = build(db_session,series_id=db_session.get(OrderRequestVersion,version["id"]).series_id)[0]["events"][0]
    assert len(event["ok"]) == 1 and not event["pending"]
    stale = api_client.put(f"/api/order-staffing/{version['id']}/limits",json={"revision":1,"capacities":capacities},headers=_auth(ops_user.username))
    assert stale.status_code == 409
    # Repeating the same selection cannot create result messages again.
    staffing.decide(db_session,version["id"],{_day(1):[workers[0].id]},[],"",2,ops_user)
    assert db_session.query(StaffingNotice).count() == 4


def test_closed_day_rejects_late_answer_and_decliner_gets_thanks(api_client, db_session, ops_user, pdf_root):
    workers = [_worker(db_session,f"人{i}") for i in range(3)]
    version = create(api_client,ops_user,workers)
    accept(db_session,version,workers[:1])
    service = LineOrderService(db_session)
    declined = db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"],worker_id=workers[1].id).one()
    outcome,reply = service.decline_delivery(declined,db_session.get(OrderRequestVersion,version["id"]).series_id,"予定あり",actor="test")
    assert outcome == "declined" and reply == staffing.DECLINE_THANKS
    staffing.save_limits(db_session,version["id"],{_day(1):1,_day(2):1},0,ops_user)
    staffing.decide(db_session,version["id"],{_day(1):[workers[0].id]},[],"",1,ops_user)
    db_session.commit()
    assert not db_session.query(StaffingNotice).filter_by(worker_id=workers[1].id).first()
    late = db_session.query(OrderRequestDelivery).filter_by(version_id=version["id"],worker_id=workers[2].id).one()
    outcome,reply = service.accept_delivery(late,None,actor="test")
    assert outcome == "closed" and late.ack_status == "unacked"


class Sender:
    def __init__(self,status=200): self.calls=[]; self.status=status
    def push_receipt(self,to,text,retry_key):
        self.calls.append((to,text,retry_key))
        return LineCallResult(self.status,"","request", "accepted" if self.status == 409 else None)


@pytest.mark.parametrize("kind",["formal","test"])
def test_durable_messages_one_per_person_and_test_off(api_client,db_session,ops_user,pdf_root,line_env,fake_line,kind):
    workers = [_worker(db_session,f"人{i}") for i in range(2)]
    for i,w in enumerate(workers): _link(api_client,ops_user,w.id,f"Ustaffing{i}",event_id=f"staffing-link-{i}")
    version = create(api_client,ops_user,workers,kind=kind)
    accept(db_session,version,workers[:1])
    staffing.save_limits(db_session,version["id"],{_day(1):1,_day(2):1},0,ops_user)
    staffing.decide(db_session,version["id"],{_day(1):[workers[0].id]},[],"",1,ops_user); db_session.commit()
    sender=Sender(0)
    staffing.dispatch_notices(db_session,version["id"],ops_user,client=sender)
    assert len(sender.calls) == (2 if kind == "formal" else 0)
    first_keys = [call[2] for call in sender.calls]
    sender.status=409
    staffing.dispatch_notices(db_session,version["id"],ops_user,client=sender,retry_failed=True)
    assert [call[2] for call in sender.calls[2:]] == first_keys
    staffing.dispatch_notices(db_session,version["id"],ops_user,client=sender,retry_failed=True)
    assert len(sender.calls) == (4 if kind == "formal" else 0)
    statuses={r.status for r in db_session.query(StaffingNotice)}
    assert statuses == ({"sent"} if kind == "formal" else {"skipped"})


def test_capacity_is_strict_integer_and_requires_write_permission(api_client,db_session,ops_user,pdf_root):
    version=create(api_client,ops_user,[_worker(db_session,"人")])
    response=api_client.put(f"/api/order-staffing/{version['id']}/limits",json={"revision":0,"capacities":{_day(1):True,_day(2):1}},headers=_auth(ops_user.username))
    assert response.status_code == 422
    assert api_client.get(f"/api/order-staffing/{version['id']}").status_code == 401


def test_closed_recruitment_never_sends_a_later_reply_reminder(api_client,db_session,ops_user,pdf_root,line_env,fake_line):
    workers=[_worker(db_session,f"候補{i}") for i in range(2)]
    version=create(api_client,ops_user,workers)
    accept(db_session,version,workers[:1])
    staffing.save_limits(db_session,version["id"],{_day(1):1,_day(2):1},0,ops_user)
    staffing.decide(db_session,version["id"],{_day(1):[workers[0].id],_day(2):[workers[0].id]},[],"",1,ops_user)
    db_session.commit()
    assert LineOrderService(db_session).send_due_reminders(now=ws.now_utc()+timedelta(days=90)) == 0
    assert not fake_line.pushes


def test_read_only_operator_cannot_set_capacity(api_client,db_session,ops_user,pdf_root):
    from src.models.access_policy import RoleAccessPolicy
    version=create(api_client,ops_user,[_worker(db_session,"候補")])
    db_session.add(RoleAccessPolicy(role="ops",display_name="運営",permissions=["order_read"]))
    db_session.commit()
    headers=_auth(ops_user.username)
    assert api_client.get(f"/api/order-staffing/{version['id']}",headers=headers).status_code == 200
    response=api_client.put(f"/api/order-staffing/{version['id']}/limits",json={"revision":0,"capacities":{_day(1):1,_day(2):1}},headers=headers)
    assert response.status_code == 403
