"""Two request series cannot bill the same actual project/day concurrently."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from sqlalchemy.orm import sessionmaker
from src.api.jwt_auth import create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.master import Client, Worker, Role
from src.models.transaction import Project
from src.models.order_billing_daily import OrderBillingActualClaim
from src.services.order_request_service import OrderRequestService, OrderRequestError
from src.services import order_billing_daily as daily, worker_schedule as ws
from tests.test_api_billing import _create_actual, _create_import_batch
from tests.test_line_daily import _payload, _schedule


def test_daily_claim_has_one_winner(conflict_engine,monkeypatch,tmp_path):
    monkeypatch.setenv("PDF_STORAGE_ROOT",str(tmp_path))
    monkeypatch.setattr(ws,"today_jst",lambda:date(2026,10,27))
    sessions=sessionmaker(bind=conflict_engine)
    with sessions() as db:
        key=generate_ulid()
        user=create_user_with_hashed_password(db,"daily-"+key,key+"@test.example","test-password","admin")
        client=Client(id=generate_ulid(),name="日別請求競合"+key)
        worker=Worker(id=generate_ulid(),name="実績人数",is_active=True)
        role=Role(id=generate_ulid(),name="競合試験",code=key)
        db.add_all([client,worker,role]);db.flush()
        project=Project(id=generate_ulid(),name="実績案件",client_id=client.id)
        db.add(project);db.flush()
        batch=_create_import_batch(db,project.id,"202610")
        actual=_create_actual(db,project=project,worker=worker,role_id=role.id,work_date=date(2026,10,26),import_batch=batch)
        actual.period_key="202610"
        versions=[]
        for i in range(2):
            payload=_payload([worker.id],schedule=_schedule(-1,-1))
            payload.update(site_id=None,site_address=None,counterparty_note=None,phone_first=False,phone_contacted_at=None,phone_note=None,tracker_user_id=None,internal_source={"client_id":client.id},internal_source_set=True)
            payload["follow_up_due_on"]=date.fromisoformat(payload["follow_up_due_on"])
            version=OrderRequestService(db).create_draft(actor=user,**payload)
            OrderRequestService(db).confirm(version,actor=user)
            daily.save_setting(db,version.id,project.id,Decimal("20000"),{},0,"",user)
            versions.append((version.id,daily.preview(db,version.id)["source_digest"]))
        actor=SimpleNamespace(id=user.id,username=user.username,role=user.role)
        project_id=project.id;db.commit()
    barrier=Barrier(2)
    def submit(item):
        with sessions() as db:
            barrier.wait(timeout=10)
            try:
                daily.confirm(db,item[0],billing_month="202611",source_digest=item[1],rates_revision=1,expected_revision=0,adjustments={},confirm_zero_days=False,reason="確認済み",incentive_amount=None,actor=actor)
                db.commit();return "ok"
            except OrderRequestError as exc:
                db.rollback();return str(exc.status_code)
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(submit,versions))
    assert sorted(result) == ["409","ok"]
    with sessions() as db:
        assert db.query(OrderBillingActualClaim).filter_by(project_id=project_id,active=True).count() == 1
