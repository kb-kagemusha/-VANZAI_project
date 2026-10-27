"""Real PostgreSQL locks: last daily slot and concurrent allocation across cases."""
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from sqlalchemy.orm import sessionmaker
from src.api.jwt_auth import create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery
from src.models.order_staffing import StaffingDecision
from src.services.order_request_service import OrderRequestService, OrderRequestError
from src.services.line_order import LineOrderService
from src.services import order_staffing as staffing
from tests.test_line_daily import _payload, _schedule, _day


def seed(engine, monkeypatch, tmp_path, *, cases=1):
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        key=generate_ulid()
        user=create_user_with_hashed_password(db=db, username="staffing-"+key, email=key+"@test.example", password="local-test-password", role="ops")
        actor=SimpleNamespace(id=user.id,username=user.username,role=user.role)
        workers=[Worker(id=generate_ulid(), name="同時確定試験", is_active=True) for _ in range(2)]
        db.add_all(workers); db.flush()
        ids=[w.id for w in workers]
        versions=[]
        for i in range(cases):
            payload=_payload(ids,kind="test",schedule=_schedule(1,1),project="競合試験"+key+str(i))
            payload.update(site_id=None,site_address=None,counterparty_note=None,phone_first=False,phone_contacted_at=None,phone_note=None,tracker_user_id=None,requires_operator_confirmation=True)
            payload["follow_up_due_on"]=date.fromisoformat(payload["follow_up_due_on"])
            service=OrderRequestService(db)
            version=service.create_draft(actor=user,**payload)
            service.confirm(version,actor=user)
            for delivery in db.query(OrderRequestDelivery).filter_by(version_id=version.id):
                LineOrderService(db).accept_delivery(delivery,None,actor="local-test")
            staffing.save_limits(db,version.id,{_day(1):1},0,user)
            versions.append(version.id)
        db.commit()
    return sessions,actor,ids,versions


def race(sessions, actor, choices):
    barrier=Barrier(2)
    def submit(choice):
        version,worker=choice
        with sessions() as db:
            barrier.wait(timeout=10)
            try:
                staffing.decide(db,version,{_day(1):[worker]},[],"",1,actor)
                db.commit()
                return "ok"
            except OrderRequestError as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(submit,choices))
    assert sorted(map(str,result)) == ["409","ok"]


def test_last_daily_slot_has_only_one_winner(conflict_engine,monkeypatch,tmp_path):
    sessions,actor,workers,versions=seed(conflict_engine,monkeypatch,tmp_path)
    race(sessions,actor,[(versions[0],w) for w in workers])
    with sessions() as db:
        assert db.query(StaffingDecision).filter_by(version_id=versions[0],status="confirmed").count() == 1


def test_same_worker_cannot_be_selected_for_two_cases_simultaneously(conflict_engine,monkeypatch,tmp_path):
    sessions,actor,workers,versions=seed(conflict_engine,monkeypatch,tmp_path,cases=2)
    race(sessions,actor,[(v,workers[0]) for v in versions])
    with sessions() as db:
        assert db.query(StaffingDecision).filter(StaffingDecision.version_id.in_(versions),StaffingDecision.status == "confirmed").count() == 1
