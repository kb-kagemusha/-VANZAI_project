"""Regressions reproduced during the workspace review; temporary SQLite only."""
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from src.models.transaction import Actual, Invoice, Closing, Payout, InvoiceLine
from src.models.master import User
from src.exceptions import ValidationException, ClosingViolationException
from src.services import invoice_service, payout_service, closing
from src.services.csv_import import CsvImportService
from src.services.closing_approval import request_operation, approve_operation
from tests.test_invoice_payout import TestInvoiceGeneration


def seeded(db):
    TestInvoiceGeneration().test_generate_invoice_basic(db)
    return db.scalars(select(Actual)).one(), db.scalars(select(Invoice)).one()


def users(db):
    first = User(username="requester", email="requester@example.com", role="admin", is_active=True)
    second = User(username="approver", email="approver@example.com", role="admin", is_active=True)
    db.add_all([first, second]); db.flush()
    return first, second


def test_hours_use_billable_and_csv_hours_only(db_session):
    actual, original = seeded(db_session)
    actual.calc_minutes_total = 540; actual.calc_minutes_billable = 480; actual.calc_minutes_break = 60
    new = invoice_service.generate_invoice(db_session, original.client_id, original.project_id, "202601", date(2026,2,1), "test")
    assert new.subtotal == Decimal("12000")
    payout = payout_service.generate_payout(db_session, actual.worker_id, actual.project_id, "202601", date(2026,2,1), "test")
    assert payout.total_amount == Decimal("9600")
    actual.calc_minutes_total = 0
    another = invoice_service.generate_invoice(db_session, original.client_id, original.project_id, "202601", date(2026,2,1), "test")
    assert another.subtotal == Decimal("12000")


def test_draft_regeneration_retains_header_and_lines(db_session):
    actual, first = seeded(db_session)
    old_lines = list(first.lines)
    new = invoice_service.generate_invoice(db_session, first.client_id, first.project_id, "202601", date(2026,2,1), "test")
    assert first.deleted_at is not None and new.id != first.id
    assert db_session.get(InvoiceLine, old_lines[0].id).invoice_id == first.id
    with pytest.raises(ValidationException):
        invoice_service.issue_invoice(db_session, first.id, "test")


def test_fixed_invoice_and_payout_cannot_be_generated_again(db_session):
    actual, invoice = seeded(db_session)
    invoice_service.issue_invoice(db_session, invoice.id, "test")
    with pytest.raises(ValidationException):
        invoice_service.generate_invoice(db_session, invoice.client_id, invoice.project_id, "202601", date(2026,2,1), "test")
    payout = payout_service.generate_payout(db_session, actual.worker_id, actual.project_id, "202601", date(2026,2,1), "test")
    payout_service.approve_payout(db_session, payout.id, "test")
    with pytest.raises(ValidationException):
        payout_service.generate_payout(db_session, actual.worker_id, actual.project_id, "202601", date(2026,2,1), "test")


@pytest.mark.parametrize("fixed", ["soft_closed", "hard_closed", "issued"])
def test_fixed_period_rejects_csv_without_changing_actuals(db_session, fixed):
    actual, invoice = seeded(db_session)
    if fixed == "issued": invoice_service.issue_invoice(db_session, invoice.id, "test")
    else: db_session.add(Closing(project_id=actual.project_id, period_key="202601", status=fixed, release_count=0))
    db_session.flush()
    csv = f"worker_id,role_id,work_date,start_time,end_time,break_minutes\n{actual.worker_id},{actual.role_id},2026-01-10,09:00,17:00,60\n"
    with pytest.raises(ValidationException): CsvImportService(db_session).import_csv(csv,"temporary.csv",actual.project_id,"202601")
    assert actual.status == "active"


def test_reissue_copies_lines_and_address_snapshots(db_session):
    actual, old = seeded(db_session)
    old.addressee_name = "Snapshot"; old.addressee_address = "Recorded address"
    invoice_service.issue_invoice(db_session, old.id, "test")
    new = invoice_service.reissue_invoice(db_session, old.id, "test")
    db_session.flush()
    assert len(new.lines) == len(old.lines) == 1
    assert new.lines[0].actual_id == old.lines[0].actual_id
    assert new.lines[0].quantity_snapshot == old.lines[0].quantity_snapshot
    assert new.addressee_name == old.addressee_name and new.addressee_address == old.addressee_address


def test_second_person_approval_is_required_and_cannot_replay(db_session):
    actual, _ = seeded(db_session)
    first, second = users(db_session)
    closing.soft_close(db_session, actual.project_id,"202601",first.username)
    with pytest.raises(ClosingViolationException):
        closing.release_soft_close(db_session,actual.project_id,"202601",first.username,"invented","reason")
    request = request_operation(db_session, actual.project_id,"202601","soft_release",first,"reason")
    with pytest.raises(ClosingViolationException): approve_operation(db_session,request.id,first)
    result = approve_operation(db_session, request.id, second)
    assert result.status == "open" and request.approved_by == second.id
    with pytest.raises(ClosingViolationException): approve_operation(db_session,request.id,second)


def test_csv_cannot_bypass_closing_using_another_period(db_session):
    actual, invoice = seeded(db_session)
    db_session.add(Closing(project_id=actual.project_id, period_key="202601", status="hard_closed", release_count=0))
    db_session.flush()
    csv = f"worker_id,role_id,work_date,start_time,end_time,break_minutes\n{actual.worker_id},{actual.role_id},2026-01-10,09:00,17:00,60\n"
    with pytest.raises(ValidationException): CsvImportService(db_session).import_csv(csv,"wrong-period.csv",actual.project_id,"202602")
    assert actual.status == "active"
