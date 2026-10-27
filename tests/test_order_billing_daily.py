"""Reviewed actual headcount, weekday prices, immutable daily lines and financial boundaries."""
from datetime import date
from decimal import Decimal
import json
import pytest
from src.models.base import generate_ulid
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoice
from src.models.order_billing_daily import OrderBillingDailyLine
from src.models.transaction import Assignment, Closing
from src.services import worker_schedule as ws
from src.services.financial_guards import ensure_unallocated
from src.exceptions import ValidationException
from tests.test_order_billing import admin_user, pdf_root, generate  # noqa: F401
from tests.test_api_order_requests import _auth, _worker
from tests.test_api_billing import _create_actual, _create_import_batch

DAYS=["2026-10-22","2026-10-23","2026-10-24"]


def request_source(api,db,user,client,worker_id,*,kind="formal"):
    conditions={"format":"additional-request-v1","project_name":"日別請求イベント","schedule":{"version":1,"work_groups":[{"id":"work","date_mode":"range","from":DAYS[0],"to":DAYS[-1],"start_time":"09:00","end_time":"18:00","end_next_day":False}],"rates_follow_work":True,"rate_groups":[{"id":"pay","work_group_id":"work","date_mode":"range","from":DAYS[0],"to":DAYS[-1],"amount":"10000","unit":"day"}]}}
    response=api.post("/api/order-requests",headers=_auth(user.username),json={"kind":kind,"worker_ids":[worker_id],"internal_source":{"client_id":client.id},"request_conditions":json.dumps(conditions),"site_name":"会場","contact_name":"担当","follow_up_due_on":"2026-10-21"})
    assert response.status_code == 200,response.text
    result=api.post(f"/api/order-requests/versions/{response.json()['id']}/confirm",headers=_auth(user.username))
    assert result.status_code == 200,result.text
    return result.json()


@pytest.fixture
def setup_daily(api_client,db_session,admin_user,client,project,role,pdf_root,monkeypatch):
    monkeypatch.setattr(ws,"today_jst",lambda:date(2026,10,27))
    workers=[_worker(db_session,f"実績の方{i}") for i in range(3)]
    version=request_source(api_client,db_session,admin_user,client,workers[0].id)
    batch=_create_import_batch(db_session,project.id,"202610")
    actuals=[]
    for value,people in zip(DAYS,(workers[:2],workers,workers[2:])):
        for person in people:
            actual=_create_actual(db_session,project=project,worker=person,role_id=role.id,work_date=date.fromisoformat(value),import_batch=batch)
            actual.period_key="202610";actuals.append(actual)
    duplicate=_create_actual(db_session,project=project,worker=workers[0],role_id=role.id,work_date=date.fromisoformat(DAYS[0]),import_batch=batch)
    duplicate.period_key="202610";actuals.append(duplicate)
    cancelled=_create_actual(db_session,project=project,worker=workers[2],role_id=role.id,work_date=date.fromisoformat(DAYS[0]),import_batch=batch)
    cancelled.period_key="202610";db_session.get(Assignment,cancelled.assignment_id).status="canceled"
    db_session.commit()
    root=f"/api/order-billing/orders/{version['id']}/daily"
    settings={"project_id":project.id,"base_rate":"20000.01","weekday_rates":{"5":"25000"},"revision":0}
    response=api_client.put(root+"/rates",headers=_auth(admin_user.username),json=settings)
    assert response.status_code == 200,response.text
    return version,root,actuals,workers


def confirm(api,user,root,**changes):
    preview=api.get(root+"/preview",headers=_auth(user.username))
    assert preview.status_code == 200,preview.text
    value=preview.json()
    body={"billing_month":"202611","source_digest":value["source_digest"],"rates_revision":value["rates_revision"],"expected_revision":0}
    body.update(changes)
    return api.post(root+"/confirm",headers=_auth(user.username),json=body)


def test_weekday_prices_deduplicate_people_and_freeze_daily_lines(api_client,db_session,admin_user,client,setup_daily):
    version,root,actuals,workers=setup_daily
    preview=api_client.get(root+"/preview",headers=_auth(admin_user.username)).json()
    assert [d["quantity"] for d in preview["days"]] == [2,3,1]
    assert preview["excluded_count"] == 1
    response=confirm(api_client,admin_user,root,adjustments={DAYS[1]:{"amount":"-10000","reason":"1名の半日を確認した個別調整"}})
    assert response.status_code == 200,response.text
    assert Decimal(response.json()["amount"]) == Decimal("115000.05")
    stored=db_session.query(OrderBillingDailyLine).order_by(OrderBillingDailyLine.work_date).all()
    assert sum(line.quantity for line in stored) == 6
    assert len(next(w for w in stored[0].source_snapshot["workers"] if w["worker_id"] == workers[0].id)["actual_ids"]) == 2
    invoice=generate(api_client,admin_user,client)
    assert invoice.status_code == 200,invoice.text
    assert Decimal(invoice.json()["subtotal"]) == Decimal("115000.05")
    assert Decimal(invoice.json()["tax_amount"]) == Decimal("11500")


def test_changed_actuals_invalidate_preview_and_unissued_amount(api_client,db_session,admin_user,setup_daily):
    version,root,actuals,_=setup_daily
    old=api_client.get(root+"/preview",headers=_auth(admin_user.username)).json()
    actuals[0].notes="実績を訂正";db_session.commit()
    response=api_client.post(root+"/confirm",headers=_auth(admin_user.username),json={"billing_month":"202611","source_digest":old["source_digest"],"rates_revision":1,"expected_revision":0})
    assert response.status_code == 409
    assert confirm(api_client,admin_user,root).status_code == 200
    actuals[0].status="invalid";db_session.commit()
    rows=api_client.get("/api/order-billing/orders?status=all",headers=_auth(admin_user.username)).json()["items"]
    assert rows[0]["pricing_stale"] and not rows[0]["billing_ready"]
    assert db_session.query(OrderBillingAmount).one().amount == Decimal("125000.05")


def test_issued_amount_pdf_and_days_do_not_change_with_live_actuals(api_client,db_session,admin_user,client,setup_daily):
    version,root,actuals,_=setup_daily
    assert confirm(api_client,admin_user,root).status_code == 200
    invoice=generate(api_client,admin_user,client).json()
    issued=api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue",headers=_auth(admin_user.username))
    assert issued.status_code == 200,issued.text
    pdf=api_client.get(f"/api/order-billing/invoices/{invoice['id']}/pdf",headers=_auth(admin_user.username)).content
    with pytest.raises(ValidationException): ensure_unallocated(db_session,[actuals[0].id],"invoice")
    actuals[0].status="invalid";db_session.commit() # simulate an external change, not the guarded import path
    row=api_client.get("/api/order-billing/orders?status=all",headers=_auth(admin_user.username)).json()["items"][0]
    assert row["billing_ready"] and row["pricing_stale"]
    assert api_client.get(f"/api/order-billing/invoices/{invoice['id']}/pdf",headers=_auth(admin_user.username)).content == pdf
    assert db_session.get(OrderBillingInvoice,invoice["id"]).subtotal == Decimal("125000.05")
    assert sum(r.subtotal for r in db_session.query(OrderBillingDailyLine)) == Decimal("125000.05")


def test_closing_freezes_confirmed_prices_and_amount(api_client,db_session,admin_user,project,setup_daily):
    version,root,actuals,_=setup_daily
    assert confirm(api_client,admin_user,root).status_code == 200
    db_session.add(Closing(id=generate_ulid(),project_id=project.id,period_key="202610",status="soft_closed"));db_session.commit()
    response=api_client.put(root+"/rates",headers=_auth(admin_user.username),json={"project_id":project.id,"base_rate":"50000","weekday_rates":{},"revision":1,"reason":"変更"})
    assert response.status_code == 409
    assert confirm(api_client,admin_user,root,expected_revision=1,reason="再確認").status_code == 409
    assert db_session.query(OrderBillingAmount).count() == 1


def test_same_actual_day_cannot_be_confirmed_for_another_request(api_client,db_session,admin_user,client,project,setup_daily):
    version,root,actuals,workers=setup_daily
    assert confirm(api_client,admin_user,root).status_code == 200
    other=request_source(api_client,db_session,admin_user,client,workers[1].id)
    second=f"/api/order-billing/orders/{other['id']}/daily"
    assert api_client.put(second+"/rates",headers=_auth(admin_user.username),json={"project_id":project.id,"base_rate":"20000","weekday_rates":{},"revision":0}).status_code == 200
    response=confirm(api_client,admin_user,second)
    assert response.status_code == 409 and "二重" in response.json()["detail"]


def test_operator_cannot_access_customer_daily_prices(api_client,db_session,setup_daily):
    from src.api.jwt_auth import create_user_with_hashed_password
    version,root,_,_=setup_daily
    user=create_user_with_hashed_password(db_session,"ops-daily","ops-daily@test.example","test-password","ops")
    db_session.commit()
    assert api_client.get(root,headers=_auth(user.username)).status_code == 403
    assert api_client.get(root+"/preview",headers=_auth(user.username)).status_code == 403


def test_zero_day_and_adjustment_need_explicit_review(api_client,db_session,admin_user,setup_daily):
    _,root,actuals,_=setup_daily
    for actual in actuals:
        if actual.work_date.isoformat() == DAYS[-1]: actual.status="invalid"
    db_session.commit()
    assert confirm(api_client,admin_user,root).status_code == 422
    assert confirm(api_client,admin_user,root,confirm_zero_days=True).status_code == 422
    assert confirm(api_client,admin_user,root,confirm_zero_days=True,reason="最終日は無稼働を確認",adjustments={DAYS[0]:{"amount":"-1000","reason":""}}).status_code == 422
    response=confirm(api_client,admin_user,root,confirm_zero_days=True,reason="最終日は無稼働を確認")
    assert response.status_code == 200,response.text
    assert Decimal(response.json()["amount"]) == Decimal("100000.05")


def test_changing_source_releases_old_claims_without_rewriting_old_snapshot(api_client,db_session,admin_user,client,project,setup_daily):
    from src.models.transaction import Project
    from src.models.order_billing_daily import OrderBillingActualClaim
    version,root,actuals,workers=setup_daily
    first=confirm(api_client,admin_user,root).json()
    other_project=Project(id=generate_ulid(),client_id=client.id,name="正しい実績案件")
    db_session.add(other_project);db_session.commit()
    response=api_client.put(root+"/rates",headers=_auth(admin_user.username),json={"project_id":other_project.id,"base_rate":"20000","weekday_rates":{},"revision":1,"reason":"実績案件の選択を訂正"})
    assert response.status_code == 200,response.text
    response=confirm(api_client,admin_user,root,expected_revision=1,confirm_zero_days=True,reason="訂正先の無稼働を確認")
    assert response.status_code == 200,response.text
    from src.models.order_request import OrderRequestVersion
    series_id=db_session.get(OrderRequestVersion,version["id"]).series_id
    assert not db_session.query(OrderBillingActualClaim).filter_by(series_id=series_id,active=True).count()
    assert db_session.get(OrderBillingAmount,first["id"]).amount == Decimal("125000.05")
    other=request_source(api_client,db_session,admin_user,client,workers[1].id)
    second=f"/api/order-billing/orders/{other['id']}/daily"
    assert api_client.put(second+"/rates",headers=_auth(admin_user.username),json={"project_id":project.id,"base_rate":"20000","weekday_rates":{},"revision":0}).status_code == 200
    assert confirm(api_client,admin_user,second).status_code == 200


def test_stale_invoice_draft_cannot_be_issued(api_client,db_session,admin_user,client,setup_daily):
    _,root,actuals,_=setup_daily
    assert confirm(api_client,admin_user,root).status_code == 200
    invoice=generate(api_client,admin_user,client).json()
    actuals[-1].status="invalid";db_session.commit()
    response=api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue",headers=_auth(admin_user.username))
    assert response.status_code == 409,response.text
    assert db_session.get(OrderBillingInvoice,invoice["id"]).status == "draft"
