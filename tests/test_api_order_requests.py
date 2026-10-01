"""発注依頼書の保存・確定・履歴。LINE送信は未接続。"""
from datetime import date, timedelta

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestVersion
from src.services.document_storage import DocumentStorage


def _token(username: str) -> str:
    return create_access_token({"sub": username})


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


@pytest.fixture
def pdf_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def ops_user(db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="order_ops",
        email="order_ops@example.com",
        password="pass123",
        role=UserRole.OPS.value,
    )
    db_session.commit()
    return user


@pytest.fixture
def worker_user(db_session):
    worker = Worker(id=generate_ulid(), name="稼働者A", email="order_worker_a@example.com", is_active=True)
    db_session.add(worker)
    db_session.flush()
    user = create_user_with_hashed_password(
        db=db_session,
        username="order_worker",
        email="order_worker@example.com",
        password="pass123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.commit()
    return user, worker


def _worker(db_session, name: str) -> Worker:
    worker = Worker(id=generate_ulid(), name=name, is_active=True)
    db_session.add(worker)
    db_session.commit()
    return worker


def _body(worker_ids: list[str], **overrides) -> dict:
    payload = {
        "kind": "formal",
        "work_date_label": "2026-10-05",
        "site_name": "渋谷現場",
        "request_conditions": "9時集合",
        "body": "通常稼働",
        "contact_name": "依頼担当",
        "contact_desk": "03-0000-0000",
        "worker_ids": worker_ids,
        "phone_first": False,
    }
    payload.update(overrides)
    return payload


def test_confirm_creates_one_pdf_and_delivery_rows(api_client, db_session, ops_user, pdf_root):
    first = _worker(db_session, "稼働者A")
    second = _worker(db_session, "稼働者B")
    created = api_client.post(
        "/api/order-requests",
        json=_body([first.id, second.id]),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    version_id = created.json()["id"]

    confirmed = api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    assert confirmed.status_code == 200, confirmed.text
    data = confirmed.json()
    assert data["status"] == "confirmed"
    assert data["has_pdf"] is True
    assert data["template_layout_applied"] is False
    assert data["line_send_available"] is False
    assert len(data["deliveries"]) == 2
    assert {row["send_status"] for row in data["deliveries"]} == {"unsent"}
    assert {row["ack_status"] for row in data["deliveries"]} == {"unacked"}
    assert "pdf_object_key" not in data

    pdf = api_client.get(
        f"/api/order-requests/versions/{version_id}/pdf",
        headers=_auth(ops_user.username),
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]


def test_pdf_save_failure_rolls_back_confirmation(api_client, db_session, ops_user, pdf_root, monkeypatch):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id]),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]

    def fail_save(self, object_key, content):
        raise OSError("disk full")

    monkeypatch.setattr(DocumentStorage, "save_bytes", fail_save)
    failed = api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    assert failed.status_code == 500

    db_session.expire_all()
    version = db_session.get(OrderRequestVersion, version_id)
    assert version.status == "draft"
    assert version.pdf_object_key is None
    assert db_session.query(OrderRequestDelivery).count() == 0


def test_confirmed_snapshot_is_not_rewritten(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "確定前の氏名")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], work_date_label="10月5日"),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]
    assert api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    ).status_code == 200

    worker.name = "改名後"
    db_session.commit()
    edited = api_client.patch(
        f"/api/order-requests/versions/{version_id}",
        json={"work_date_label": "変えてはいけない"},
        headers=_auth(ops_user.username),
    )
    assert edited.status_code == 409

    detail = api_client.get(
        f"/api/order-requests/versions/{version_id}",
        headers=_auth(ops_user.username),
    ).json()
    assert detail["work_date_label"] == "10月5日"
    assert detail["deliveries"][0]["worker_name_snapshot"] == "確定前の氏名"


def test_kind_cannot_change_after_confirm_and_revision_keeps_old_version(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body([worker.id], kind="test"),
        headers=_auth(ops_user.username),
    )
    version_id = created.json()["id"]
    api_client.post(
        f"/api/order-requests/versions/{version_id}/confirm",
        headers=_auth(ops_user.username),
    )
    changed = api_client.patch(
        f"/api/order-requests/versions/{version_id}",
        json={"kind": "formal"},
        headers=_auth(ops_user.username),
    )
    assert changed.status_code == 409

    revised = api_client.post(
        f"/api/order-requests/versions/{version_id}/revise",
        json={"reason": "条件変更"},
        headers=_auth(ops_user.username),
    )
    assert revised.status_code == 200, revised.text
    draft = revised.json()
    assert draft["status"] == "draft"
    assert draft["kind"] == "test"
    assert draft["version_no"] == 2
    assert draft["revision_of_version_id"] == version_id
    assert draft["deliveries"] == []

    original = api_client.get(
        f"/api/order-requests/versions/{version_id}",
        headers=_auth(ops_user.username),
    ).json()
    assert original["status"] == "confirmed"
    assert original["work_date_label"] == "2026-10-05"


def test_default_list_hides_test_documents(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    api_client.post("/api/order-requests", json=_body([worker.id], kind="test"), headers=_auth(ops_user.username))
    formal = api_client.post("/api/order-requests", json=_body([worker.id]), headers=_auth(ops_user.username))
    listed = api_client.get("/api/order-requests", headers=_auth(ops_user.username))
    assert listed.status_code == 200
    numbers = {item["document_number"] for item in listed.json()["items"]}
    assert formal.json()["document_number"] in numbers
    assert all(item["kind"] == "formal" for item in listed.json()["items"])

    tests = api_client.get("/api/order-requests?kind=test", headers=_auth(ops_user.username))
    assert tests.json()["total"] == 1
    assert tests.json()["items"][0]["kind"] == "test"


def test_phone_first_does_not_mark_sent_and_overdue_stays_unsent(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post(
        "/api/order-requests",
        json=_body(
            [worker.id],
            phone_first=True,
            phone_note="先に電話した",
            follow_up_due_on=(date.today() - timedelta(days=2)).isoformat(),
            tracker_user_id=ops_user.id,
        ),
        headers=_auth(ops_user.username),
    )
    assert created.status_code == 200, created.text
    assert created.json()["phone_first"] is True
    assert created.json()["deliveries"] == []

    overdue = api_client.get("/api/order-requests?queue=overdue", headers=_auth(ops_user.username))
    assert overdue.json()["total"] == 1
    assert overdue.json()["items"][0]["phone_first"] is True
    assert overdue.json()["items"][0]["unsent_count"] == 0
    assert overdue.json()["items"][0]["status"] == "draft"


def test_cancel_stops_dispatch_without_clearing_delivery(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "稼働者A")
    created = api_client.post("/api/order-requests", json=_body([worker.id]), headers=_auth(ops_user.username))
    version_id = created.json()["id"]
    api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops_user.username))
    cancelled = api_client.post(
        f"/api/order-requests/versions/{version_id}/cancel",
        json={"reason": "中止"},
        headers=_auth(ops_user.username),
    )
    assert cancelled.status_code == 200, cancelled.text
    data = cancelled.json()
    assert data["status"] == "cancelled"
    assert data["dispatch_stopped"] is True
    assert data["deliveries"][0]["send_status"] == "unsent"
    assert data["deliveries"][0]["ack_status"] == "unacked"

    hidden = api_client.get("/api/order-requests?queue=unsent", headers=_auth(ops_user.username))
    assert all(item["version_id"] != version_id for item in hidden.json()["items"])


def test_worker_and_anonymous_cannot_read_pdf(api_client, db_session, ops_user, worker_user, pdf_root):
    _user, worker = worker_user
    created = api_client.post("/api/order-requests", json=_body([worker.id]), headers=_auth(ops_user.username))
    version_id = created.json()["id"]
    api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops_user.username))

    denied = api_client.get(
        f"/api/order-requests/versions/{version_id}/pdf",
        headers=_auth("order_worker"),
    )
    assert denied.status_code == 403
    assert api_client.get(f"/api/order-requests/versions/{version_id}/pdf").status_code == 401
    assert api_client.get("/storage/pdfs/order-requests/secret.pdf").status_code == 404


def test_rejects_too_many_or_duplicate_recipients(api_client, db_session, ops_user):
    worker = _worker(db_session, "稼働者A")
    duplicated = api_client.post(
        "/api/order-requests",
        json=_body([worker.id, worker.id]),
        headers=_auth(ops_user.username),
    )
    assert duplicated.status_code == 400

    ids = [_worker(db_session, f"人{index}").id for index in range(31)]
    too_many = api_client.post(
        "/api/order-requests",
        json=_body(ids),
        headers=_auth(ops_user.username),
    )
    assert too_many.status_code == 400
    assert db_session.query(OrderRequestDelivery).count() == 0
