"""GET/POST /api/assignments のAPIテスト"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import ActualStatus, AssignmentStatus, AssignmentWorkerResponseStatus, UserRole
from src.models.master import Role, Worker
from src.models.enums import AuditAction
from src.models.transaction import Actual, AssignmentSelectionSet, AuditLog, ImportBatch, Project, ShiftSlot, Assignment
from src.api import main as api_main
from src.services import scheduler as scheduler_module


class _FakeReminderSender:
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_templates = []

    def send_email(self, template, dry_run: bool = False) -> bool:
        self.sent_templates.append((template, dry_run))
        return self.should_succeed


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def _create_import_batch(db_session, project_id: str, period_key: str = "202601") -> ImportBatch:
    batch = ImportBatch(
        id=generate_ulid(),
        submitted_by="tester",
        submit_channel="api_test",
        file_name="assignments.csv",
        file_hash=f"hash-{generate_ulid()}",
        project_id=project_id,
        period_key=period_key,
        mode="replace_scope",
        scope_type="project_month",
        status="completed",
        count_success=1,
        count_error=0,
        count_skip=0,
        count_superseded=0,
        has_row_count_warning=False,
        has_total_time_warning=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def test_list_assignments_returns_paginated_items(api_client, db_session, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignments",
        email="ops_assignments@example.com",
        password="secret123",
        role="ops",
    )
    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=generate_ulid(),
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        cancel_reason=None,
        locked_price_sales=Decimal("2000.00"),
        locked_price_outsource=Decimal("1500.00"),
    )
    shift_slot = ShiftSlot(
        id=assignment.shift_slot_id,
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=1,
    )
    db_session.add(shift_slot)
    db_session.add(assignment)
    db_session.commit()

    response = api_client.get(
        "/api/assignments",
        params={"project_id": project.id, "status": AssignmentStatus.CONFIRMED.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == assignment.id
    assert payload["items"][0]["project_name"] == project.name
    assert payload["items"][0]["worker_name"] == worker.name
    assert payload["items"][0]["shift_label"] == "日勤"
    assert payload["items"][0]["status"] == AssignmentStatus.CONFIRMED.value


def test_list_assignments_restricts_site_manager_scope(api_client, db_session, project, worker, role):
    project.primary_manager_id = worker.id
    db_session.add(project)
    db_session.flush()

    site_manager = create_user_with_hashed_password(
        db=db_session,
        username="site_manager_assignments",
        email="site_manager_assignments@example.com",
        password="secret123",
        role=UserRole.SITE_MANAGER.value,
    )
    site_manager.worker_id = worker.id
    db_session.add(site_manager)

    other_project = Project(
        id=generate_ulid(),
        name="Other Assignment Project",
        code="OAP001",
        client_id=project.client_id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
        night_calc_mode="store_minutes",
        is_active=True,
    )
    db_session.add(other_project)
    db_session.commit()

    response = api_client.get(
        "/api/assignments",
        params={"project_id": other_project.id},
        headers=_auth_header(site_manager.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Project access denied"


def test_create_assignment_requires_assignment_write(api_client, db_session, shift_slot, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_create_assignment",
        email="accounting_create_assignment@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/assignments",
        json={
            "shift_slot_id": shift_slot.id,
            "worker_id": worker.id,
            "role_id": role.id,
            "status": AssignmentStatus.TENTATIVE.value,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_create_assignment_succeeds_for_ops(api_client, db_session, shift_slot, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_assignment",
        email="ops_create_assignment@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/assignments",
        json={
            "shift_slot_id": shift_slot.id,
            "worker_id": worker.id,
            "role_id": role.id,
            "status": AssignmentStatus.TENTATIVE.value,
            "locked_price_sales": "2000.00",
            "locked_price_outsource": "1500.00",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["shift_slot_id"] == shift_slot.id
    assert payload["worker_id"] == worker.id
    assert payload["role_id"] == role.id
    assert payload["status"] == AssignmentStatus.TENTATIVE.value
    assert payload["worker_response_status"] == AssignmentWorkerResponseStatus.PENDING.value
    assert payload["worker_response_requested_at"] is not None


def test_worker_can_update_assignment_response_and_log_it(api_client, db_session, assignment, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_assignment_response",
        email="worker_assignment_response@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    user.worker_id = worker.id
    db_session.add(user)
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/worker-response",
        json={"response_status": AssignmentWorkerResponseStatus.ACCEPTED.value, "note": "現地直行します"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_response_status"] == AssignmentWorkerResponseStatus.ACCEPTED.value
    assert payload["worker_response_note"] == "現地直行します"
    assert payload["worker_response_at"] is not None

    audit_log = db_session.query(AuditLog).filter(AuditLog.target_id == assignment.id).order_by(AuditLog.created_at.desc()).first()
    assert audit_log is not None
    assert audit_log.action == AuditAction.ASSIGNMENT_WORKER_RESPONSE_UPDATED.value


def test_worker_response_rejects_other_workers_assignment(api_client, db_session, assignment):
    other_worker = Worker(
        id=generate_ulid(),
        name="Other Worker",
        email="other-worker@example.com",
    )
    user = create_user_with_hashed_password(
        db=db_session,
        username="worker_assignment_response_forbidden",
        email="worker_assignment_response_forbidden@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.add(other_worker)
    db_session.flush()
    user.worker_id = other_worker.id
    db_session.add(user)
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/worker-response",
        json={"response_status": AssignmentWorkerResponseStatus.DECLINED.value, "note": "別現場が入っています"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Assignment access denied"


def test_list_assignments_can_filter_by_worker_response_status(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_response_filter",
        email="ops_assignment_response_filter@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    second_shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 16),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="翌日勤",
        required_count=1,
    )
    accepted_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=second_shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.ACCEPTED.value,
        worker_response_note="対応可能です",
        worker_response_at=datetime.now(timezone.utc),
    )
    db_session.add(second_shift_slot)
    db_session.add(accepted_assignment)
    db_session.commit()

    response = api_client.get(
        "/api/assignments",
        params={"response_status": AssignmentWorkerResponseStatus.ACCEPTED.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == accepted_assignment.id
    assert payload["items"][0]["worker_response_status"] == AssignmentWorkerResponseStatus.ACCEPTED.value


def test_list_assignments_can_filter_pending_monitoring_status(api_client, db_session, project, worker, role, monkeypatch):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_monitoring_filter",
        email="ops_assignment_monitoring_filter@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    requested_at = datetime.now(timezone.utc) - timedelta(hours=96)

    escalate_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=10),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="要確認",
        required_count=1,
    )
    watch_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=10),
        start_time=time(10, 0),
        end_time=time(19, 0),
        shift_label="監視中",
        required_count=1,
    )
    missing_email_worker = Worker(id=generate_ulid(), name="No Mail", email=None)
    db_session.add_all([escalate_slot, watch_slot, missing_email_worker])
    db_session.flush()

    db_session.add_all(
        [
            Assignment(
                id=generate_ulid(),
                shift_slot_id=escalate_slot.id,
                worker_id=worker.id,
                role_id=role.id,
                status=AssignmentStatus.CONFIRMED.value,
                worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
                worker_response_requested_at=requested_at,
            ),
            Assignment(
                id=generate_ulid(),
                shift_slot_id=watch_slot.id,
                worker_id=missing_email_worker.id,
                role_id=role.id,
                status=AssignmentStatus.CONFIRMED.value,
                worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
                worker_response_requested_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setenv("ASSIGNMENT_RESPONSE_ESCALATION_HOURS_SINCE_REQUEST", "48")

    escalate_response = api_client.get(
        "/api/assignments",
        params={
            "response_status": AssignmentWorkerResponseStatus.PENDING.value,
            "monitoring_status": "escalate",
        },
        headers=_auth_header(user.username),
    )
    assert escalate_response.status_code == 200
    escalate_payload = escalate_response.json()
    assert escalate_payload["total"] == 2
    assert all(item["monitoring_status"] == "escalate" for item in escalate_payload["items"])

    missing_email_response = api_client.get(
        "/api/assignments",
        params={
            "response_status": AssignmentWorkerResponseStatus.PENDING.value,
            "missing_email_only": True,
        },
        headers=_auth_header(user.username),
    )
    assert missing_email_response.status_code == 200
    missing_email_payload = missing_email_response.json()
    assert missing_email_payload["total"] == 1
    assert missing_email_payload["items"][0]["worker_email"] is None
    assert "メール送信先未設定" in missing_email_payload["items"][0]["monitoring_reasons"]


def test_send_assignment_response_reminders_groups_selected_pending_assignments(api_client, db_session, project, worker, role, monkeypatch):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_reminder_send",
        email="ops_assignment_reminder_send@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    first_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=1,
    )
    second_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=2),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="夜勤",
        required_count=1,
    )
    db_session.add_all([first_slot, second_slot])
    db_session.flush()

    first_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=first_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
    )
    second_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=second_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
    )
    db_session.add_all([first_assignment, second_assignment])
    db_session.commit()

    fake_sender = _FakeReminderSender(should_succeed=True)
    monkeypatch.setattr(scheduler_module, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    response = api_client.post(
        "/api/assignments/reminders/send",
        json={"assignment_ids": [first_assignment.id, second_assignment.id]},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_assignment_count"] == 2
    assert payload["eligible_assignment_count"] == 2
    assert payload["recipient_count"] == 1
    assert payload["sent_count"] == 1
    assert payload["dry_run"] is True
    assert len(fake_sender.sent_templates) == 1

    reminder_log = db_session.query(AuditLog).filter(AuditLog.action == AuditAction.ASSIGNMENT_RESPONSE_REMINDER_SENT.value).order_by(AuditLog.created_at.desc()).first()
    assert reminder_log is not None
    assert reminder_log.actor == user.username
    assert reminder_log.after_value["assignment_count"] == 2


def test_get_assignment_response_reminder_history_returns_recent_items(api_client, db_session, project, worker, role, monkeypatch):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_reminder_history",
        email="ops_assignment_reminder_history@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
        required_count=1,
    )
    db_session.add(slot)
    db_session.flush()
    target_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
    )
    db_session.add(target_assignment)
    db_session.commit()

    fake_sender = _FakeReminderSender(should_succeed=True)
    monkeypatch.setattr(scheduler_module, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    send_response = api_client.post(
        "/api/assignments/reminders/send",
        json={"assignment_ids": [target_assignment.id]},
        headers=_auth_header(user.username),
    )
    assert send_response.status_code == 200

    history_response = api_client.post(
        "/api/assignments/reminders/history",
        json={"assignment_ids": [target_assignment.id], "limit": 10},
        headers=_auth_header(user.username),
    )
    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["worker_name"] == worker.name
    assert payload["items"][0]["status"] == "sent"
    assert payload["items"][0]["dry_run"] is True


def test_send_assignment_response_escalation_notifies_admin_recipients(api_client, db_session, project, worker, role, monkeypatch):
    sender_user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_escalation",
        email="ops_assignment_escalation@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="至急",
        required_count=1,
    )
    db_session.add(slot)
    db_session.flush()
    target_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
        worker_response_requested_at=datetime.now(timezone.utc) - timedelta(hours=96),
    )
    db_session.add(target_assignment)
    db_session.commit()

    fake_sender = _FakeReminderSender(should_succeed=True)
    monkeypatch.setattr(api_main, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")
    monkeypatch.setenv("ASSIGNMENT_RESPONSE_ESCALATION_HOURS_SINCE_REQUEST", "48")
    monkeypatch.setenv("ASSIGNMENT_RESPONSE_ESCALATION_EMAILS", "admin1@example.com,admin2@example.com")

    response = api_client.post(
        "/api/assignments/reminders/escalate",
        json={"assignment_ids": [target_assignment.id]},
        headers=_auth_header(sender_user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_assignment_count"] == 1
    assert payload["recipient_count"] == 2
    assert payload["sent_count"] == 2
    assert len(fake_sender.sent_templates) == 2

    escalation_log = db_session.query(AuditLog).filter(AuditLog.action == AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_SENT.value).order_by(AuditLog.created_at.desc()).first()
    assert escalation_log is not None
    assert escalation_log.actor == sender_user.username


def test_get_assignment_response_escalation_history_returns_recent_items(api_client, db_session, project, worker, role, monkeypatch):
    sender_user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_escalation_history",
        email="ops_assignment_escalation_history@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date.today() + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="履歴確認",
        required_count=1,
    )
    db_session.add(slot)
    db_session.flush()
    target_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
        worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
        worker_response_requested_at=datetime.now(timezone.utc) - timedelta(hours=96),
    )
    db_session.add(target_assignment)
    db_session.commit()

    fake_sender = _FakeReminderSender(should_succeed=True)
    monkeypatch.setattr(api_main, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")
    monkeypatch.setenv("ASSIGNMENT_RESPONSE_ESCALATION_HOURS_SINCE_REQUEST", "48")
    monkeypatch.setenv("ASSIGNMENT_RESPONSE_ESCALATION_EMAILS", "admin1@example.com,admin2@example.com")

    send_response = api_client.post(
        "/api/assignments/reminders/escalate",
        json={"assignment_ids": [target_assignment.id]},
        headers=_auth_header(sender_user.username),
    )
    assert send_response.status_code == 200

    history_response = api_client.post(
        "/api/assignments/reminders/escalations/history",
        json={"assignment_ids": [target_assignment.id], "limit": 10},
        headers=_auth_header(sender_user.username),
    )

    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload["items"]) == 2
    recipient_emails = {item["recipient_email"] for item in payload["items"]}
    assert recipient_emails == {"admin1@example.com", "admin2@example.com"}
    assert all(item["status"] == "sent" for item in payload["items"])
    assert all(item["dry_run"] is True for item in payload["items"])
    assert all(item["assignment_ids"] == [target_assignment.id] for item in payload["items"])
    assert all(item["assignment_count"] == 1 for item in payload["items"])


def test_update_assignment_requires_assignment_write(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_update_assignment",
        email="accounting_update_assignment@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.put(
        f"/api/assignments/{assignment.id}",
        json={
            "shift_slot_id": assignment.shift_slot_id,
            "worker_id": assignment.worker_id,
            "role_id": assignment.role_id,
            "locked_price_sales": "2100.00",
            "locked_price_outsource": "1600.00",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403


def test_update_assignment_updates_worker_role_and_prices(api_client, db_session, assignment, shift_slot, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment",
        email="ops_update_assignment@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    other_worker = Worker(
        id=generate_ulid(),
        name="Edit Target Worker",
        email="edit-target-worker@example.com",
    )
    other_role = Role(
        id=generate_ulid(),
        name="夜勤責任者",
        code="night_lead",
        description="夜勤帯の責任者",
    )
    db_session.add(other_worker)
    db_session.add(other_role)
    db_session.commit()

    response = api_client.put(
        f"/api/assignments/{assignment.id}",
        json={
            "shift_slot_id": shift_slot.id,
            "worker_id": other_worker.id,
            "role_id": other_role.id,
            "locked_price_sales": "2500.00",
            "locked_price_outsource": "1800.00",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == other_worker.id
    assert payload["role_id"] == other_role.id
    assert payload["locked_price_sales"] == "2500.00"
    assert payload["locked_price_outsource"] == "1800.00"


def test_create_assignment_selection_set_persists_server_side(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_create_assignment_selection_set",
        email="ops_create_assignment_selection_set@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/assignments/selection-sets",
        json={
            "name": "4月前半の確定候補",
            "period_key": "202601",
            "assignment_ids": [assignment.id],
            "is_shared": False,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "4月前半の確定候補"
    assert payload["assignment_ids"] == [assignment.id]
    assert payload["total_assignment_count"] == 1
    assert payload["available_assignment_count"] == 1
    assert payload["created_by"] == user.username

    selection_set = db_session.get(AssignmentSelectionSet, payload["id"])
    assert selection_set is not None
    assert selection_set.assignment_ids == [assignment.id]

    audit_log = db_session.query(AuditLog).filter(AuditLog.target_id == selection_set.id).order_by(AuditLog.created_at.desc()).first()
    assert audit_log is not None
    assert audit_log.action == AuditAction.ASSIGNMENT_SELECTION_SET_SAVED.value


def test_create_shared_assignment_selection_set_requires_assignment_write(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_shared_assignment_selection_set",
        email="accounting_shared_assignment_selection_set@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/assignments/selection-sets",
        json={
            "name": "共有セット",
            "period_key": "202601",
            "assignment_ids": [assignment.id],
            "is_shared": True,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "共有選択セットの保存権限がありません"


def test_list_assignment_selection_sets_returns_own_and_shared_items(api_client, db_session, assignment):
    owner = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_selection_set_owner",
        email="ops_assignment_selection_set_owner@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    other = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_selection_set_other",
        email="ops_assignment_selection_set_other@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    own_set = AssignmentSelectionSet(
        id=generate_ulid(),
        name="自分用セット",
        period_key="202601",
        created_by_user_id=owner.id,
        is_shared=False,
        assignment_ids=[assignment.id],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    shared_set = AssignmentSelectionSet(
        id=generate_ulid(),
        name="共有セット",
        period_key="202601",
        created_by_user_id=other.id,
        is_shared=True,
        assignment_ids=[assignment.id],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(own_set)
    db_session.add(shared_set)
    db_session.commit()

    response = api_client.get(
        "/api/assignments/selection-sets",
        params={"period_key": "202601"},
        headers=_auth_header(owner.username),
    )

    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert names == {"自分用セット", "共有セット"}


def test_delete_assignment_selection_set_soft_deletes_and_logs(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_delete_assignment_selection_set",
        email="ops_delete_assignment_selection_set@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    selection_set = AssignmentSelectionSet(
        id=generate_ulid(),
        name="削除対象セット",
        period_key="202601",
        created_by_user_id=user.id,
        is_shared=False,
        assignment_ids=[assignment.id],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(selection_set)
    db_session.commit()

    response = api_client.delete(
        f"/api/assignments/selection-sets/{selection_set.id}",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 204
    db_session.refresh(selection_set)
    assert selection_set.deleted_at is not None

    audit_log = db_session.query(AuditLog).filter(AuditLog.target_id == selection_set.id).order_by(AuditLog.created_at.desc()).first()
    assert audit_log is not None
    assert audit_log.action == AuditAction.ASSIGNMENT_SELECTION_SET_DELETED.value


def test_update_assignment_blocks_reassignment_when_active_actual_exists(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_blocked",
        email="ops_update_assignment_blocked@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    other_shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 16),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="翌日勤",
        required_count=1,
    )
    batch = _create_import_batch(db_session, project.id)
    actual = Actual(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=assignment.id,
        import_batch_id=batch.id,
        work_date=date(2026, 1, 15),
        period_key="202601",
        status=ActualStatus.ACTIVE.value,
        start_time=time(9, 0),
        end_time=time(18, 0),
        break_minutes_input=60,
        hours_input=Decimal("8.00"),
        calc_minutes_total=540,
        calc_minutes_break=60,
        calc_minutes_billable=480,
        calc_minutes_night=0,
        calc_rounding_unit=15,
        calc_rounding_method="ceil",
        calc_break_rule="auto",
        applied_price_sales=Decimal("2000.00"),
        applied_price_outsource=Decimal("1500.00"),
        external_row_key=f"row-{generate_ulid()}",
        needs_review=False,
    )
    db_session.add(other_shift_slot)
    db_session.add(actual)
    db_session.commit()

    response = api_client.put(
        f"/api/assignments/{assignment.id}",
        json={
            "shift_slot_id": other_shift_slot.id,
            "worker_id": worker.id,
            "role_id": role.id,
            "locked_price_sales": "2000.00",
            "locked_price_outsource": "1500.00",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "active な実績があるため枠・稼働者・役割は変更できません"


def test_bulk_update_assignment_status_updates_multiple_assignments(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_bulk_update_assignment",
        email="ops_bulk_update_assignment@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    second_shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 16),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="翌日勤",
        required_count=1,
    )
    second_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=second_shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
    )
    db_session.add(second_shift_slot)
    db_session.add(second_assignment)
    db_session.commit()

    response = api_client.post(
        "/api/assignments/status/bulk",
        json={
            "assignment_ids": [assignment.id, second_assignment.id],
            "status": AssignmentStatus.TENTATIVE.value,
            "cancel_reason": None,
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_count"] == 2
    assert payload["status"] == AssignmentStatus.TENTATIVE.value

    db_session.refresh(assignment)
    db_session.refresh(second_assignment)
    assert assignment.status == AssignmentStatus.TENTATIVE.value
    assert second_assignment.status == AssignmentStatus.TENTATIVE.value


def test_bulk_update_assignment_status_is_all_or_nothing_when_cancel_blocked(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_bulk_update_assignment_blocked",
        email="ops_bulk_update_assignment_blocked@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    second_shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 16),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="翌日勤",
        required_count=1,
    )
    second_assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=second_shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
    )
    batch = _create_import_batch(db_session, project.id)
    actual = Actual(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=assignment.id,
        import_batch_id=batch.id,
        work_date=date(2026, 1, 15),
        period_key="202601",
        status=ActualStatus.ACTIVE.value,
        start_time=time(9, 0),
        end_time=time(18, 0),
        break_minutes_input=60,
        hours_input=Decimal("8.00"),
        calc_minutes_total=540,
        calc_minutes_break=60,
        calc_minutes_billable=480,
        calc_minutes_night=0,
        calc_rounding_unit=15,
        calc_rounding_method="ceil",
        calc_break_rule="auto",
        applied_price_sales=Decimal("2000.00"),
        applied_price_outsource=Decimal("1500.00"),
        external_row_key=f"row-{generate_ulid()}",
        needs_review=False,
    )
    db_session.add(second_shift_slot)
    db_session.add(second_assignment)
    db_session.add(actual)
    db_session.commit()

    response = api_client.post(
        "/api/assignments/status/bulk",
        json={
            "assignment_ids": [assignment.id, second_assignment.id],
            "status": AssignmentStatus.CANCELED.value,
            "cancel_reason": "現場都合",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "active な実績があるため取消できません"

    db_session.refresh(assignment)
    db_session.refresh(second_assignment)
    assert assignment.status == AssignmentStatus.CONFIRMED.value
    assert second_assignment.status == AssignmentStatus.CONFIRMED.value


def test_update_assignment_status_requires_reason_for_cancel(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_cancel_reason",
        email="ops_update_assignment_cancel_reason@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/status",
        json={"status": AssignmentStatus.CANCELED.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400


def test_update_assignment_status_requires_reason_for_reopen(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_reopen_reason",
        email="ops_update_assignment_reopen_reason@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    assignment.status = AssignmentStatus.CANCELED.value
    assignment.cancel_reason = "本人都合"
    db_session.add(assignment)
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/status",
        json={"status": AssignmentStatus.TENTATIVE.value},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "復帰理由は必須です"


def test_update_assignment_status_blocks_cancel_when_active_actual_exists(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_cancel_blocked",
        email="ops_update_assignment_cancel_blocked@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    batch = _create_import_batch(db_session, project.id)
    actual = Actual(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role.id,
        assignment_id=assignment.id,
        import_batch_id=batch.id,
        work_date=date(2026, 1, 15),
        period_key="202601",
        status=ActualStatus.ACTIVE.value,
        start_time=time(9, 0),
        end_time=time(18, 0),
        break_minutes_input=60,
        hours_input=Decimal("8.00"),
        calc_minutes_total=540,
        calc_minutes_break=60,
        calc_minutes_billable=480,
        calc_minutes_night=0,
        calc_rounding_unit=15,
        calc_rounding_method="ceil",
        calc_break_rule="auto",
        applied_price_sales=Decimal("2000.00"),
        applied_price_outsource=Decimal("1500.00"),
        external_row_key=f"row-{generate_ulid()}",
        needs_review=False,
    )
    db_session.add(actual)
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/status",
        json={"status": AssignmentStatus.CANCELED.value, "cancel_reason": "現場都合"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "active な実績があるため取消できません"


def test_update_assignment_status_cancels_without_actual(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_cancel_success",
        email="ops_update_assignment_cancel_success@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/status",
        json={"status": AssignmentStatus.CANCELED.value, "cancel_reason": "本人都合"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == AssignmentStatus.CANCELED.value
    assert payload["cancel_reason"] == "本人都合"


def test_update_assignment_status_reopens_with_reason(api_client, db_session, assignment):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_update_assignment_reopen_success",
        email="ops_update_assignment_reopen_success@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    assignment.status = AssignmentStatus.CANCELED.value
    assignment.cancel_reason = "欠員調整"
    db_session.add(assignment)
    db_session.commit()

    response = api_client.post(
        f"/api/assignments/{assignment.id}/status",
        json={"status": AssignmentStatus.CONFIRMED.value, "reopen_reason": "スタッフ確保完了"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == AssignmentStatus.CONFIRMED.value
    assert payload["cancel_reason"] is None

    audit_logs = db_session.query(AuditLog).filter(AuditLog.target_id == assignment.id).order_by(AuditLog.created_at.desc()).all()
    assert audit_logs[0].action == AuditAction.ASSIGNMENT_STATUS_CHANGED.value
    assert audit_logs[0].reason == "スタッフ確保完了"


def test_list_assignment_cancellation_history_returns_latest_entries(api_client, db_session, assignment, project, worker, role):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_assignment_cancellation_history",
        email="ops_assignment_cancellation_history@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    assignment.status = AssignmentStatus.TENTATIVE.value
    canceled_log = AuditLog(
        id=generate_ulid(),
        action=AuditAction.ASSIGNMENT_CANCELED.value,
        target_type="assignment",
        target_id=assignment.id,
        actor="ops_assignment_cancellation_history",
        actor_role=UserRole.OPS.value,
        reason="人員調整",
        extra_metadata=None,
        before_value={"status": AssignmentStatus.CONFIRMED.value},
        after_value={"status": AssignmentStatus.CANCELED.value},
        created_at=datetime.now(timezone.utc),
    )
    reopened_log = AuditLog(
        id=generate_ulid(),
        action=AuditAction.ASSIGNMENT_STATUS_CHANGED.value,
        target_type="assignment",
        target_id=assignment.id,
        actor="ops_assignment_cancellation_history",
        actor_role=UserRole.OPS.value,
        reason="代替要員を確保",
        extra_metadata=None,
        before_value={"status": AssignmentStatus.CANCELED.value},
        after_value={"status": AssignmentStatus.TENTATIVE.value},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(canceled_log)
    db_session.add(reopened_log)
    db_session.commit()

    response = api_client.get(
        "/api/assignments/cancellation-history",
        params={"work_date_from": "2026-01-01", "work_date_to": "2026-01-31"},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["assignment_id"] == assignment.id
    assert payload["items"][0]["cancel_reason"] == "人員調整"
    assert payload["items"][0]["reopen_reason"] == "代替要員を確保"
    assert payload["items"][0]["current_status"] == AssignmentStatus.TENTATIVE.value