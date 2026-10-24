from datetime import datetime, timezone
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion, OrderRequestDocument
from src.services import worker_schedule as ws
from tests.test_line_daily import _create_confirm, _revise_confirm
from tests.test_api_line_order_requests import _worker, _link, _auth, ops_user, pdf_root, line_env, fake_line  # noqa: F401


def accepted_change(api_client, db, ops_user, *, kind="formal"):
    worker = _worker(db, "旧版の受諾者")
    first = _create_confirm(api_client, ops_user, [worker.id], kind=kind)
    old = db.get(OrderRequestDelivery, first["deliveries"][0]["id"])
    old.send_status, old.ack_status = "unknown", "acked"
    ws.append_state(db, old, dates=old.offered_dates, source="full_accept", actor=ops_user.username)
    ws.set_application(db, series_id=db.get(OrderRequestVersion, old.version_id).series_id, worker_id=worker.id, delivery=old, ended_reason=None, actor=ops_user.username)
    db.commit()
    latest = _revise_confirm(api_client, ops_user, first["id"])
    return worker, latest


def test_change_waiting_visible_until_sent_and_rechecks_before_send(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, latest = accepted_change(api_client, db_session, ops_user)
    auth = _auth(ops_user.username)
    url = "/api/order-requests/change-delivery-pending"
    result = api_client.get(url, headers=auth).json()
    assert result["total"] == result["pending_people"] == 1
    row = result["items"][0]["recipients"][0]
    assert row["worker_name"] == worker.name and row["send_status"] == "unsent" and not row["can_send"]
    send = url + "/" + row["delivery_id"] + "/send"
    assert api_client.post(send, headers=auth).status_code == 409  # 未連携は送らない
    _link(api_client, ops_user, worker.id, "U123")
    assert api_client.post(send, headers=auth).json()["send_status"] == "accepted"
    assert api_client.get(url, headers=auth).json()["pending_people"] == 0
    assert api_client.post(send, headers=auth).status_code == 409  # 二度押しで再送しない
    assert len(fake_line.pushes) == 1
    assert db_session.get(OrderRequestDelivery, row["delivery_id"]).ack_status == "unacked"
    assert api_client.get(url).status_code == 401
    assert api_client.get(url+"?kind=invalid", headers=auth).status_code == 422


def test_unknown_stays_visible_but_cannot_be_resent_here(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, latest = accepted_change(api_client, db_session, ops_user)
    _link(api_client, ops_user, worker.id, "U123")
    auth = _auth(ops_user.username)
    delivery_id = latest["deliveries"][0]["id"]
    url = "/api/order-requests/change-delivery-pending"
    fake_line.push_status = 0
    assert api_client.post(f"{url}/{delivery_id}/send", headers=auth).json()["send_status"] == "unknown"
    result = api_client.get(url, headers=auth).json()
    assert result["pending_people"] == 1
    assert not result["items"][0]["recipients"][0]["can_send"]
    assert api_client.post(f"{url}/{delivery_id}/send", headers=auth).status_code == 409


def test_only_current_active_changes_paginate_and_formal_test_are_separate(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    formal_worker, formal = accepted_change(api_client, db_session, ops_user)
    _, test = accepted_change(api_client, db_session, ops_user, kind="test")
    newcomer = _worker(db_session, "新規依頼の送付先")
    _create_confirm(api_client, ops_user, [newcomer.id])
    auth = _auth(ops_user.username)
    url = "/api/order-requests/change-delivery-pending"
    assert api_client.get(url, headers=auth).json()["pending_people"] == 1
    page = api_client.get(url+"?kind=all&limit=1&offset=1", headers=auth).json()
    assert page["total"] == page["pending_people"] == 2 and len(page["items"]) == 1
    assert api_client.get(url+"?kind=test", headers=auth).json()["items"][0]["kind"] == "test"
    # 再改訂すると、旧版の送付待ちは消えて最新版だけが出る。
    newest = _revise_confirm(api_client, ops_user, formal["id"])
    result = api_client.get(url, headers=auth).json()
    assert result["total"] == 1 and result["items"][0]["version_id"] == newest["id"]
    stale = api_client.post(f"{url}/{formal['deliveries'][0]['id']}/send", headers=auth)
    assert stale.status_code == 409
    doc = db_session.get(OrderRequestDocument, newest["document_id"])
    doc.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    assert api_client.get(url, headers=auth).json()["pending_people"] == 0
