"""add ocr receipt tables

Revision ID: 20260411a001
Revises: 20260409a001
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260411a001"
down_revision: Union[str, None] = "20260409a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ocr_parse_jobs",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_by", sa.String(length=100), nullable=True),
        sa.Column("raw_ocr_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ocr_source_images",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_key", sa.String(length=6), nullable=True),
        sa.Column("parse_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("uploaded_by", sa.String(length=100), nullable=True),
        sa.Column("last_job_id", sa.String(length=26), sa.ForeignKey("ocr_parse_jobs.id"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_ocr_source_images_sha256"),
    )
    op.create_index("ix_ocr_source_images_source_type", "ocr_source_images", ["source_type"], unique=False)
    op.create_index("ix_ocr_source_images_period_key", "ocr_source_images", ["period_key"], unique=False)
    op.create_index("ix_ocr_source_images_parse_status", "ocr_source_images", ["parse_status"], unique=False)

    op.create_table(
        "ocr_extracted_rows",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("source_image_id", sa.String(length=26), sa.ForeignKey("ocr_source_images.id"), nullable=False),
        sa.Column("parse_job_id", sa.String(length=26), sa.ForeignKey("ocr_parse_jobs.id"), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("period_key", sa.String(length=6), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("record_time", sa.String(length=8), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="JPY"),
        sa.Column("transaction_no", sa.String(length=20), nullable=True),
        sa.Column("receipt_no", sa.String(length=20), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("terminal_id", sa.String(length=100), nullable=True),
        sa.Column("cash_sales", sa.Numeric(15, 2), nullable=True),
        sa.Column("credit_sales", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=True),
        sa.Column("tax_included", sa.Numeric(15, 2), nullable=True),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=True),
        sa.Column("store_name", sa.String(length=200), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_review"),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("project_id", sa.String(length=26), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("linked_entity_type", sa.String(length=50), nullable=True),
        sa.Column("linked_entity_id", sa.String(length=26), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_extracted_rows_period_key", "ocr_extracted_rows", ["period_key"], unique=False)
    op.create_index("ix_ocr_extracted_rows_source_type", "ocr_extracted_rows", ["source_type"], unique=False)
    op.create_index("ix_ocr_extracted_rows_status", "ocr_extracted_rows", ["status"], unique=False)
    op.create_index(
        "ix_ocr_extracted_rows_transaction_receipt",
        "ocr_extracted_rows",
        ["transaction_no", "receipt_no"],
        unique=False,
    )

    op.create_table(
        "ocr_monthly_exports",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("period_key", sa.String(length=6), nullable=False),
        sa.Column("export_type", sa.String(length=50), nullable=False, server_default="all"),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("generated_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_monthly_exports_period_key", "ocr_monthly_exports", ["period_key"], unique=False)

    op.create_table(
        "ocr_reconciliation_batches",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("period_key", sa.String(length=6), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("uploaded_by", sa.String(length=100), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_ocr_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_hq_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_diff_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ocr_reconciliation_results",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("batch_id", sa.String(length=26), sa.ForeignKey("ocr_reconciliation_batches.id"), nullable=False),
        sa.Column("match_status", sa.String(length=30), nullable=False),
        sa.Column("ocr_row_id", sa.String(length=26), sa.ForeignKey("ocr_extracted_rows.id"), nullable=True),
        sa.Column("hq_row_index", sa.Integer(), nullable=True),
        sa.Column("hq_payload", sa.JSON(), nullable=True),
        sa.Column("amount_diff", sa.Numeric(15, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_reconciliation_results_batch_id", "ocr_reconciliation_results", ["batch_id"], unique=False)
    op.create_index(
        "ix_ocr_reconciliation_results_match_status",
        "ocr_reconciliation_results",
        ["match_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ocr_reconciliation_results_match_status", table_name="ocr_reconciliation_results")
    op.drop_index("ix_ocr_reconciliation_results_batch_id", table_name="ocr_reconciliation_results")
    op.drop_table("ocr_reconciliation_results")
    op.drop_table("ocr_reconciliation_batches")
    op.drop_index("ix_ocr_monthly_exports_period_key", table_name="ocr_monthly_exports")
    op.drop_table("ocr_monthly_exports")
    op.drop_index("ix_ocr_extracted_rows_transaction_receipt", table_name="ocr_extracted_rows")
    op.drop_index("ix_ocr_extracted_rows_status", table_name="ocr_extracted_rows")
    op.drop_index("ix_ocr_extracted_rows_source_type", table_name="ocr_extracted_rows")
    op.drop_index("ix_ocr_extracted_rows_period_key", table_name="ocr_extracted_rows")
    op.drop_table("ocr_extracted_rows")
    op.drop_index("ix_ocr_source_images_parse_status", table_name="ocr_source_images")
    op.drop_index("ix_ocr_source_images_period_key", table_name="ocr_source_images")
    op.drop_index("ix_ocr_source_images_source_type", table_name="ocr_source_images")
    op.drop_table("ocr_source_images")
    op.drop_table("ocr_parse_jobs")
