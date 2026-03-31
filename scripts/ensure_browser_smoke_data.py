"""Create deterministic browser-smoke data for admin-web and staff-mobile smoke checks."""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.deps import SessionLocal
from src.models.base import generate_ulid
from src.models.enums import AuditAction, AssignmentStatus, AssignmentWorkerResponseStatus, AvailabilityStatus, PayoutStatus
from src.models.master import Client, Role, Worker
from src.models.transaction import Actual, Assignment, AuditLog, Expense, Payout, PayoutDelivery, Project, ShiftSlot, WorkerAvailability


CLIENT_CODE = "SMOKE-CLIENT"
PROJECT_CODE = "SMOKE-PAYOUT"
WORKER_NOTE = "browser-smoke-missing-recipient"
PAYOUT_NOTE = "browser-smoke-missing-recipient-payout"
AUDIT_REASON = "browser smoke payout delivery summary"
PERIOD_KEY = "202601"
DELIVERY_RECIPIENT = "smoke-recipient@example.com"
DELIVERY_NOTE = "スモーク確認送信"
INTERNAL_NOTE = "監査ログ要約確認用"
RESPONSE_WORKER_NOTE = "browser-smoke-assignment-response"
RESPONSE_WORKER_EMAIL = "smoke-assignment-worker@example.com"
RESPONSE_ROLE_CODE = "SMOKE-RESP-ROLE"
RESPONSE_SHIFT_LABEL = "Smoke Pending Response"
RESPONSE_SHIFT_NOTE = "browser-smoke-assignment-response-shift"
OPS_WORKER_NOTE = "browser-smoke-assignment-ops"
OPS_WORKER_EMAIL = "smoke-assignment-ops@example.com"
OPS_ROLE_CODE = "SMOKE-OPS-ROLE"
OPS_SHIFT_LABEL = "Smoke Ops Assignment"
OPS_SHIFT_NOTE = "browser-smoke-assignment-ops-shift"
MOBILE_PROJECT_CODE = "SMOKE-MOBILE"
MOBILE_WORKER_NOTE = "browser-smoke-mobile-worker"
MOBILE_WORKER_EMAIL = "smoke-mobile-worker@example.com"
MOBILE_ROLE_CODE = "SMOKE-MOBILE-ROLE"
MOBILE_TODAY_SHIFT_LABEL = "Smoke Mobile Today"
MOBILE_PENDING_SHIFT_LABEL = "Smoke Mobile Pending Response"
MOBILE_SHIFT_NOTE = "browser-smoke-mobile-shift"
MOBILE_EXPENSE_NOTE = "browser-smoke-mobile-expense"
MOBILE_AVAILABILITY_NOTE = "browser-smoke-mobile-availability"


def ensure_client(session):
    client = session.query(Client).filter(Client.code == CLIENT_CODE).first()
    if client is None:
        client = Client(
            id=generate_ulid(),
            name="Browser Smoke Client",
            code=CLIENT_CODE,
            contact_email="smoke-client@example.com",
        )
        session.add(client)
        session.flush()
    return client


def ensure_project(session, client_id: str):
    project = session.query(Project).filter(Project.code == PROJECT_CODE).first()
    if project is None:
        project = Project(
            id=generate_ulid(),
            name="Browser Smoke Payout Project",
            code=PROJECT_CODE,
            client_id=client_id,
            is_active=True,
        )
        session.add(project)
        session.flush()
    else:
        project.client_id = client_id
        project.is_active = True
    return project


def ensure_mobile_project(session, client_id: str):
    project = session.query(Project).filter(Project.code == MOBILE_PROJECT_CODE).first()
    if project is None:
        project = Project(
            id=generate_ulid(),
            name="Browser Smoke Mobile Project",
            code=MOBILE_PROJECT_CODE,
            client_id=client_id,
            is_active=True,
        )
        session.add(project)
        session.flush()
    else:
        project.name = "Browser Smoke Mobile Project"
        project.client_id = client_id
        project.is_active = True
    return project


def ensure_worker(session):
    worker = session.query(Worker).filter(Worker.notes == WORKER_NOTE).first()
    if worker is None:
        worker = Worker(
            id=generate_ulid(),
            name="Browser Smoke Missing Recipient Worker",
            email=None,
            notes=WORKER_NOTE,
            is_active=True,
        )
        session.add(worker)
        session.flush()
    else:
        worker.name = "Browser Smoke Missing Recipient Worker"
        worker.email = None
        worker.is_active = True
    return worker


def ensure_assignment_response_worker(session):
    worker = session.query(Worker).filter(Worker.notes == RESPONSE_WORKER_NOTE).first()
    if worker is None:
        worker = Worker(
            id=generate_ulid(),
            name="Browser Smoke Response Worker",
            email=RESPONSE_WORKER_EMAIL,
            notes=RESPONSE_WORKER_NOTE,
            is_active=True,
        )
        session.add(worker)
        session.flush()
    else:
        worker.name = "Browser Smoke Response Worker"
        worker.email = RESPONSE_WORKER_EMAIL
        worker.is_active = True
    return worker


def ensure_assignment_ops_worker(session):
    worker = session.query(Worker).filter(Worker.notes == OPS_WORKER_NOTE).first()
    if worker is None:
        worker = Worker(
            id=generate_ulid(),
            name="Browser Smoke Ops Worker",
            email=OPS_WORKER_EMAIL,
            notes=OPS_WORKER_NOTE,
            is_active=True,
        )
        session.add(worker)
        session.flush()
    else:
        worker.name = "Browser Smoke Ops Worker"
        worker.email = OPS_WORKER_EMAIL
        worker.is_active = True
    return worker


def ensure_mobile_worker(session):
    worker = session.query(Worker).filter(Worker.notes == MOBILE_WORKER_NOTE).first()
    if worker is None:
        worker = Worker(
            id=generate_ulid(),
            name="Browser Smoke Mobile Worker",
            email=MOBILE_WORKER_EMAIL,
            notes=MOBILE_WORKER_NOTE,
            is_active=True,
        )
        session.add(worker)
        session.flush()
    else:
        worker.name = "Browser Smoke Mobile Worker"
        worker.email = MOBILE_WORKER_EMAIL
        worker.is_active = True
    return worker


def ensure_response_role(session):
    role = session.query(Role).filter(Role.code == RESPONSE_ROLE_CODE).first()
    if role is None:
        role = Role(
            id=generate_ulid(),
            name="Browser Smoke Response Role",
            code=RESPONSE_ROLE_CODE,
        )
        session.add(role)
        session.flush()
    else:
        role.name = "Browser Smoke Response Role"
    return role


def ensure_assignment_ops_role(session):
    role = session.query(Role).filter(Role.code == OPS_ROLE_CODE).first()
    if role is None:
        role = Role(
            id=generate_ulid(),
            name="Browser Smoke Ops Role",
            code=OPS_ROLE_CODE,
        )
        session.add(role)
        session.flush()
    else:
        role.name = "Browser Smoke Ops Role"
    return role


def ensure_mobile_role(session):
    role = session.query(Role).filter(Role.code == MOBILE_ROLE_CODE).first()
    if role is None:
        role = Role(
            id=generate_ulid(),
            name="Browser Smoke Mobile Role",
            code=MOBILE_ROLE_CODE,
        )
        session.add(role)
        session.flush()
    else:
        role.name = "Browser Smoke Mobile Role"
    return role


def ensure_assignment_response_slot(session, project_id: str):
    slot = (
        session.query(ShiftSlot)
        .filter(
            ShiftSlot.project_id == project_id,
            ShiftSlot.work_date == date(2026, 1, 15),
            ShiftSlot.shift_label == RESPONSE_SHIFT_LABEL,
        )
        .first()
    )
    if slot is None:
        slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project_id,
            work_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(18, 0),
            shift_label=RESPONSE_SHIFT_LABEL,
            required_count=1,
            notes=RESPONSE_SHIFT_NOTE,
        )
        session.add(slot)
        session.flush()
    else:
        slot.start_time = time(9, 0)
        slot.end_time = time(18, 0)
        slot.required_count = 1
        slot.notes = RESPONSE_SHIFT_NOTE
    return slot


def ensure_assignment_ops_slot(session, project_id: str):
    slot = (
        session.query(ShiftSlot)
        .filter(
            ShiftSlot.project_id == project_id,
            ShiftSlot.work_date == date(2026, 1, 20),
            ShiftSlot.shift_label == OPS_SHIFT_LABEL,
        )
        .first()
    )
    if slot is None:
        slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project_id,
            work_date=date(2026, 1, 20),
            start_time=time(8, 30),
            end_time=time(17, 30),
            shift_label=OPS_SHIFT_LABEL,
            required_count=1,
            notes=OPS_SHIFT_NOTE,
        )
        session.add(slot)
        session.flush()
    else:
        slot.start_time = time(8, 30)
        slot.end_time = time(17, 30)
        slot.required_count = 1
        slot.notes = OPS_SHIFT_NOTE
    return slot


def ensure_mobile_today_slot(session, project_id: str):
    slot = (
        session.query(ShiftSlot)
        .filter(
            ShiftSlot.project_id == project_id,
            ShiftSlot.work_date == date(2026, 4, 1),
            ShiftSlot.shift_label == MOBILE_TODAY_SHIFT_LABEL,
        )
        .first()
    )
    if slot is None:
        slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project_id,
            work_date=date(2026, 4, 1),
            start_time=time(9, 0),
            end_time=time(18, 0),
            shift_label=MOBILE_TODAY_SHIFT_LABEL,
            required_count=1,
            notes=MOBILE_SHIFT_NOTE,
        )
        session.add(slot)
        session.flush()
    else:
        slot.start_time = time(9, 0)
        slot.end_time = time(18, 0)
        slot.required_count = 1
        slot.notes = MOBILE_SHIFT_NOTE
    return slot


def ensure_mobile_pending_slot(session, project_id: str):
    slot = (
        session.query(ShiftSlot)
        .filter(
            ShiftSlot.project_id == project_id,
            ShiftSlot.work_date == date(2026, 4, 3),
            ShiftSlot.shift_label == MOBILE_PENDING_SHIFT_LABEL,
        )
        .first()
    )
    if slot is None:
        slot = ShiftSlot(
            id=generate_ulid(),
            project_id=project_id,
            work_date=date(2026, 4, 3),
            start_time=time(10, 0),
            end_time=time(19, 0),
            shift_label=MOBILE_PENDING_SHIFT_LABEL,
            required_count=1,
            notes=MOBILE_SHIFT_NOTE,
        )
        session.add(slot)
        session.flush()
    else:
        slot.start_time = time(10, 0)
        slot.end_time = time(19, 0)
        slot.required_count = 1
        slot.notes = MOBILE_SHIFT_NOTE
    return slot


def ensure_assignment_response_assignment(session, slot_id: str, worker_id: str, role_id: str):
    assignment = (
        session.query(Assignment)
        .filter(Assignment.shift_slot_id == slot_id, Assignment.worker_id == worker_id)
        .first()
    )
    if assignment is None:
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=slot_id,
            worker_id=worker_id,
            role_id=role_id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
            worker_response_requested_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        )
        session.add(assignment)
        session.flush()
    else:
        assignment.role_id = role_id
        assignment.status = AssignmentStatus.CONFIRMED.value
        assignment.worker_response_status = AssignmentWorkerResponseStatus.PENDING.value
        assignment.worker_response_requested_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
        assignment.worker_response_at = None
        assignment.worker_response_note = None
    return assignment


def ensure_assignment_ops_assignment(session, slot_id: str, worker_id: str, role_id: str):
    assignment = (
        session.query(Assignment)
        .filter(Assignment.shift_slot_id == slot_id, Assignment.worker_id == worker_id)
        .first()
    )
    if assignment is None:
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=slot_id,
            worker_id=worker_id,
            role_id=role_id,
            status=AssignmentStatus.CONFIRMED.value,
            cancel_reason=None,
            worker_response_status=AssignmentWorkerResponseStatus.ACCEPTED.value,
            locked_price_sales=Decimal("32100.00"),
            locked_price_outsource=Decimal("21000.00"),
        )
        session.add(assignment)
        session.flush()
    else:
        assignment.role_id = role_id
        assignment.status = AssignmentStatus.CONFIRMED.value
        assignment.cancel_reason = None
        assignment.worker_response_status = AssignmentWorkerResponseStatus.ACCEPTED.value
        assignment.worker_response_requested_at = None
        assignment.worker_response_at = None
        assignment.worker_response_note = None
        assignment.locked_price_sales = Decimal("32100.00")
        assignment.locked_price_outsource = Decimal("21000.00")
    return assignment


def ensure_mobile_today_assignment(session, slot_id: str, worker_id: str, role_id: str):
    assignment = (
        session.query(Assignment)
        .filter(Assignment.shift_slot_id == slot_id, Assignment.worker_id == worker_id)
        .first()
    )
    if assignment is None:
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=slot_id,
            worker_id=worker_id,
            role_id=role_id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.ACCEPTED.value,
            worker_response_requested_at=datetime(2026, 3, 30, 9, 0, tzinfo=timezone.utc),
            worker_response_at=datetime(2026, 3, 30, 10, 0, tzinfo=timezone.utc),
            worker_response_note="スモーク用に参加可で返信済み",
        )
        session.add(assignment)
        session.flush()
    else:
        assignment.role_id = role_id
        assignment.status = AssignmentStatus.CONFIRMED.value
        assignment.cancel_reason = None
        assignment.worker_response_status = AssignmentWorkerResponseStatus.ACCEPTED.value
        assignment.worker_response_requested_at = datetime(2026, 3, 30, 9, 0, tzinfo=timezone.utc)
        assignment.worker_response_at = datetime(2026, 3, 30, 10, 0, tzinfo=timezone.utc)
        assignment.worker_response_note = "スモーク用に参加可で返信済み"
    return assignment


def ensure_mobile_pending_assignment(session, slot_id: str, worker_id: str, role_id: str):
    assignment = (
        session.query(Assignment)
        .filter(Assignment.shift_slot_id == slot_id, Assignment.worker_id == worker_id)
        .first()
    )
    if assignment is None:
        assignment = Assignment(
            id=generate_ulid(),
            shift_slot_id=slot_id,
            worker_id=worker_id,
            role_id=role_id,
            status=AssignmentStatus.CONFIRMED.value,
            worker_response_status=AssignmentWorkerResponseStatus.PENDING.value,
            worker_response_requested_at=datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc),
            worker_response_note=None,
        )
        session.add(assignment)
        session.flush()
    else:
        assignment.role_id = role_id
        assignment.status = AssignmentStatus.CONFIRMED.value
        assignment.cancel_reason = None
        assignment.worker_response_status = AssignmentWorkerResponseStatus.PENDING.value
        assignment.worker_response_requested_at = datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc)
        assignment.worker_response_at = None
        assignment.worker_response_note = None
    return assignment


def reset_mobile_today_actual(session, assignment_id: str):
    session.query(Actual).filter(Actual.assignment_id == assignment_id).delete(synchronize_session=False)


def ensure_mobile_availability(session, worker_id: str):
    entry = (
        session.query(WorkerAvailability)
        .filter(
            WorkerAvailability.worker_id == worker_id,
            WorkerAvailability.availability_date == date(2026, 4, 10),
        )
        .first()
    )
    if entry is None:
        entry = WorkerAvailability(
            id=generate_ulid(),
            worker_id=worker_id,
            availability_date=date(2026, 4, 10),
            status=AvailabilityStatus.UNDECIDED.value,
            notes=MOBILE_AVAILABILITY_NOTE,
        )
        session.add(entry)
        session.flush()
    else:
        entry.status = AvailabilityStatus.UNDECIDED.value
        entry.notes = MOBILE_AVAILABILITY_NOTE
    return entry


def ensure_mobile_expense(session, project_id: str, worker_id: str):
    expense = session.query(Expense).filter(Expense.notes == MOBILE_EXPENSE_NOTE).first()
    if expense is None:
        expense = Expense(
            id=generate_ulid(),
            project_id=project_id,
            worker_id=worker_id,
            expense_date=date(2026, 4, 1),
            category="交通費",
            amount=Decimal("980.00"),
            description="スモーク用既存経費",
            status="pending",
            target_invoice=False,
            target_payout=True,
            notes=MOBILE_EXPENSE_NOTE,
        )
        session.add(expense)
        session.flush()
    else:
        expense.project_id = project_id
        expense.worker_id = worker_id
        expense.expense_date = date(2026, 4, 1)
        expense.category = "交通費"
        expense.amount = Decimal("980.00")
        expense.description = "スモーク用既存経費"
        expense.status = "pending"
        expense.target_invoice = False
        expense.target_payout = True
        expense.notes = MOBILE_EXPENSE_NOTE
    return expense


def ensure_payout(session, worker_id: str, project_id: str):
    payout = session.query(Payout).filter(Payout.notes == PAYOUT_NOTE, Payout.period_key == PERIOD_KEY).first()
    if payout is None:
        payout = Payout(
            id=generate_ulid(),
            worker_id=worker_id,
            project_id=project_id,
            period_key=PERIOD_KEY,
            payment_date=date(2026, 2, 28),
            status=PayoutStatus.APPROVED.value,
            version=1,
            total_amount=Decimal("12345.00"),
            notes=PAYOUT_NOTE,
        )
        session.add(payout)
        session.flush()
    else:
        payout.worker_id = worker_id
        payout.project_id = project_id
        payout.payment_date = date(2026, 2, 28)
        payout.status = PayoutStatus.APPROVED.value
        payout.version = 1
        payout.total_amount = Decimal("12345.00")
        payout.notes = PAYOUT_NOTE
    return payout


def ensure_audit_log(session, payout_id: str, project_id: str):
    log = (
        session.query(AuditLog)
        .filter(
            AuditLog.action == AuditAction.PAYOUT_DELIVERY_SENT.value,
            AuditLog.target_type == "payout",
            AuditLog.target_id == payout_id,
            AuditLog.reason == AUDIT_REASON,
        )
        .first()
    )

    extra_metadata = {
        "period_key": PERIOD_KEY,
        "project_id": project_id,
        "recipient_email": DELIVERY_RECIPIENT,
        "delivery_note": DELIVERY_NOTE,
        "internal_note": INTERNAL_NOTE,
        "provider": "smtp",
        "status": "sent",
    }
    after_value = {
        "status": "sent",
        "recipient_email": DELIVERY_RECIPIENT,
        "delivery_note": DELIVERY_NOTE,
    }

    if log is None:
        log = AuditLog(
            id=generate_ulid(),
            action=AuditAction.PAYOUT_DELIVERY_SENT.value,
            target_type="payout",
            target_id=payout_id,
            actor="admin_web_smoke",
            actor_role="admin",
            after_value=after_value,
            reason=AUDIT_REASON,
            extra_metadata=extra_metadata,
            created_at=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
        )
        session.add(log)
    else:
        log.actor = "admin_web_smoke"
        log.actor_role = "admin"
        log.after_value = after_value
        log.reason = AUDIT_REASON
        log.extra_metadata = extra_metadata
        log.created_at = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


def ensure_payout_delivery(session, payout_id: str):
    delivery = (
        session.query(PayoutDelivery)
        .filter(
            PayoutDelivery.payout_id == payout_id,
            PayoutDelivery.recipient_email == DELIVERY_RECIPIENT,
            PayoutDelivery.delivery_note == DELIVERY_NOTE,
        )
        .first()
    )

    if delivery is None:
        delivery = PayoutDelivery(
            id=generate_ulid(),
            payout_id=payout_id,
            recipient_email=DELIVERY_RECIPIENT,
            status="sent",
            provider="smtp",
            delivered_by="admin_web_smoke",
            delivery_note=DELIVERY_NOTE,
            internal_note=INTERNAL_NOTE,
            sent_at=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
        )
        session.add(delivery)
    else:
        delivery.status = "sent"
        delivery.provider = "smtp"
        delivery.delivered_by = "admin_web_smoke"
        delivery.delivery_note = DELIVERY_NOTE
        delivery.internal_note = INTERNAL_NOTE
        delivery.sent_at = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


def main() -> None:
    session = SessionLocal()
    try:
        client = ensure_client(session)
        project = ensure_project(session, client.id)
        mobile_project = ensure_mobile_project(session, client.id)
        worker = ensure_worker(session)
        response_worker = ensure_assignment_response_worker(session)
        ops_worker = ensure_assignment_ops_worker(session)
        mobile_worker = ensure_mobile_worker(session)
        response_role = ensure_response_role(session)
        ops_role = ensure_assignment_ops_role(session)
        mobile_role = ensure_mobile_role(session)
        response_slot = ensure_assignment_response_slot(session, project.id)
        ops_slot = ensure_assignment_ops_slot(session, project.id)
        mobile_today_slot = ensure_mobile_today_slot(session, mobile_project.id)
        mobile_pending_slot = ensure_mobile_pending_slot(session, mobile_project.id)
        response_assignment = ensure_assignment_response_assignment(session, response_slot.id, response_worker.id, response_role.id)
        ops_assignment = ensure_assignment_ops_assignment(session, ops_slot.id, ops_worker.id, ops_role.id)
        mobile_today_assignment = ensure_mobile_today_assignment(session, mobile_today_slot.id, mobile_worker.id, mobile_role.id)
        mobile_pending_assignment = ensure_mobile_pending_assignment(session, mobile_pending_slot.id, mobile_worker.id, mobile_role.id)
        reset_mobile_today_actual(session, mobile_today_assignment.id)
        ensure_mobile_availability(session, mobile_worker.id)
        ensure_mobile_expense(session, mobile_project.id, mobile_worker.id)
        payout = ensure_payout(session, worker.id, project.id)
        ensure_payout_delivery(session, payout.id)
        ensure_audit_log(session, payout.id, project.id)
        session.commit()
        print(f"browser_smoke_project={project.code}")
        print(f"browser_smoke_mobile_project={mobile_project.code}")
        print(f"browser_smoke_payout={payout.id}")
        print(f"browser_smoke_assignment_response_assignment={response_assignment.id}")
        print(f"browser_smoke_assignment_ops_assignment={ops_assignment.id}")
        print(f"browser_smoke_mobile_today_assignment={mobile_today_assignment.id}")
        print(f"browser_smoke_mobile_pending_assignment={mobile_pending_assignment.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()