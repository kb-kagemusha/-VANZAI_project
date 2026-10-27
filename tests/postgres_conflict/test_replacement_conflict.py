"""Two separate vacancy recruitments cannot consume the same remaining parent capacity."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, time
from src.models.base import generate_ulid
from src.models.master import Worker, User
from src.models.line_daily import WorkerScheduleEntry
from src.models.line_order import LineWorkerLink
from src.models.order_request import OrderRequestVersion, OrderRequestDelivery
from src.services import order_staffing as staffing, staffing_replacement as replacement, worker_schedule as ws
from src.services.line_order import LineOrderService
from src.services.order_request_service import OrderRequestError
from tests.postgres_conflict.test_staffing_conflict import seed
from tests.test_line_daily import _day


def test_separate_replacement_rounds_share_parent_limit(conflict_engine,monkeypatch,tmp_path):
    sessions,actor,original,versions=seed(conflict_engine,monkeypatch,tmp_path)
    requests=[]
    with sessions() as db:
        user=db.get(User,actor.id)
        root=db.get(OrderRequestVersion,versions[0])
        staffing.save_limits(db,root.id,{_day(1):3},1,user)
        staffing.decide(db,root.id,{_day(1):original},[],"",2,user)
        db.commit()
        for i,wid in enumerate(original):
            entry=db.query(WorkerScheduleEntry).filter_by(worker_id=wid,series_id=root.series_id,status="active").one()
            vacancy=replacement.create(db,entry.id,replacement.preview(db,entry.id)["guard"],"競合試験の欠員",user)
            worker=Worker(id=generate_ulid(),name="代替競合試験",is_active=True)
            db.add(worker);db.flush()
            db.add(LineWorkerLink(id=generate_ulid(),worker_id=worker.id,line_user_id="U"+generate_ulid(),status="active",linked_at=ws.now_utc()))
            db.flush()
            result=replacement.recruit(db,vacancy["id"],[worker.id],datetime.combine(entry.work_date,time(8),tzinfo=ws.JST),0,user)
            version_id=result["recruitment_version_id"]
            delivery=db.query(OrderRequestDelivery).filter_by(version_id=version_id).one()
            LineOrderService(db).accept_delivery(delivery,None,actor="local-test")
            db.commit()
            requests.append((version_id,worker.id))
        current=staffing.read(db,root.id)
        staffing.save_limits(db,root.id,{_day(1):1},current["revision"],user)
        db.commit()
    barrier=Barrier(2)
    def select(choice):
        with sessions() as db:
            barrier.wait(timeout=10)
            try:
                staffing.decide(db,choice[0],{_day(1):[choice[1]]},[],"",0,actor)
                db.commit(); return "ok"
            except OrderRequestError as exc:
                db.rollback();return str(exc.status_code)
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(select,requests))
    assert sorted(result) == ["409","ok"]
