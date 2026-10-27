"""送信回答を文書単位でページ化し、同じ文書の送付先を欠落させない。"""
from datetime import date, datetime, timezone
from tests.test_api_order_requests import _worker, _auth, ops_user, pdf_root  # noqa: F401
from tests.test_line_daily import _create_confirm
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion, OrderRequestDocument
from src.models.master import Worker
from scripts.tag_demo_directors import apply, DEMO_DIRECTORS
from tests.test_order_billing import admin_user  # noqa: F401


def test_reply_groups_paginate_documents_and_keep_all_recipients(api_client, db_session, ops_user, pdf_root, client):
    auth = _auth(ops_user.username)
    workers = [_worker(db_session, f"送付先{i}") for i in range(8)]
    versions = []
    for kind in ("test", "formal", "test"):
        version = _create_confirm(api_client, ops_user, [w.id for w in workers], kind=kind)
        versions.append(db_session.get(OrderRequestVersion, version["id"]))
    for version in versions:
        rows = db_session.query(OrderRequestDelivery).filter_by(version_id=version.id).all()
        for i, delivery in enumerate(rows):
            delivery.send_status = "unknown"
            delivery.ack_status = ("acked", "unacked", "declined")[i % 3]
    db_session.commit()
    seen = set()
    for offset in range(3):
        response = api_client.get(f"/api/order-requests/reply-groups?limit=1&offset={offset}", headers=auth)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total"] == 3 and len(result["items"]) == 1
        group = result["items"][0]
        assert group["document_id"] not in seen
        seen.add(group["document_id"])
        assert len(group["recipients"]) == 8
        assert {p["ack_status"] for p in group["recipients"]} == {"acked", "unacked", "declined"}
        assert len({p["delivery_id"] for p in group["recipients"]}) == 8
        assert all(p["document_number"] == group["document_number"] for p in group["recipients"])
    formal = api_client.get("/api/order-requests/reply-groups?kind=formal", headers=auth).json()
    tests = api_client.get("/api/order-requests/reply-groups?kind=test", headers=auth).json()
    assert formal["total"] == 1 and tests["total"] == 2
    assert all(g["kind"] == "test" for g in tests["items"])
    # 作成済みのテストもページ全体の件数と整合し、送信一覧と同じ区分で取得できる。
    created = api_client.get("/api/order-requests?kind=test&limit=1&offset=1", headers=auth).json()
    assert created["total"] == 2 and len(created["items"]) == 1 and created["items"][0]["kind"] == "test"
    db_session.get(OrderRequestDocument, versions[0].document_id).deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    assert api_client.get("/api/order-requests/reply-groups", headers=auth).json()["total"] == 2
    assert api_client.get("/api/order-requests/reply-groups?kind=invalid", headers=auth).status_code == 400
    assert api_client.get("/api/order-requests/reply-groups?offset=-1", headers=auth).status_code == 422
    assert api_client.get("/api/order-requests/reply-groups?limit=51", headers=auth).status_code == 422
    assert api_client.get("/api/order-requests/reply-groups").status_code == 401


def test_demo_directors_are_append_only_and_repeatable(db_session, admin_user):
    workers = [_worker(db_session, name) for name in DEMO_DIRECTORS]
    for worker in workers:
        worker.tags = ["event_small_d"]
        worker.available_start_date = date(2020,1,1)
    own = _worker(db_session, "テスト アカウント")
    db_session.flush()
    assert apply(db_session)["tagged"] == 3
    db_session.expire_all()
    for worker in workers:
        assert db_session.get(Worker, worker.id).tags == ["director", "event_small_d"]
        assert db_session.get(Worker, worker.id).available_start_date == date(2020,1,1)
    assert not db_session.get(Worker, own.id).tags
    assert apply(db_session)["tagged"] == 0

def test_reply_group_uses_latest_sent_version_per_person(api_client, db_session, ops_user):
    workers = [_worker(db_session, "回答更新あり"), _worker(db_session, "旧版に回答")]
    document = OrderRequestDocument(document_number="GROUP-VERSIONS", kind="test", created_by_user_id=ops_user.id)
    db_session.add(document)
    db_session.flush()
    versions = [OrderRequestVersion(document_id=document.id, version_no=n, created_by_user_id=ops_user.id, status="confirmed") for n in (1, 2)]
    db_session.add_all(versions)
    db_session.flush()
    db_session.add_all([
        OrderRequestDelivery(version_id=versions[0].id, worker_id=workers[0].id, worker_name_snapshot=workers[0].name, send_status="accepted", ack_status="acked"),
        OrderRequestDelivery(version_id=versions[1].id, worker_id=workers[0].id, worker_name_snapshot=workers[0].name, send_status="accepted", ack_status="unacked"),
        OrderRequestDelivery(version_id=versions[0].id, worker_id=workers[1].id, worker_name_snapshot=workers[1].name, send_status="accepted", ack_status="acked"),
        OrderRequestDelivery(version_id=versions[1].id, worker_id=workers[1].id, worker_name_snapshot=workers[1].name, send_status="unsent", ack_status="unacked"),
    ])
    db_session.commit()
    response = api_client.get("/api/order-requests/reply-groups", headers=_auth(ops_user.username))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == len(result["items"]) == 1
    group = result["items"][0]
    assert group["version_no"] == 2
    people = {p["worker_name"]: p for p in group["recipients"]}
    assert len(people) == 2
    assert people[workers[0].name]["ack_status"] == "unacked" and people[workers[0].name]["version_no"] == 2
    assert people[workers[1].name]["ack_status"] == "acked" and people[workers[1].name]["version_no"] == 1

def test_reply_groups_and_detail_use_current_names_without_rewriting_snapshots(api_client, db_session, ops_user, pdf_root, client):
    workers = [_worker(db_session, f"【テスト】追加スタッフ0{i}") for i in range(1, 4)]
    result = _create_confirm(api_client, ops_user, [w.id for w in workers], kind="test")
    version = db_session.get(OrderRequestVersion, result["id"])
    original_pdf = version.pdf_object_key
    import copy
    original_snapshot = copy.deepcopy(version.snapshot_json)
    old_names = {w.id: w.name for w in workers}
    current_names = ["渡邊 健太郎", "長谷川 亜香里", "岡田 直人"]
    for worker, name in zip(workers, current_names):
        worker.name = name
    for delivery in db_session.query(OrderRequestDelivery).filter_by(version_id=version.id):
        delivery.send_status = "unknown"
    db_session.commit()
    auth = _auth(ops_user.username)
    grouped = api_client.get("/api/order-requests/reply-groups", headers=auth)
    assert grouped.status_code == 200, grouped.text
    people = grouped.json()["items"][0]["recipients"]
    assert {p["worker_name"] for p in people} == set(current_names)
    assert {p["worker_name_snapshot"] for p in people} == set(old_names.values())
    detail = api_client.get(f"/api/order-requests/versions/{version.id}", headers=auth)
    assert detail.status_code == 200, detail.text
    assert {p["worker_name"] for p in detail.json()["deliveries"]} == set(current_names)
    assert {p["worker_name_snapshot"] for p in detail.json()["deliveries"]} == set(old_names.values())
    db_session.expire_all()
    assert db_session.get(OrderRequestVersion, version.id).snapshot_json == original_snapshot
    assert db_session.get(OrderRequestVersion, version.id).pdf_object_key == original_pdf
    assert all(d.worker_name_snapshot == old_names[d.worker_id] for d in db_session.query(OrderRequestDelivery).filter_by(version_id=version.id))
