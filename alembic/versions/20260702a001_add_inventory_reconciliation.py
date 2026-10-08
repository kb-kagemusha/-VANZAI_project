"""Add PAYGATE settlement extended columns and inventory reconciliation tables.

計画書 v4「PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）」Phase 2a に対応。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260702a001"
down_revision: Union[str, None] = "20260616a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = {column["name"] for column in inspector.get_columns("ocr_extracted_rows")}

    def add_col(name: str, column: sa.Column) -> None:
        if name not in existing:
            op.add_column("ocr_extracted_rows", column)

    add_col("terminal_short_id", sa.Column("terminal_short_id", sa.String(length=20), nullable=True))
    add_col("pos_sales", sa.Column("pos_sales", sa.Numeric(15, 2), nullable=True))
    add_col("other_payment", sa.Column("other_payment", sa.Numeric(15, 2), nullable=True))
    add_col("cash_unit_count", sa.Column("cash_unit_count", sa.Integer(), nullable=True))
    add_col("pos_unit_count", sa.Column("pos_unit_count", sa.Integer(), nullable=True))
    add_col("work_date", sa.Column("work_date", sa.Date(), nullable=True))
    add_col("unit_breakdown_status", sa.Column("unit_breakdown_status", sa.String(length=20), nullable=True))
    add_col("unit_breakdown_json", sa.Column("unit_breakdown_json", sa.JSON(), nullable=True))
    add_col("amount_ones_digit_ok", sa.Column("amount_ones_digit_ok", sa.Boolean(), nullable=True))
    add_col("blocking_errors", sa.Column("blocking_errors", sa.JSON(), nullable=True))
    add_col("warnings", sa.Column("warnings", sa.JSON(), nullable=True))
    add_col(
        "duplicate_receipt_candidate",
        sa.Column("duplicate_receipt_candidate", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    add_col(
        "reconciliation_eligible",
        sa.Column("reconciliation_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    add_col("excluded_reason", sa.Column("excluded_reason", sa.String(length=200), nullable=True))
    add_col("voided_at", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    add_col("voided_by", sa.Column("voided_by", sa.String(length=100), nullable=True))
    add_col("void_reason", sa.Column("void_reason", sa.Text(), nullable=True))
    add_col("branch_id", sa.Column("branch_id", sa.String(length=50), nullable=True))
    add_col("staff_id", sa.Column("staff_id", sa.String(length=50), nullable=True))

    existing_indexes = {index["name"] for index in inspector.get_indexes("ocr_extracted_rows")}
    if "ix_ocr_extracted_rows_work_date" not in existing_indexes:
        op.create_index("ix_ocr_extracted_rows_work_date", "ocr_extracted_rows", ["work_date"])
    if "ix_ocr_extracted_rows_terminal_short_id" not in existing_indexes:
        op.create_index("ix_ocr_extracted_rows_terminal_short_id", "ocr_extracted_rows", ["terminal_short_id"])

    # 部分ユニーク制約: 同一 branch_id x terminal_short_id x work_date で
    # reconciliation_eligible=true な confirmed 行は最大1件（計画書 v4 §2.3）。
    is_postgres = connection.dialect.name == "postgresql"
    if "uq_ocr_settlement_reconciliation_target" not in existing_indexes:
        if is_postgres:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_ocr_settlement_reconciliation_target
                    ON ocr_extracted_rows (branch_id, terminal_short_id, work_date)
                    WHERE source_type = 'paygate_settlement'
                      AND status = 'confirmed'
                      AND reconciliation_eligible = true
                      AND voided_at IS NULL
                      AND deleted_at IS NULL
                    """
                )
            )
        else:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_ocr_settlement_reconciliation_target
                    ON ocr_extracted_rows (branch_id, terminal_short_id, work_date)
                    WHERE source_type = 'paygate_settlement'
                      AND status = 'confirmed'
                      AND reconciliation_eligible = 1
                      AND voided_at IS NULL
                      AND deleted_at IS NULL
                    """
                )
            )

    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("branch_id", sa.String(length=50), nullable=False),
        sa.Column("terminal_short_id", sa.String(length=20), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("staff_id", sa.String(length=50), nullable=True),
        sa.Column("opening_count", sa.Integer(), nullable=False),
        sa.Column("closing_count", sa.Integer(), nullable=False),
        sa.Column("adjustment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adjustment_reason", sa.Text(), nullable=True),
        sa.Column("entered_by", sa.String(length=100), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("branch_id", "terminal_short_id", "work_date", name="uq_inventory_snapshots_key"),
    )
    op.create_index("ix_inventory_snapshots_work_date", "inventory_snapshots", ["work_date"])

    op.create_table(
        "inventory_reconciliation_batches",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("period_key", sa.String(length=6), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("executed_by", sa.String(length=100), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adjusted_matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("count_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sales_only_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inventory_only_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_inventory_reconciliation_batches_period_key", "inventory_reconciliation_batches", ["period_key"]
    )

    op.create_table(
        "inventory_reconciliation_results",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=26),
            sa.ForeignKey("inventory_reconciliation_batches.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.String(length=50), nullable=False),
        sa.Column("terminal_short_id", sa.String(length=20), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("ocr_row_id", sa.String(length=26), sa.ForeignKey("ocr_extracted_rows.id"), nullable=True),
        sa.Column(
            "inventory_snapshot_id",
            sa.String(length=26),
            sa.ForeignKey("inventory_snapshots.id"),
            nullable=True,
        ),
        sa.Column("ocr_transaction_count", sa.Integer(), nullable=True),
        sa.Column("inventory_decrease", sa.Integer(), nullable=True),
        sa.Column("diff", sa.Integer(), nullable=True),
        sa.Column("match_status", sa.String(length=30), nullable=False),
        sa.Column("diff_reason_category", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_inventory_reconciliation_results_batch_id", "inventory_reconciliation_results", ["batch_id"]
    )
    op.create_index(
        "ix_inventory_reconciliation_results_match_status",
        "inventory_reconciliation_results",
        ["match_status"],
    )
    op.create_index(
        "ix_inventory_reconciliation_results_work_date", "inventory_reconciliation_results", ["work_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_reconciliation_results_work_date", table_name="inventory_reconciliation_results")
    op.drop_index(
        "ix_inventory_reconciliation_results_match_status", table_name="inventory_reconciliation_results"
    )
    op.drop_index("ix_inventory_reconciliation_results_batch_id", table_name="inventory_reconciliation_results")
    op.drop_table("inventory_reconciliation_results")

    op.drop_index("ix_inventory_reconciliation_batches_period_key", table_name="inventory_reconciliation_batches")
    op.drop_table("inventory_reconciliation_batches")

    op.drop_index("ix_inventory_snapshots_work_date", table_name="inventory_snapshots")
    op.drop_table("inventory_snapshots")

    op.execute(sa.text("DROP INDEX IF EXISTS uq_ocr_settlement_reconciliation_target"))
    op.drop_index("ix_ocr_extracted_rows_terminal_short_id", table_name="ocr_extracted_rows")
    op.drop_index("ix_ocr_extracted_rows_work_date", table_name="ocr_extracted_rows")

    for column in (
        "staff_id",
        "branch_id",
        "void_reason",
        "voided_by",
        "voided_at",
        "excluded_reason",
        "reconciliation_eligible",
        "duplicate_receipt_candidate",
        "warnings",
        "blocking_errors",
        "amount_ones_digit_ok",
        "unit_breakdown_json",
        "unit_breakdown_status",
        "work_date",
        "pos_unit_count",
        "cash_unit_count",
        "other_payment",
        "pos_sales",
        "terminal_short_id",
    ):
        op.drop_column("ocr_extracted_rows", column)
