"""Admin order receivables. Money is never inferred from worker pay or actuals."""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_FLOOR
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.master import Client
from src.models.line_daily import OrderRequestSeries
from src.models.order_request import OrderRequestDocument, OrderRequestVersion
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoice, OrderBillingInvoiceLine, OrderBillingTaxRule, OrderBillingIssuer
from src.services.audit import AuditService
from src.services.document_storage import DocumentStorage
from src.services.order_request_format import parse_sections
from src.services.order_request_service import OrderRequestError
from src.services import worker_schedule as ws


def now():
    return datetime.now(timezone.utc)


def validate_month(value: str):
    if not re.fullmatch(r"[1-9]\d{3}(0[1-9]|1[0-2])", value):
        raise OrderRequestError(400, "請求月をYYYYMMで指定してください")


class OrderBillingService:
    def __init__(self, session: Session):
        self.session = session

    def lock(self):
        # All mutations take the same existing client locks before series locks.
        self.session.execute(select(Client).order_by(Client.id).with_for_update().execution_options(populate_existing=True)).scalars().all()

    def issuer_settings(self):
        row = self.session.get(OrderBillingIssuer, "default")
        if row is None:
            raise OrderRequestError(503, "請求書の発行元設定がありません")
        return row

    def issuer_snapshot(self):
        row = self.issuer_settings()
        return {key: getattr(row, key) for key in ("revision", "name", "postal_code", "address", "registration_number", "bank_details", "payment_terms")}

    def update_issuer(self, *, expected_revision, actor, **values):
        self.session.execute(select(OrderBillingIssuer).where(OrderBillingIssuer.id == "default").with_for_update().execution_options(populate_existing=True)).scalars().all()
        row = self.issuer_settings()
        if row.revision != expected_revision:
            raise OrderRequestError(409, "別の操作で発行元設定が変更されました。開き直して確認してください")
        before = self.issuer_snapshot()
        for key, value in values.items():
            setattr(row, key, value.strip())
        if not row.name:
            raise OrderRequestError(400, "発行元の正式名称を入力してください")
        row.revision += 1
        AuditService(self.session).log("order_billing_issuer_updated", target_type="order_billing_issuer", target_id=row.id,
            actor=actor.username, actor_role=actor.role, before_value=before, after_value=self.issuer_snapshot())
        return row

    def eligible(self):
        return self.session.query(OrderRequestVersion, OrderRequestDocument).join(
            OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id
        ).join(OrderRequestSeries, OrderRequestSeries.answerable_version_id == OrderRequestVersion.id).filter(
            OrderRequestVersion.status == "confirmed", OrderRequestDocument.kind == "formal",
            OrderRequestDocument.deleted_at.is_(None)
        ).order_by(OrderRequestVersion.confirmed_at.desc(), OrderRequestVersion.id).all()

    def latest_amounts(self):
        latest = self.session.query(OrderBillingAmount.version_id, func.max(OrderBillingAmount.revision).label("revision")).group_by(OrderBillingAmount.version_id).subquery()
        return {r.version_id: r for r in self.session.query(OrderBillingAmount).join(latest,
            (OrderBillingAmount.version_id == latest.c.version_id) & (OrderBillingAmount.revision == latest.c.revision)).all()}

    def rows(self):
        amounts = self.latest_amounts()
        clients = {c.id: c for c in self.session.query(Client).all()}
        claims = {l.series_id: l for l in self.session.query(OrderBillingInvoiceLine).filter(OrderBillingInvoiceLine.active_series_id.is_not(None)).all()}
        result = []
        for version, document in self.eligible():
            amount = amounts.get(version.id)
            claim = claims.get(version.series_id)
            client_id = amount.client_id if amount else version.internal_client_id
            client = clients.get(client_id)
            sections = parse_sections(version.request_conditions) or {}
            result.append({"version_id": version.id, "series_id": version.series_id, "document_number": document.document_number,
                "version_no": version.version_no, "project_name": sections.get("project_name", ""), "work_date_label": version.work_date_label,
                "client_id": client_id, "client_name": client.name if client else "未設定", "revision": amount.revision if amount else 0,
                "amount_id": amount.id if amount else None, "amount": str(amount.amount) if amount else None,
                "billing_month": amount.billing_month if amount else None, "confirmed_at": amount.created_at.isoformat() if amount else None,
                "invoice_id": claim.invoice_id if claim else None,
                "status": "invoice_created" if claim else "confirmed" if amount else "missing"})
        return result

    def save_amount(self, version_id, *, client_id, billing_month, amount, expected_revision, reason, actor):
        validate_month(billing_month)
        self.lock()
        source = self.session.get(OrderRequestVersion, version_id)
        if source is None or not source.series_id:
            raise OrderRequestError(404, "依頼書が見つかりません")
        ws.lock_series(self.session, source.series_id)
        pair = next(((v, d) for v, d in self.eligible() if v.id == version_id), None)
        if pair is None:
            raise OrderRequestError(409, "正式・確定済みの最新依頼書だけ金額を確定できます。一覧を更新してください")
        source, document = pair
        if self.session.query(OrderBillingInvoiceLine).filter_by(active_series_id=source.series_id).first():
            raise OrderRequestError(409, "この依頼は請求書に含まれています。下書きは取り消してから変更してください。発行済みは上書きできません")
        current = self.latest_amounts().get(version_id)
        revision = current.revision if current else 0
        if expected_revision != revision:
            raise OrderRequestError(409, "別の操作で金額が更新されました。一覧を更新して確認してください")
        if current and not reason.strip():
            raise OrderRequestError(400, "金額や請求先・請求月を変更する理由を入力してください")
        client = self.session.get(Client, client_id)
        if client is None or client.deleted_at is not None:
            raise OrderRequestError(400, "有効な請求先を選択してください")
        sections = parse_sections(source.request_conditions) or {}
        row = OrderBillingAmount(version_id=version_id, revision=revision + 1, client_id=client_id,
            billing_month=billing_month, amount=amount, reason=reason.strip(), created_by_user_id=actor.id, created_at=now(),
            snapshot={"document_number": document.document_number, "version_no": source.version_no,
                      "project_name": sections.get("project_name", ""), "work_date_label": source.work_date_label, "client_name": client.name})
        self.session.add(row)
        self.session.flush()
        AuditService(self.session).log("order_billing_amount_confirmed", target_type="order_billing_amount", target_id=row.id,
            actor=actor.username, actor_role=actor.role, reason=row.reason,
            before_value={"amount": str(current.amount), "client_id": current.client_id, "billing_month": current.billing_month} if current else None,
            after_value={"amount": str(amount), "client_id": client_id, "billing_month": billing_month, "version_id": version_id, "revision": row.revision})
        return row

    def get_invoice(self, invoice_id):
        row = self.session.get(OrderBillingInvoice, invoice_id)
        if row is None:
            raise OrderRequestError(404, "請求書が見つかりません")
        return row

    def lines(self, invoice):
        return self.session.query(OrderBillingInvoiceLine).filter_by(invoice_id=invoice.id).order_by(OrderBillingInvoiceLine.line_number).all()

    def generate(self, *, client_id, billing_month, billing_date, actor):
        validate_month(billing_month)
        self.lock()
        client = self.session.get(Client, client_id)
        if client is None or client.deleted_at is not None:
            raise OrderRequestError(400, "有効な請求先を選んでください")
        from src.models.transaction import Invoice
        if self.session.query(Invoice.id).filter(Invoice.client_id == client_id, Invoice.period_key == billing_month,
                Invoice.deleted_at.is_(None), Invoice.document_type == "invoice").first():
            raise OrderRequestError(409, "同じ請求先・請求月に実績から作成した請求書があります。二重請求を防ぐため、請求経路を確認してください")
        existing = self.session.query(OrderBillingInvoice).filter_by(client_id=client_id, billing_month=billing_month).order_by(OrderBillingInvoice.version.desc()).first()
        if existing and existing.status == "draft":
            return existing  # Retry cannot create another draft or add more lines.
        if existing and existing.status == "issued":
            raise OrderRequestError(409, "この請求先・請求月は発行済みです。追加や訂正の請求が必要なため、同じ月の請求書は上書きできません")
        rows = [r for r in self.rows() if r["client_id"] == client_id and r["billing_month"] == billing_month and r["amount_id"]]
        if not rows:
            raise OrderRequestError(400, "この請求先・請求月に金額確定済みの依頼がありません")
        if any(r["invoice_id"] for r in rows):
            raise OrderRequestError(409, "既に別の請求書に含まれている依頼があります。二重には請求できません")
        for series_id in sorted(r["series_id"] for r in rows):
            ws.lock_series(self.session, series_id)
        # A revision/cancellation may have committed while waiting for a series lock.
        latest = {r["version_id"]: r for r in self.rows()}
        if any(r["version_id"] not in latest or latest[r["version_id"]]["amount_id"] != r["amount_id"] for r in rows):
            raise OrderRequestError(409, "依頼内容が変わりました。一覧を更新してください")
        rule = self.session.get(OrderBillingTaxRule, "standard-10-floor-v1")
        if rule is None:
            raise OrderRequestError(503, "消費税ルールが未設定です")
        identifier = generate_ulid()
        invoice = OrderBillingInvoice(id=identifier, document_number=f"OB-{billing_month}-{identifier}", client_id=client_id,
            billing_month=billing_month, billing_date=billing_date, version=existing.version + 1 if existing else 1,
            parent_invoice_id=existing.id if existing else None, status="draft", client_snapshot={"name": client.name, "address": client.address or ""},
            issuer_snapshot=self.issuer_snapshot(),
            tax_rule_id=rule.id, tax_rate=rule.rate, tax_rounding=rule.rounding, subtotal=Decimal(0), tax_amount=Decimal(0), total_amount=Decimal(0), created_by_user_id=actor.id)
        self.session.add(invoice)
        self.session.flush()
        for index, row in enumerate(sorted(rows, key=lambda r: r["document_number"]), 1):
            self.session.add(OrderBillingInvoiceLine(invoice_id=invoice.id, amount_id=row["amount_id"], series_id=row["series_id"],
                active_series_id=row["series_id"], line_number=index, description=row["project_name"] or "案件", document_number=row["document_number"],
                work_date_label=row["work_date_label"], amount=Decimal(row["amount"])))
        self.session.flush()
        invoice.subtotal = sum((line.amount for line in self.lines(invoice)), Decimal(0))
        invoice.tax_amount = (invoice.subtotal * invoice.tax_rate).quantize(Decimal("1"), rounding=ROUND_FLOOR)
        invoice.total_amount = invoice.subtotal + invoice.tax_amount
        self.session.flush()
        self.store_pdf(invoice)
        self.audit_invoice("order_billing_invoice_created", invoice, actor)
        return invoice

    def store_pdf(self, invoice):
        from src.services.order_billing_pdf import generate_pdf
        key = f"order_billing/{invoice.billing_month}/{invoice.id}/v{invoice.version}-{invoice.status}-{generate_ulid()}.pdf"
        # Each state has its own key. Existing artifacts are never overwritten.
        storage = DocumentStorage()
        if storage.exists(key):
            raise OrderRequestError(409, "同じ版のPDFが既に保管されています。再操作せず管理者へ確認してください")
        invoice.pdf_object_key = storage.save_bytes(key, generate_pdf(invoice, self.lines(invoice)))

    def issue(self, invoice_id, *, actor):
        self.lock()
        invoice = self.get_invoice(invoice_id)
        if invoice.status == "issued":
            return invoice
        if invoice.status != "draft":
            raise OrderRequestError(409, "取消済みの下書きは発行できません")
        lines = self.lines(invoice)
        if invoice.subtotal != sum((line.amount for line in lines), Decimal(0)) or invoice.tax_amount != (invoice.subtotal * invoice.tax_rate).quantize(Decimal("1"), rounding=ROUND_FLOOR):
            raise OrderRequestError(409, "請求明細と合計が一致しません。発行せず管理者へ確認してください")
        for line in sorted(lines, key=lambda l: l.series_id):
            ws.lock_series(self.session, line.series_id)
        current = {r["version_id"]: r for r in self.rows()}
        for line in lines:
            amount = self.session.get(OrderBillingAmount, line.amount_id)
            if amount.version_id not in current or current[amount.version_id]["amount_id"] != amount.id:
                raise OrderRequestError(409, "請求書作成後に依頼が変更・取消されました。下書きを取り消して確認してください")
        # Unallocated new orders for the same client/month must not silently disappear.
        if any(r["client_id"] == invoice.client_id and r["billing_month"] == invoice.billing_month and not r["invoice_id"] for r in current.values()):
            raise OrderRequestError(409, "同じ請求月に追加の金額確定済み依頼があります。下書きを取り消してまとめ直してください")
        invoice.status = "issued"
        invoice.issued_at = now()
        self.store_pdf(invoice)
        self.audit_invoice("order_billing_invoice_issued", invoice, actor)
        return invoice

    def cancel_draft(self, invoice_id, *, reason, actor):
        self.lock()
        invoice = self.get_invoice(invoice_id)
        if invoice.status != "draft":
            raise OrderRequestError(409, "発行済み・取消済みの請求書は変更できません")
        if not reason.strip():
            raise OrderRequestError(400, "下書きを取り消す理由を入力してください")
        invoice.status = "cancelled"
        invoice.cancelled_at = now()
        invoice.cancel_reason = reason.strip()
        for line in self.lines(invoice):
            line.active_series_id = None
        self.session.flush()
        self.audit_invoice("order_billing_invoice_draft_cancelled", invoice, actor, reason)
        return invoice

    def audit_invoice(self, action, invoice, actor, reason=None):
        AuditService(self.session).log(action, target_type="order_billing_invoice", target_id=invoice.id, actor=actor.username,
            actor_role=actor.role, reason=reason, after_value={"document_number": invoice.document_number, "client_id": invoice.client_id,
                "billing_month": invoice.billing_month, "version": invoice.version, "subtotal": str(invoice.subtotal), "tax_amount": str(invoice.tax_amount), "total_amount": str(invoice.total_amount)})
