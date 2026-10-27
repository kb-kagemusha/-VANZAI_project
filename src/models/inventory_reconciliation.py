"""Inventory reconciliation models (PAYGATE精算 在庫照合).

計画書 v4 Phase 2a に対応。OCR確定済み精算行の通常取引数と、事務局が入力する
実在庫記録（開始/終了在庫・非販売調整）を突合し、差異を検知する。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, SoftDeleteMixin, generate_ulid


class InventorySnapshot(Base, TimestampMixin, SoftDeleteMixin):
    """稼働1件（支社×端末×稼働日）ごとの実在庫記録。

    adjustment_count の符号規約（計画書 v4 §1・レビュー②2.1）:
      - 販売以外の理由で在庫が「減った」場合は正の値
      - 販売以外の理由で在庫が「増えた」場合は負の値
      - 販売相当減数 = opening_count - closing_count - adjustment_count
    """
    __tablename__ = "inventory_snapshots"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    branch_id: Mapped[str] = mapped_column(String(50), nullable=False)
    terminal_short_id: Mapped[str] = mapped_column(String(20), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    staff_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    opening_count: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 承認フローは実装しない（計画書 v4 §2 確定方針）。confirmed_by は entered_by と
    # 同一人物でも可。月次で事務局責任者が adjustment_reason を目視レビューする運用で
    # 事後監査を行う（docs/ops/OCR_INVENTORY_RUNBOOK.md 参照）。
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "branch_id", "terminal_short_id", "work_date",
            name="uq_inventory_snapshots_key",
        ),
        Index("ix_inventory_snapshots_work_date", "work_date"),
    )

    @property
    def inventory_decrease(self) -> int:
        return self.opening_count - self.closing_count - self.adjustment_count


class InventoryReconciliationBatch(Base, TimestampMixin):
    __tablename__ = "inventory_reconciliation_batches"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    period_key: Mapped[str | None] = mapped_column(String(6), nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    executed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adjusted_matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count_mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_only_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inventory_only_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_inventory_reconciliation_batches_period_key", "period_key"),
    )


class InventoryReconciliationResult(Base, TimestampMixin):
    __tablename__ = "inventory_reconciliation_results"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    batch_id: Mapped[str] = mapped_column(String(26), ForeignKey("inventory_reconciliation_batches.id"), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(50), nullable=False)
    terminal_short_id: Mapped[str] = mapped_column(String(20), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    ocr_row_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("ocr_extracted_rows.id"), nullable=True)
    inventory_snapshot_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("inventory_snapshots.id"), nullable=True
    )
    ocr_transaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_decrease: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diff: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # matched | adjusted_matched | count_mismatch | sales_only | inventory_only |
    # excluded | needs_inventory_confirmation | duplicate_candidate
    match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    # ocr_error | inventory_input_error | receipt_missing | image_duplicate |
    # partial_settlement | terminal_mismatch | staff_mismatch | loss_damage | unclassified
    diff_reason_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_inventory_reconciliation_results_batch_id", "batch_id"),
        Index("ix_inventory_reconciliation_results_match_status", "match_status"),
        Index("ix_inventory_reconciliation_results_work_date", "work_date"),
    )
