"""CSV export for OCR extracted rows."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from src.models.ocr import OcrExtractedRow

# Canonical metadata values: see src/services/ocr/confirm_metadata.py
CSV_COLUMNS = [
    "source_type",
    "period_key",
    "record_date",
    "record_time",
    "amount",
    "currency",
    "transaction_no",
    "receipt_no",
    "payment_method",
    "terminal_id",
    "cash_sales",
    "credit_sales",
    "transaction_count",
    "tax_included",
    "subtotal",
    "store_name",
    "confidence",
    "amount_inferred",
    "amount_source",
    "datetime_source",
    "confirm_required",
    "manually_edited",
    "status",
    "image_id",
    "row_id",
]


def _format_yen_amount(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(int(value.to_integral_value()))
    return str(value)


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return _format_yen_amount(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# --- paygate_settlement 専用CSV（計画書 v4 §2.7: 既存25列CSVとは分離） -------------
# 既存 CSV_COLUMNS / rows_to_csv は後方互換のため変更しない。
SETTLEMENT_CSV_EXPORT_VERSION = "settlement_v1"

SETTLEMENT_CSV_COLUMNS = [
    "export_version",
    "row_id",
    "image_id",
    "branch_id",
    "terminal_short_id",
    "terminal_id",
    "work_date",
    "record_date",
    "record_time",
    "staff_id",
    "amount",
    "cash_sales",
    "pos_sales",
    "credit_sales",
    "other_payment",
    "subtotal",
    "tax_included",
    "transaction_count",
    "cash_unit_count",
    "pos_unit_count",
    "unit_breakdown_status",
    "amount_ones_digit_ok",
    "blocking_errors",
    "warnings",
    "duplicate_receipt_candidate",
    "reconciliation_eligible",
    "excluded_reason",
    "status",
    "confirmed_at",
    "confirmed_by",
    "voided_at",
    "void_reason",
    "store_name",
]


def _list_cell(value: list | None) -> str:
    if not value:
        return ""
    return ";".join(str(v) for v in value)


def settlement_rows_to_csv(rows: list[OcrExtractedRow]) -> str:
    """paygate_settlement 専用の拡張CSV（既存の25列CSVとは独立）。"""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=SETTLEMENT_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "export_version": SETTLEMENT_CSV_EXPORT_VERSION,
                "row_id": row.id,
                "image_id": row.source_image_id,
                "branch_id": row.branch_id or "",
                "terminal_short_id": row.terminal_short_id or "",
                "terminal_id": row.terminal_id or "",
                "work_date": row.work_date.isoformat() if row.work_date else "",
                "record_date": row.record_date.isoformat() if row.record_date else "",
                "record_time": row.record_time or "",
                "staff_id": row.staff_id or "",
                "amount": _cell(row.amount),
                "cash_sales": _cell(row.cash_sales),
                "pos_sales": _cell(row.pos_sales),
                "credit_sales": _cell(row.credit_sales),
                "other_payment": _cell(row.other_payment),
                "subtotal": _cell(row.subtotal),
                "tax_included": _cell(row.tax_included),
                "transaction_count": row.transaction_count if row.transaction_count is not None else "",
                "cash_unit_count": row.cash_unit_count if row.cash_unit_count is not None else "",
                "pos_unit_count": row.pos_unit_count if row.pos_unit_count is not None else "",
                "unit_breakdown_status": row.unit_breakdown_status or "",
                "amount_ones_digit_ok": _cell(row.amount_ones_digit_ok),
                "blocking_errors": _list_cell(row.blocking_errors),
                "warnings": _list_cell(row.warnings),
                "duplicate_receipt_candidate": _cell(row.duplicate_receipt_candidate),
                "reconciliation_eligible": _cell(row.reconciliation_eligible),
                "excluded_reason": row.excluded_reason or "",
                "status": row.status,
                "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else "",
                "confirmed_by": row.confirmed_by or "",
                "voided_at": row.voided_at.isoformat() if row.voided_at else "",
                "void_reason": row.void_reason or "",
                "store_name": row.store_name or "",
            }
        )
    return buffer.getvalue()


def rows_to_csv(rows: list[OcrExtractedRow]) -> str:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "source_type": row.source_type,
                "period_key": row.period_key or "",
                "record_date": row.record_date.isoformat() if row.record_date else "",
                "record_time": row.record_time or "",
                "amount": _cell(row.amount),
                "currency": row.currency,
                "transaction_no": row.transaction_no or "",
                "receipt_no": row.receipt_no or "",
                "payment_method": row.payment_method or "",
                "terminal_id": row.terminal_id or "",
                "cash_sales": _cell(row.cash_sales),
                "credit_sales": _cell(row.credit_sales),
                "transaction_count": row.transaction_count if row.transaction_count is not None else "",
                "tax_included": _cell(row.tax_included),
                "subtotal": _cell(row.subtotal),
                "store_name": row.store_name or "",
                "confidence": _cell(row.confidence),
                "amount_inferred": _cell(row.amount_inferred),
                "amount_source": row.amount_source or "",
                "datetime_source": row.datetime_source or "",
                "confirm_required": _cell(row.confirm_required),
                "manually_edited": _cell(row.manually_edited),
                "status": row.status,
                "image_id": row.source_image_id,
                "row_id": row.id,
            }
        )
    return buffer.getvalue()
