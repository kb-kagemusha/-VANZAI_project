from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from src.models.enums import ActualStatus, InvoiceStatus, PayoutStatus
from src.models.transaction import Actual, Assignment, ShiftSlot, Project, Invoice, Payout
from src.services import invoice_service, payout_service


@dataclass
class BatchResult:
    generated_invoices: int
    skipped_invoices: int
    failed_invoices: list[dict[str, Any]]
    generated_payouts: int
    skipped_payouts: int
    failed_payouts: list[dict[str, Any]]


def _existing_invoice(session: Session, client_id: str, period_key: str) -> bool:
    stmt = select(Invoice.id).where(
        Invoice.client_id == client_id,
        Invoice.project_id.is_(None),
        Invoice.period_key == period_key,
        Invoice.status != InvoiceStatus.PREPARING,
    ).limit(1)
    return session.execute(stmt).scalar_one_or_none() is not None


def _existing_payout(session: Session, worker_id: str, period_key: str) -> bool:
    stmt = select(Payout.id).where(
        Payout.worker_id == worker_id,
        Payout.project_id.is_(None),
        Payout.period_key == period_key,
        Payout.status != PayoutStatus.PREPARING,
    ).limit(1)
    return session.execute(stmt).scalar_one_or_none() is not None


def generate_monthly_billing(session: Session, period_key: str, user_id: str) -> BatchResult:
    stmt_clients = (
        select(distinct(Project.client_id))
        .join(ShiftSlot, ShiftSlot.project_id == Project.id)
        .join(Assignment, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Actual, Actual.assignment_id == Assignment.id)
        .where(
            Actual.status == ActualStatus.ACTIVE,
            Actual.period_key == period_key,
            Project.client_id.is_not(None),
        )
    )
    client_ids = [row[0] for row in session.execute(stmt_clients).all() if row and row[0]]

    stmt_workers = (
        select(distinct(Assignment.worker_id))
        .join(Actual, Actual.assignment_id == Assignment.id)
        .where(
            Actual.status == ActualStatus.ACTIVE,
            Actual.period_key == period_key,
            Assignment.worker_id.is_not(None),
        )
    )
    worker_ids = [row[0] for row in session.execute(stmt_workers).all() if row and row[0]]

    generated_invoices = 0
    skipped_invoices = 0
    failed_invoices: list[dict[str, Any]] = []

    generated_payouts = 0
    skipped_payouts = 0
    failed_payouts: list[dict[str, Any]] = []

    for client_id in client_ids:
        if _existing_invoice(session, client_id, period_key):
            skipped_invoices += 1
            continue
        try:
            invoice_service.generate_invoice(
                session=session,
                client_id=client_id,
                project_id=None,
                period_key=period_key,
                billing_date=date.today(),
                user_id=user_id,
            )
            generated_invoices += 1
        except Exception as exc:
            failed_invoices.append({"client_id": client_id, "error": str(exc)})

    for worker_id in worker_ids:
        if _existing_payout(session, worker_id, period_key):
            skipped_payouts += 1
            continue
        try:
            payout_service.generate_payout(
                session=session,
                worker_id=worker_id,
                project_id=None,
                period_key=period_key,
                payment_date=date.today(),
                user_id=user_id,
            )
            generated_payouts += 1
        except Exception as exc:
            failed_payouts.append({"worker_id": worker_id, "error": str(exc)})

    return BatchResult(
        generated_invoices=generated_invoices,
        skipped_invoices=skipped_invoices,
        failed_invoices=failed_invoices,
        generated_payouts=generated_payouts,
        skipped_payouts=skipped_payouts,
        failed_payouts=failed_payouts,
    )
