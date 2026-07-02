"""OCR receipt parsing models."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, SoftDeleteMixin, generate_ulid


class OcrSourceImage(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ocr_source_images"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_key: Mapped[str | None] = mapped_column(String(6), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_job_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("ocr_parse_jobs.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("sha256", name="uq_ocr_source_images_sha256"),
        Index("ix_ocr_source_images_source_type", "source_type"),
        Index("ix_ocr_source_images_period_key", "period_key"),
        Index("ix_ocr_source_images_parse_status", "parse_status"),
    )


class OcrParseJob(Base, TimestampMixin):
    __tablename__ = "ocr_parse_jobs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_ocr_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OcrExtractedRow(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ocr_extracted_rows"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    source_image_id: Mapped[str] = mapped_column(String(26), ForeignKey("ocr_source_images.id"), nullable=False)
    parse_job_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("ocr_parse_jobs.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_key: Mapped[str | None] = mapped_column(String(6), nullable=True)
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    record_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="JPY")
    transaction_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    receipt_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    terminal_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cash_sales: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    credit_sales: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    transaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_included: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    amount_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amount_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    datetime_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confirm_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    manually_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review")
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("projects.id"), nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    linked_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linked_entity_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- paygate_settlement 専用項目（計画書 v4） -----------------------------
    # 端末識別番号（レシート印字値。既存 terminal_id はUUID形式の正式ID）
    terminal_short_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # PAYGATE POS（カード・交通系IC・QR決済の合算）。既存 credit_sales とは別項目。
    pos_sales: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    other_payment: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    cash_unit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pos_unit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 稼働日（深夜またぎ時は精算日の前日。src.services.ocr.work_date 参照）
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # resolved | ambiguous | invalid | manual
    unit_breakdown_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    amount_ones_digit_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # OCR確定をブロックする致命的エラー（confirm_rows で参照）
    blocking_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # OCR確定はブロックしないが要確認な事項
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 意味的重複候補（画像SHA256とは別に、抽出値の一致で検知）
    duplicate_receipt_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # OCR行としては有効(confirmed)だが、在庫照合には使わない場合に false へ変更
    # (opt-out方式。デフォルトtrue = 原則すべて在庫照合対象として採用)
    reconciliation_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluded_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # OCR確定済みの行を後から無効化した場合（誤アップロード・誤確定等）
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    staff_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source_image: Mapped[OcrSourceImage] = relationship("OcrSourceImage", foreign_keys=[source_image_id])

    __table_args__ = (
        Index("ix_ocr_extracted_rows_period_key", "period_key"),
        Index("ix_ocr_extracted_rows_source_type", "source_type"),
        Index("ix_ocr_extracted_rows_status", "status"),
        Index("ix_ocr_extracted_rows_transaction_receipt", "transaction_no", "receipt_no"),
        Index("ix_ocr_extracted_rows_work_date", "work_date"),
        Index("ix_ocr_extracted_rows_terminal_short_id", "terminal_short_id"),
        # 同一キー(branch_id x terminal_short_id x work_date)で在庫照合対象となる
        # confirmed行は最大1件までとするDB側の安全網（計画書 v4 §2.3/§6.4）。
        # branch_id は未割当時 "UNASSIGNED"（settlement_processing.DEFAULT_BRANCH_ID）を
        # 入れることでNULLの一意性除外問題を回避する。
        Index(
            "uq_ocr_settlement_reconciliation_target",
            "branch_id",
            "terminal_short_id",
            "work_date",
            unique=True,
            postgresql_where=text(
                "source_type = 'paygate_settlement' AND status = 'confirmed' "
                "AND reconciliation_eligible = true AND voided_at IS NULL "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "source_type = 'paygate_settlement' AND status = 'confirmed' "
                "AND reconciliation_eligible = 1 AND voided_at IS NULL "
                "AND deleted_at IS NULL"
            ),
        ),
    )


class OcrMonthlyExport(Base, TimestampMixin):
    __tablename__ = "ocr_monthly_exports"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)
    export_type: Mapped[str] = mapped_column(String(50), nullable=False, default="all")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_ocr_monthly_exports_period_key", "period_key"),
    )


class OcrReconciliationBatch(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ocr_reconciliation_batches"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    period_key: Mapped[str | None] = mapped_column(String(6), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    column_mapping: Mapped[dict] = mapped_column(JSON, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_ocr_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_hq_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_diff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OcrReconciliationResult(Base, TimestampMixin):
    __tablename__ = "ocr_reconciliation_results"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    batch_id: Mapped[str] = mapped_column(String(26), ForeignKey("ocr_reconciliation_batches.id"), nullable=False)
    match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    ocr_row_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("ocr_extracted_rows.id"), nullable=True)
    hq_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hq_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    amount_diff: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ocr_reconciliation_results_batch_id", "batch_id"),
        Index("ix_ocr_reconciliation_results_match_status", "match_status"),
    )
