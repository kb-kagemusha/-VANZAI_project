"""Formal drafts preserve test history and require new real masters; never send."""
from datetime import date,timedelta
from decimal import Decimal
import pytest
from src.models.order_formalization import OrderFormalization
from src.models.order_request import OrderRequestDocument,OrderRequestVersion,OrderRequestDelivery
from src.models.line_daily import WorkerScheduleEntry
from src.models.order_billing import OrderBillingAmount
from src.models.order_billing_daily import OrderBillingRateSetting
from src.services import order_staffing as staffing,worker_schedule as ws
from src.services.line_order import LineOrderService
from tests.test_api_order_requests import ops_user,pdf_root,worker_user,_auth,_worker  # noqa:F401
from tests.test_order_billing import admin_user  # noqa:F401
from tests.test_line_daily import _payload,_revise_confirm


@pytest.fixture
def source(api_client,db_session,ops_user,client,pdf_root):
    sample=_worker(db_session,"テスト時の候補")
    real=_worker(db_session,"正式な候補")
    payload=_payload([sample.id],kind="test")
    payload.update(internal_source={"client_id":client.id},requires_operator_confirmation=True)
    created=api_client.post('/api/order-requests',headers=_auth(ops_user.username),json=payload).json()
    confirmed=api_client.post(f"/api/order-requests/versions/{created['id']}/confirm",headers=_auth(ops_user.username))
    assert confirmed.status_code == 200,confirmed.text
    version=db_session.get(OrderRequestVersion,created['id'])
    capacities={d["work_date"]:2 for d in ws.version_work_days(version)}
    staffing.save_limits(db_session,version.id,capacities,0,ops_user)
    delivery=db_session.query(OrderRequestDelivery).filter_by(version_id=version.id).one()
    LineOrderService(db_session).accept_delivery(delivery,None,actor="local-test")
    db_session.commit()
    return version.id,sample.id,real.id,capacities


def plan(api,user,version):
    result=api.get(f'/api/order-requests/versions/{version}/formalization',headers=_auth(user.username))
    assert result.status_code == 200,result.text
    return result.json()


def create(api,user,version,client,worker,**changes):
    value=plan(api,user,version)
    body={"source_digest":value.get('source_digest','a'*64),"internal_source":{"client_id":client.id},"worker_ids":[worker],"capacities":value.get('capacities',{}),"masters_reviewed":True,"follow_up_due_on":(ws.today_jst()+timedelta(days=1)).isoformat()}
    body.update(changes)
    return api.post(f'/api/order-requests/versions/{version}/formalization',headers=_auth(user.username),json=body)


def test_formal_draft_keeps_test_and_does_not_inherit_answers_or_send(api_client,db_session,ops_user,client,source):
    identifier,sample,real,capacities=source
    original=api_client.get(f'/api/order-requests/versions/{identifier}',headers=_auth(ops_user.username)).json()
    response=create(api_client,ops_user,identifier,client,real)
    assert response.status_code == 200,response.text
    formal=response.json()
    assert formal['kind'] == 'formal' and formal['status'] == 'draft'
    assert formal['document_id'] != original['document_id']
    assert formal['draft_worker_ids'] == [real] and formal['deliveries'] == []
    assert not formal['has_pdf'] and formal['follow_up_due_on'] == (ws.today_jst()+timedelta(days=1)).isoformat()
    assert formal['draft_recipient_absences'] == {} and formal['requires_operator_confirmation']
    assert formal['request_conditions'] == original['request_conditions']
    assert formal['formalization']['source_version_id'] == identifier
    assert db_session.query(WorkerScheduleEntry).filter_by(document_id=formal['document_id']).count() == 0
    # A separately numbered change in the same test case also reuses the formal draft.
    changed=api_client.post('/api/order-requests',headers=_auth(ops_user.username),json=_payload([sample],kind='test',based_on=identifier))
    assert changed.status_code == 200,changed.text
    assert plan(api_client,ops_user,changed.json()['id'])['existing']['formal_version_id'] == formal['id']
    assert db_session.query(OrderBillingAmount).filter_by(version_id=formal['id']).count() == 0
    after=api_client.get(f'/api/order-requests/versions/{identifier}',headers=_auth(ops_user.username)).json()
    assert after['kind'] == 'test' and after['deliveries'] == original['deliveries'] and after['has_pdf']
    assert create(api_client,ops_user,identifier,client,real).json()['id'] == formal['id']
    assert db_session.query(OrderFormalization).count() == 1
    # The normal confirmation remains a separate explicit step, with a new deadline.
    patch=api_client.patch(f"/api/order-requests/versions/{formal['id']}",headers=_auth(ops_user.username),json={"follow_up_due_on":(date.today()+timedelta(days=1)).isoformat()})
    assert patch.status_code == 200,patch.text
    confirmed=api_client.post(f"/api/order-requests/versions/{formal['id']}/confirm",headers=_auth(ops_user.username))
    assert confirmed.status_code == 200,confirmed.text
    assert all(d['send_status']=='unsent' and d['ack_status']=='unacked' for d in confirmed.json()['deliveries'])
    assert {d['date']:d['capacity'] for d in staffing.read(db_session,formal['id'])['days']} == capacities
    assert db_session.query(WorkerScheduleEntry).filter_by(document_id=formal['document_id']).count() == 0


def test_formalization_requires_master_review_and_active_candidates(api_client,db_session,ops_user,client,source):
    identifier,_,real,_=source
    assert create(api_client,ops_user,identifier,client,real,masters_reviewed=False).status_code == 422
    assert create(api_client,ops_user,identifier,client,real,worker_ids=[]).status_code == 422
    assert create(api_client,ops_user,identifier,client,real,source_digest='b'*64).status_code == 409
    from src.models.master import Worker
    db_session.get(Worker,real).is_active=False;db_session.commit()
    assert create(api_client,ops_user,identifier,client,real).status_code == 422
    assert db_session.query(OrderFormalization).count() == 0


def test_old_or_cancelled_source_and_worker_role_cannot_formalize(api_client,db_session,ops_user,client,source,worker_user):
    identifier,_,real,_=source
    user,_=worker_user
    assert api_client.get(f'/api/order-requests/versions/{identifier}/formalization',headers=_auth(user.username)).status_code == 403
    revised=_revise_confirm(api_client,ops_user,identifier)
    assert api_client.get(f'/api/order-requests/versions/{identifier}/formalization',headers=_auth(ops_user.username)).status_code == 409
    response=api_client.post(f"/api/order-requests/versions/{revised['id']}/cancel",headers=_auth(ops_user.username),json={"reason":"試験終了"})
    assert response.status_code == 200,response.text
    assert api_client.get(f"/api/order-requests/versions/{revised['id']}/formalization",headers=_auth(ops_user.username)).status_code == 409


def test_prices_only_reference_and_formal_kind_cannot_be_changed(api_client,db_session,ops_user,admin_user,client,project,source):
    identifier,_,real,_=source
    db_session.add(OrderBillingRateSetting(version_id=identifier,project_id=project.id,base_rate=Decimal('20000'),weekday_rates={'5':'25000'},revision=1,updated_by=admin_user.id,updated_at=ws.now_utc()))
    db_session.commit()
    assert plan(api_client,ops_user,identifier)['rate_reference'] is None
    assert Decimal(plan(api_client,admin_user,identifier)['rate_reference']['base_rate']) == Decimal('20000')
    formal=create(api_client,ops_user,identifier,client,real).json()
    assert db_session.get(OrderBillingRateSetting,formal['id']) is None
    response=api_client.patch(f"/api/order-requests/versions/{formal['id']}",headers=_auth(ops_user.username),json={"kind":"test"})
    assert response.status_code == 409
    assert db_session.get(OrderRequestDocument,formal['document_id']).kind == 'formal'
