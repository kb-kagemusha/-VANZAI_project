from datetime import date, timedelta, time

from sqlalchemy.orm import sessionmaker

from src.models.base import generate_ulid
from src.models.enums import AssignmentStatus, AssignmentWorkerResponseStatus, AuditAction
from src.models.master import Worker
from src.models.transaction import Assignment, AuditLog, ShiftSlot
from src.services import scheduler as scheduler_module


class _FakeSender:
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_templates = []

    def send_email(self, template, dry_run: bool = False) -> bool:
        self.sent_templates.append((template, dry_run))
        return self.should_succeed


def test_weekly_reminder_sends_grouped_assignment_response_email(engine, db_session, project, worker, role, monkeypatch):
    today = date.today()

    base_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=today + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
    )
    db_session.add(base_slot)
    db_session.flush()
    db_session.add(
        Assignment(
            id=generate_ulid(),
            shift_slot_id=base_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
        )
    )

    second_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=today + timedelta(days=3),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="夜勤",
    )
    db_session.add(second_slot)
    db_session.flush()

    db_session.add(
        Assignment(
            id=generate_ulid(),
            shift_slot_id=second_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
        )
    )

    responded_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=today + timedelta(days=5),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="返答済み",
    )
    db_session.add(responded_slot)
    db_session.flush()
    db_session.add(
        Assignment(
            id=generate_ulid(),
            shift_slot_id=responded_slot.id,
            worker_id=worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.ACCEPTED.value,
        )
    )

    missing_email_worker = Worker(
        id=generate_ulid(),
        name="No Mail Worker",
        email=None,
    )
    db_session.add(missing_email_worker)
    db_session.flush()

    missing_mail_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=today + timedelta(days=4),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="未設定",
    )
    db_session.add(missing_mail_slot)
    db_session.flush()
    db_session.add(
        Assignment(
            id=generate_ulid(),
            shift_slot_id=missing_mail_slot.id,
            worker_id=missing_email_worker.id,
            role_id=role.id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
        )
    )
    db_session.commit()

    testing_session_local = sessionmaker(bind=engine)
    fake_sender = _FakeSender(should_succeed=True)
    monkeypatch.setattr(scheduler_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(scheduler_module, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")
    monkeypatch.setenv("SCHEDULER_WEEKLY_LOOKAHEAD_DAYS", "14")

    service = scheduler_module.SchedulerService()
    try:
        service._run_weekly_reminder()
    finally:
        service.shutdown()

    assert len(fake_sender.sent_templates) == 1
    template, dry_run = fake_sender.sent_templates[0]
    assert dry_run is True
    assert template.to == worker.email
    assert "未回答件数: 2" in template.body
    assert project.name in template.body

    audit_logs = db_session.query(AuditLog).filter(AuditLog.action == AuditAction.ASSIGNMENT_RESPONSE_REMINDER_SENT.value).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].actor == "scheduler"
    assert audit_logs[0].after_value["assignment_count"] == 2


def test_weekly_reminder_logs_failed_delivery(engine, db_session, assignment, project, worker, role, monkeypatch):
    today = date.today()
    assignment.worker_response_status = AssignmentWorkerResponseStatus.PENDING.value
    assignment.shift_slot.work_date = today + timedelta(days=1)
    db_session.add(assignment)
    db_session.commit()

    testing_session_local = sessionmaker(bind=engine)
    fake_sender = _FakeSender(should_succeed=False)
    monkeypatch.setattr(scheduler_module, "SessionLocal", testing_session_local)
    monkeypatch.setattr(scheduler_module, "get_default_sender", lambda provider="gmail": fake_sender)
    monkeypatch.setenv("EMAIL_DRY_RUN", "false")
    monkeypatch.setenv("SCHEDULER_WEEKLY_LOOKAHEAD_DAYS", "14")

    service = scheduler_module.SchedulerService()
    try:
        service._run_weekly_reminder()
    finally:
        service.shutdown()

    assert len(fake_sender.sent_templates) == 1
    audit_log = db_session.query(AuditLog).filter(AuditLog.action == AuditAction.ASSIGNMENT_RESPONSE_REMINDER_FAILED.value).one()
    assert audit_log.actor == "scheduler"
    assert audit_log.after_value["worker_id"] == worker.id