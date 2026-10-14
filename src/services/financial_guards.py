"""Common locks and fixed-document guards for imports and billing."""
from datetime import datetime, timezone
import re

from sqlalchemy import select

from src.exceptions import ValidationException
from src.models.transaction import Actual, Closing, Invoice, InvoiceLine, Payout, PayoutLine, Project, Expense, Incentive
from src.services.audit import AuditService


def lock_projects(session, project_ids):
    ids = sorted(set(project_ids))
    if not ids:
        return
    # Project rows exist before the first closing or document. All financial
    # mutations lock them in the same order, including on PostgreSQL.
    session.execute(select(Project).where(Project.id.in_(ids)).order_by(Project.id)
                    .with_for_update().execution_options(populate_existing=True)).scalars().all()


def lock_client_projects(session, client_id):
    lock_all_projects(session)


def lock_all_projects(session):
    # Supplier and staff payouts can aggregate many projects. Locking the same
    # existing rows avoids gaps when recipient membership changes mid-operation.
    lock_projects(session, session.scalars(select(Project.id)).all())


def ensure_import_mutable(session, project_id, period_key):
    if not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])", period_key):
        raise ValidationException("対象月をYYYYMMで指定してください")
    lock_projects(session, [project_id])
    state = session.scalar(select(Closing.status).where(
        Closing.project_id == project_id, Closing.period_key == period_key))
    if state and state != "open":
        raise ValidationException("締め済みの期間にはCSVを取り込めません。承認済みの解除手順を使用してください。")
    ids = session.scalars(select(Actual.id).where(
        Actual.project_id == project_id, Actual.period_key == period_key)).all()
    ensure_unallocated(session, ids, "invoice")
    ensure_unallocated(session, ids, "payout")


def ensure_unallocated(session, actual_ids, kind, exclude_document_ids=()):
    ids = list(set(actual_ids))
    if not ids:
        return
    book, line, fk = (Invoice, InvoiceLine, InvoiceLine.invoice_id) if kind == "invoice" else (Payout, PayoutLine, PayoutLine.payout_id)
    fixed = ("issued", "closed") if kind == "invoice" else ("approved", "paid", "closed")
    query = select(line.id).join(book, fk == book.id).where(
        line.actual_id.in_(ids), book.deleted_at.is_(None), book.status.in_(fixed))
    if exclude_document_ids:
        query = query.where(book.id.not_in(exclude_document_ids))
    if session.scalar(query.limit(1)):
        raise ValidationException("発行済みの請求書または承認済みの支払明細に含まれる実績を再計上・変更できません。訂正手順を使用してください。")


def ancestor_ids(session, document, model, parent_field):
    result = [document.id]
    parent = getattr(document, parent_field)
    while parent and parent not in result:
        result.append(parent)
        row = session.get(model, parent)
        parent = getattr(row, parent_field) if row else None
    return result


def archive_drafts(session, documents, kind):
    # Keep headers and lines for investigation instead of physically deleting
    # parents whose non-null child keys prevent safe regeneration.
    for document in documents:
        for model in (Expense, Incentive):
            field = getattr(model, "target_invoice_id" if kind == "invoice" else "target_payout_id")
            for item in session.scalars(select(model).where(field == document.id)).all():
                setattr(item, field.key, None)
        document.deleted_at = datetime.now(timezone.utc)
        AuditService(session).log(f"{kind}_draft_superseded", target_type=kind,
                                 target_id=document.id, reason="regenerated")
    session.flush()


def copy_lines(session, model, source_id, target_id, foreign_key):
    rows = session.scalars(select(model).where(getattr(model, foreign_key) == source_id)).all()
    for row in rows:
        values = {column.name: getattr(row, column.name) for column in model.__table__.columns
                  if column.name not in {"id", foreign_key, "created_at", "updated_at"}}
        session.add(model(**{foreign_key: target_id}, **values))


def ensure_components_unallocated(session, document, kind):
    book, line, fk = (Invoice, InvoiceLine, InvoiceLine.invoice_id) if kind == "invoice" else (Payout, PayoutLine, PayoutLine.payout_id)
    fixed = ("issued", "closed") if kind == "invoice" else ("approved", "paid", "closed")
    parent_field = "parent_invoice_id" if kind == "invoice" else "parent_payout_id"
    excluded = ancestor_ids(session, document, book, parent_field)
    for component in ("expense_id", "incentive_id"):
        ids = [getattr(row, component) for row in document.lines if getattr(row, component)]
        if ids and session.scalar(select(line.id).join(book, fk == book.id).where(
            getattr(line, component).in_(ids), book.status.in_(fixed), book.deleted_at.is_(None), book.id.not_in(excluded)).limit(1)):
            raise ValidationException("確定済み帳票の経費・インセンティブを再計上できません")
    for row in document.lines:
        if row.actual_id:
            actual = session.get(Actual, row.actual_id, populate_existing=True)
            if not actual or actual.status != "active":
                raise ValidationException("下書き作成後に実績が変わったため、再生成してください")
