"""依頼書の売上確定と月次請求。稼働者向け単価・実績会計とは別の正本。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin, generate_ulid


class OrderBillingTaxRule(Base):
    __tablename__ = "order_billing_tax_rules"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    rounding: Mapped[str] = mapped_column(String(20), nullable=False)
    __table_args__ = (CheckConstraint("rate >= 0 AND rate <= 1", name="ck_order_billing_tax_rate"),
                     CheckConstraint("rounding = 'floor_yen'", name="ck_order_billing_rounding"))


class OrderBillingIssuer(Base, TimestampMixin):
    """管理者が編集する発行元。請求書は作成時点の内容を別途保持する。"""
    __tablename__ = "order_billing_issuer"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False)
    bank_details: Mapped[str] = mapped_column(Text, nullable=False)
    payment_terms: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (CheckConstraint("id = 'default' AND revision > 0", name="ck_order_billing_issuer_singleton"),)


class OrderBillingAmount(Base):
    """確定履歴は追記のみ。版が変わると新しい金額確認が必要。"""
    __tablename__ = "order_billing_amounts"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    version_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_versions.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[str] = mapped_column(String(26), ForeignKey("clients.id"), nullable=False)
    billing_month: Mapped[str] = mapped_column(String(6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    incentive_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("version_id", "revision", name="uq_order_billing_amount_revision"),
                     CheckConstraint("incentive_amount IS NULL OR incentive_amount >= 0", name="ck_order_billing_incentive_amount"),
                     CheckConstraint("amount >= 0 AND revision > 0", name="ck_order_billing_amount"),
                     CheckConstraint("length(billing_month) = 6", name="ck_order_billing_month"),
                     Index("ix_order_billing_amount_client_month", "client_id", "billing_month"))


class OrderBillingInvoice(Base, TimestampMixin):
    __tablename__ = "order_billing_invoices"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    document_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(26), ForeignKey("clients.id"), nullable=False)
    billing_month: Mapped[str] = mapped_column(String(6), nullable=False)
    billing_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_invoice_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("order_billing_invoices.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    client_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    issuer_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    tax_rule_id: Mapped[str] = mapped_column(String(40), ForeignKey("order_billing_tax_rules.id"), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tax_rounding: Mapped[str] = mapped_column(String(20), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    pdf_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (CheckConstraint("status IN ('draft', 'issued', 'cancelled')", name="ck_order_billing_invoice_status"),
                     CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount = subtotal + tax_amount AND version > 0", name="ck_order_billing_invoice_totals"),
                     UniqueConstraint("client_id", "billing_month", "version", name="uq_order_billing_invoice_version"),
                     Index("uq_order_billing_invoice_active", "client_id", "billing_month", unique=True,
                           postgresql_where=text("status <> 'cancelled'"), sqlite_where=text("status <> 'cancelled'")))


class OrderBillingInvoiceLine(Base):
    __tablename__ = "order_billing_invoice_lines"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    invoice_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_billing_invoices.id"), nullable=False)
    amount_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_billing_amounts.id"), nullable=False)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    # 下書き取消時だけ解放。系列単位のDB制約で変更版の二重請求も防ぐ。
    active_series_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("order_request_series.id"), unique=True, nullable=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    document_number: Mapped[str] = mapped_column(String(40), nullable=False)
    work_date_label: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    incentive_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    incentive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("invoice_id", "line_number", name="uq_order_billing_line_number"),
                     CheckConstraint("incentive_amount IS NULL OR (incentive_amount >= 0 AND incentive_amount <= amount)", name="ck_order_billing_line_incentive"),
                     CheckConstraint("amount >= 0 AND line_number > 0", name="ck_order_billing_line"),
                     CheckConstraint("active_series_id IS NULL OR active_series_id = series_id", name="ck_order_billing_line_claim"))
