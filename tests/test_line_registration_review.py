"""LINE申請の専用審査。入口が無効でも、届いている申請は審査できる。"""
from datetime import datetime, timedelta, timezone

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.api.line_registration_routes import LINE_ID_TOKEN_EXPIRED, assert_line_id_token_usable, line_verify_error_message
from src.domain.worker_edit_guard import issue_worker_edit_guard
from tests.registration_test_helpers import complete_registered_worker, submission_headers
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.line_order import LINK_ACTIVE, LINK_REVOKED, LineWorkerLink
from src.models.line_registration import LineRegistrationContext
from src.models.master import RegistrationRequest, Worker, WorkerRegistrationRequestDetail
from src.models.transaction import AuditLog
from src.services.audit import AuditService
from src.services.line_registration import LineRegistrationAuthError


def _enable(monkeypatch):
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("LINE_LIFF_ID", "liff-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "login-channel")
    monkeypatch.setenv("WORKER_EDIT_GUARD_KEY", "line-review-test")
    monkeypatch.setattr(
        "src.api.line_registration_routes.verify_line_id_token",
        lambda id_token: "U-line-review",
    )


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


def _admin(db_session):
    return create_user_with_hashed_password(
        db=db_session,
        username="line_review_admin",
        email="line_review_admin@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )


def _submit(api_client, body: dict, key: str) -> tuple[str, str]:
    created = api_client.post("/api/line/registration/sessions", json={"id_token": "verified-by-test"})
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    submitted = api_client.post(
        "/api/line/registration/submissions",
        json=body,
        headers=submission_headers(api_client, token, key),
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json()["request_id"], token


def _choose_new(api_client, request_id: str, headers: dict[str, str]) -> dict:
    chosen = api_client.post(
        f"/api/line/registration/reviews/{request_id}/choice",
        json={"decision": "create_new"},
        headers=headers,
    )
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()
    assert body["mode"] == "create_new"
    assert body["can_decide"] is True
    assert body["comparison_ticket"]
    return body


def _full_body() -> dict:
    return {
        "last_name": "山田",
        "first_name": "太郎",
        "last_name_furigana": "やまだ",
        "first_name_furigana": "たろう",
        "phone": "09000001111",
        "birth_date": "1990-01-02",
        "postal_code": "1000001",
        "prefecture": "東京都",
        "address1": "千代田区1-1",
        "address2": "建物",
        "email": "worker@example.com",
        "nearest_station": "新宿駅",
        "station_walk_minutes": "0",
        "emergency_contact_phone": "09000002222",
        "emergency_contact_name": "山田 花子",
        "emergency_contact_relationship": "実母",
    }


def test_worker_inbox_filters_line_pending_and_approval_moves_to_workers(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    headers = _auth(admin.username)
    public = RegistrationRequest(
        id=generate_ulid(), request_type="worker", status="pending", source_type="public_form",
    )
    db_session.add(public)
    db_session.commit()
    request_id, _ = _submit(api_client, _full_body(), "worker-inbox")
    params = {"request_type": "worker", "status": "pending", "line_only": True, "limit": 1}

    # public_formだけではLINEと従来フォームを区別できない。
    all_pending = api_client.get("/api/registration-requests", params={"status": "pending"}, headers=headers)
    assert all_pending.json()["total"] == 2
    inbox = api_client.get("/api/registration-requests", params=params, headers=headers)
    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["total"] == 1
    assert [item["id"] for item in inbox.json()["items"]] == [request_id]
    assert inbox.json()["items"][0]["summary_name"] == "山田 太郎"
    assert db_session.query(Worker).count() == 0
    assert api_client.get("/api/registration-requests", params={**params, "offset": 1}, headers=headers).json()["items"] == []
    assert api_client.get("/api/registration-requests", params=params).status_code == 401

    compared = _choose_new(api_client, request_id, headers)
    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": compared["comparison_ticket"]}, headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert api_client.get("/api/registration-requests", params=params, headers=headers).json()["total"] == 0
    workers = api_client.get("/api/workers", headers=headers)
    assert workers.status_code == 200, workers.text
    assert [worker["name"] for worker in workers.json()["items"]] == ["山田 太郎"]
    assert db_session.get(RegistrationRequest, public.id).status == "pending"


def test_create_new_links_in_the_same_decision_and_replay_keeps_the_request(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    untouched = Worker(id=generate_ulid(), name="山田 太郎", phone="09000001111", is_active=True, tags=[])
    db_session.add(untouched)
    db_session.commit()
    request_id, token = _submit(api_client, _full_body(), "review-create")
    headers = _auth(admin.username)

    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
    assert review.status_code == 200, review.text
    opened = review.json()
    assert opened["mode"] == "choose"
    assert opened["can_decide"] is False
    assert opened["comparison_ticket"] is None
    assert any(item["worker_id"] == untouched.id for item in opened["candidates"])
    body = _choose_new(api_client, request_id, headers)
    assert body["worker_id"] is None
    assert body["before"]["name"] == ""
    assert body["after"]["name"] == "山田 太郎"
    assert body["after"]["address"] == "東京都千代田区1-1\n建物"

    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": body["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    db_session.expire_all()
    stored = db_session.get(RegistrationRequest, request_id)
    context = db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one()
    created = db_session.get(Worker, approved.json()["worker_id"])
    links = db_session.query(LineWorkerLink).filter_by(worker_id=created.id, status=LINK_ACTIVE).all()
    assert stored.status == "approved"
    assert stored.approved_target_id == created.id
    assert context.is_open is False
    assert created.name == "山田 太郎"
    assert created.birth_date.isoformat() == "1990-01-02"
    assert created.postal_code == "1000001"
    assert len(links) == 1
    assert links[0].line_user_id == "U-line-review"
    assert db_session.get(Worker, untouched.id).name == "山田 太郎"
    assert db_session.query(LineWorkerLink).filter_by(worker_id=untouched.id).count() == 0

    replay = api_client.post(
        "/api/line/registration/submissions",
        json=_full_body(),
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "review-create"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["request_id"] == request_id
    assert replay.json()["saved"] is True
    assert db_session.query(LineRegistrationContext).filter_by(line_user_id="U-line-review").count() == 1

    fresh = api_client.post("/api/line/registration/sessions", json={"id_token": "verified-by-test"})
    another = api_client.post(
        "/api/line/registration/submissions",
        json=_full_body(),
        headers=submission_headers(api_client, fresh.json()["token"], "review-create-next"),
    )
    assert another.status_code == 200, another.text
    assert another.json()["request_id"] != request_id


def test_linked_update_keeps_blank_fields_and_does_not_add_a_link(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    worker = Worker(
        id=generate_ulid(),
        name="元の 名前",
        furigana="もとの なまえ",
        phone="09011112222",
        email="keep@example.com",
        postal_code="1500001",
        address="東京都旧住所",
        is_active=True,
        tags=[],
    )
    db_session.add(complete_registered_worker(worker))
    db_session.flush()
    db_session.add(
        LineWorkerLink(
            id=generate_ulid(),
            worker_id=worker.id,
            line_user_id="U-line-review",
            status=LINK_ACTIVE,
            linked_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    request_id, _token = _submit(api_client, {"phone": "09000003333"}, "review-linked")
    headers = _auth(admin.username)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["mode"] == "fixed_update"
    assert body["worker_id"] == worker.id
    assert body["before"]["email"] == "keep@example.com"
    assert body["after"]["phone"] == "09000003333"
    assert body["after"]["email"] == "keep@example.com"
    assert body["after"]["address"] == "東京都旧住所"

    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": body["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    db_session.expire_all()
    stored = db_session.get(Worker, worker.id)
    assert stored.phone == "09000003333"
    assert stored.email == "keep@example.com"
    assert stored.address == "東京都旧住所"
    assert stored.name == "元の 名前"
    assert db_session.query(LineWorkerLink).filter_by(status=LINK_ACTIVE).count() == 1
    assert db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one().is_open is False


def test_reject_closes_the_request_without_changing_the_worker(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    request_id, _token = _submit(api_client, _full_body(), "review-reject")
    headers = _auth(admin.username)
    rejected = api_client.post(
        f"/api/line/registration/reviews/{request_id}/reject",
        json={"reason": "内容不足"},
        headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    db_session.expire_all()
    assert db_session.get(RegistrationRequest, request_id).status == "rejected"
    assert db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one().is_open is False
    assert db_session.query(LineWorkerLink).count() == 0


def test_stale_ticket_does_not_approve_and_failure_audit_has_no_values(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    worker = Worker(id=generate_ulid(), name="元", phone="09011110000", is_active=True, tags=[])
    db_session.add(complete_registered_worker(worker))
    db_session.flush()
    db_session.add(
        LineWorkerLink(
            id=generate_ulid(),
            worker_id=worker.id,
            line_user_id="U-line-review",
            status=LINK_ACTIVE,
            linked_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    request_id, _token = _submit(api_client, {"phone": "09000004444"}, "review-stale")
    headers = _auth(admin.username)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
    ticket = review.json()["comparison_ticket"]
    worker.phone = "09099998888"
    db_session.commit()

    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": ticket},
        headers=headers,
    )
    assert approved.status_code == 409
    db_session.expire_all()
    assert db_session.get(Worker, worker.id).phone == "09099998888"
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    assert db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one().is_open is True
    audit = (
        db_session.query(AuditLog)
        .filter_by(target_id=request_id, action="line_registration_review_rejected")
        .one()
    )
    assert audit.reason == "ticket_mismatch"
    assert audit.before_value is None
    assert audit.after_value is None
    assert "09099998888" not in f"{audit.extra_metadata}"
    assert "U-line-review" not in f"{audit.actor} {audit.reason} {audit.extra_metadata}"

    edit_ticket = issue_worker_edit_guard(db_session.get(Worker, worker.id), admin.id)
    wrong = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": edit_ticket},
        headers=headers,
    )
    assert wrong.status_code == 409
    db_session.expire_all()
    assert db_session.get(RegistrationRequest, request_id).status == "pending"


def test_review_works_while_entry_is_off_and_public_requests_stay_on_the_old_path(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    request_id, _token = _submit(api_client, _full_body(), "review-closed-entry")
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "0")
    headers = _auth(admin.username)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
    assert review.status_code == 200, review.text
    assert review.json()["comparison_ticket"] is None
    chosen = _choose_new(api_client, request_id, headers)
    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": chosen["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text

    plain = RegistrationRequest(
        id=generate_ulid(),
        request_type="worker",
        status="pending",
        source_type="public_form",
        failed_attempts=0,
    )
    db_session.add(plain)
    db_session.commit()
    missing = api_client.get(f"/api/line/registration/reviews/{plain.id}", headers=headers)
    assert missing.status_code == 404
    rejected = api_client.post(
        f"/api/registration-requests/{plain.id}/reject",
        json={"reason": "従来フォーム"},
        headers=headers,
    )
    assert rejected.status_code == 200, rejected.text


def test_relink_cannot_move_the_fixed_target(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    worker_a = Worker(id=generate_ulid(), name="稼働者A", phone="09011110001", is_active=True, tags=[])
    db_session.add(complete_registered_worker(worker_a))
    db_session.flush()
    link_a = LineWorkerLink(
        id=generate_ulid(),
        worker_id=worker_a.id,
        line_user_id="U-line-review",
        status=LINK_ACTIVE,
        linked_at=datetime.now(timezone.utc),
    )
    db_session.add(link_a)
    db_session.commit()
    request_id, _token = _submit(api_client, {"phone": "09000003333"}, "review-fixed-relink")
    link_a.status = LINK_REVOKED
    db_session.commit()
    worker_b = Worker(id=generate_ulid(), name="稼働者B", phone="09022220002", is_active=True, tags=[])
    db_session.add(complete_registered_worker(worker_b))
    db_session.flush()
    db_session.add(
        LineWorkerLink(
            id=generate_ulid(),
            worker_id=worker_b.id,
            line_user_id="U-line-review",
            status=LINK_ACTIVE,
            linked_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    headers = _auth(admin.username)

    def opened():
        review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
        assert review.status_code == 200, review.text
        return review.json()

    body = opened()
    assert body["mode"] == "fixed_update"
    assert body["worker_id"] == worker_a.id
    assert body["link_id"] == link_a.id
    assert body["can_decide"] is False
    assert body["comparison_ticket"]
    assert "解除または差し替え" in body["blocked_reason"]
    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": body["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 409
    assert "解除または差し替え" in approved.text
    db_session.expire_all()
    assert db_session.get(Worker, worker_a.id).phone == "09011110001"
    assert db_session.get(Worker, worker_b.id).phone == "09022220002"
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    again = opened()
    assert again["worker_id"] == worker_a.id
    assert again["link_id"] == link_a.id
    assert again["can_decide"] is False
    retried = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": again["comparison_ticket"]},
        headers=headers,
    )
    assert retried.status_code == 409
    db_session.expire_all()
    assert db_session.get(Worker, worker_b.id).phone == "09022220002"


def test_unlinked_existing_worker_is_not_created_without_an_explicit_choice(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    existing = Worker(
        id=generate_ulid(),
        name="山田 太郎",
        furigana="やまだ たろう",
        phone="09000001111",
        email="keep@example.com",
        is_active=True,
        tags=[],
    )
    db_session.add(existing)
    db_session.commit()
    body = _full_body()
    body["phone"] = "09000002222"
    body["email"] = "next@example.com"
    request_id, _token = _submit(api_client, body, "review-existing")
    headers = _auth(admin.username)
    review = api_client.get(f"/api/line/registration/reviews/{request_id}", headers=headers)
    assert review.status_code == 200, review.text
    opened = review.json()
    assert opened["mode"] == "choose"
    assert opened["can_decide"] is False
    assert opened["comparison_ticket"] is None
    assert any(item["worker_id"] == existing.id and "氏名" in item["match_reasons"] for item in opened["candidates"])
    missing = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": "not-a-ticket"},
        headers=headers,
    )
    assert missing.status_code == 409
    waiting = api_client.post(
        f"/api/line/registration/reviews/{request_id}/choice",
        json={"decision": "existing", "worker_id": existing.id},
        headers=headers,
    )
    assert waiting.status_code == 200, waiting.text
    held = waiting.json()
    assert held["mode"] == "existing"
    assert held["worker_id"] == existing.id
    assert held["can_decide"] is False
    assert held["comparison_ticket"] is None
    assert "一次性コード" in held["blocked_reason"]
    db_session.expire_all()
    assert db_session.query(Worker).count() == 1
    assert db_session.query(LineWorkerLink).count() == 0
    assert db_session.get(Worker, existing.id).email == "keep@example.com"

    db_session.add(
        LineWorkerLink(
            id=generate_ulid(),
            worker_id=existing.id,
            line_user_id="U-line-review",
            status=LINK_ACTIVE,
            linked_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    ready = api_client.post(
        f"/api/line/registration/reviews/{request_id}/choice",
        json={"decision": "existing", "worker_id": existing.id},
        headers=headers,
    )
    assert ready.status_code == 200, ready.text
    selected = ready.json()
    assert selected["can_decide"] is True
    assert selected["mode"] == "existing"
    assert selected["comparison_ticket"]
    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": selected["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    db_session.expire_all()
    assert db_session.query(Worker).count() == 1
    assert db_session.query(LineWorkerLink).filter_by(status=LINK_ACTIVE).count() == 1
    stored = db_session.get(Worker, existing.id)
    assert stored.phone == "09000002222"
    assert stored.email == "next@example.com"


def test_create_new_rechecks_required_fields_and_a_failure_leaves_no_worker(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    headers = _auth(admin.username)
    request_id, _token = _submit(api_client, _full_body(), "review-required")
    chosen = _choose_new(api_client, request_id, headers)
    detail = db_session.query(WorkerRegistrationRequestDetail).filter_by(request_id=request_id).one()
    detail.phone = None
    db_session.commit()
    blocked = api_client.post(
        f"/api/line/registration/reviews/{request_id}/choice",
        json={"decision": "create_new"},
        headers=headers,
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["can_decide"] is False
    assert blocked.json()["comparison_ticket"] is None
    approved = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": chosen["comparison_ticket"]},
        headers=headers,
    )
    assert approved.status_code == 409
    assert "必要な項目" in approved.text
    db_session.expire_all()
    assert db_session.query(Worker).count() == 0
    assert db_session.query(LineWorkerLink).count() == 0
    assert db_session.get(RegistrationRequest, request_id).status == "pending"

    detail.phone = "09000001111"
    db_session.commit()
    fresh = _choose_new(api_client, request_id, headers)
    original = AuditService.log

    def stop_after_insert(self, action, *args, **kwargs):
        if action == "line_registration_approved":
            raise RuntimeError("forced")
        return original(self, action, *args, **kwargs)

    monkeypatch.setattr(AuditService, "log", stop_after_insert)
    failed = api_client.post(
        f"/api/line/registration/reviews/{request_id}/approve",
        json={"comparison_ticket": fresh["comparison_ticket"]},
        headers=headers,
    )
    assert failed.status_code == 500
    db_session.expire_all()
    assert db_session.query(Worker).count() == 0
    assert db_session.query(LineWorkerLink).count() == 0
    assert db_session.get(RegistrationRequest, request_id).status == "pending"
    assert db_session.query(LineRegistrationContext).filter_by(request_id=request_id).one().is_open is True


def test_line_id_token_expiry_is_distinct_from_the_registration_bearer():
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    try:
        assert_line_id_token_usable(
            {"sub": "U-person", "aud": "login-channel", "exp": int(now.timestamp()) - 1},
            "login-channel",
            now,
        )
    except LineRegistrationAuthError as exc:
        assert exc.message == LINE_ID_TOKEN_EXPIRED
    else:
        raise AssertionError("期限切れのIDトークンを受け付けました")
    subject = assert_line_id_token_usable(
        {"sub": "U-person", "aud": "login-channel", "exp": int((now + timedelta(minutes=30)).timestamp())},
        "login-channel",
        now,
    )
    assert subject == "U-person"
    assert line_verify_error_message('{"error_description":"IdToken expired."}') == LINE_ID_TOKEN_EXPIRED
    assert LINE_ID_TOKEN_EXPIRED != "本人確認の期限が切れました。入力は残しています。本人確認をやり直してから、もう一度送信してください。"
