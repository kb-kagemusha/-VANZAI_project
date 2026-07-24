"""Derived-field computation for paygate_settlement OCR rows.

Ties together work_date resolution, unit-count breakdown solving, and the
blocking/warning validation split (計画書 v4 §1, §2.1, §2.5, §5.2).

`apply_settlement_derived_fields` is pure (no DB access) and can be called on any
object exposing the relevant attributes (ParsedOcrRow dataclass or OcrExtractedRow
ORM instance). Duplicate-candidate detection requires a DB session and is handled
separately via `src.services.ocr.duplicate_detection`.
"""
from __future__ import annotations

from src.services.ocr.unit_breakdown import compute_unit_breakdown
from src.services.ocr.validation import (
    compute_settlement_blocking_errors,
    compute_settlement_ones_digit_ok,
    compute_settlement_warnings,
)
from src.services.ocr.work_date import compute_work_date

DEFAULT_BRANCH_ID = "UNASSIGNED"


def _sales_yen(value) -> int:
    if value is None:
        return 0
    return int(value)


def normalize_settlement_transaction_count(
    transaction_count: int | None,
    cash_sales,
    pos_sales,
) -> int | None:
    """OCR が売上ありなのに通常取引数 0 を返す誤認識を除外する。"""
    if transaction_count != 0:
        return transaction_count
    if _sales_yen(cash_sales) > 0 or _sales_yen(pos_sales) > 0:
        return None
    return 0


def apply_settlement_derived_fields(row) -> None:
    """Recompute work_date / unit_breakdown_* / amount_ones_digit_ok / blocking_errors
    / warnings / confirm_required on a paygate_settlement row object in place.

    `validation_errors` (legacy column, also used by the generic OCR UI/CSV) is
    mirrored to blocking_errors for paygate_settlement rows so existing surfaces keep
    showing something meaningful without needing separate branching everywhere.
    """
    row.work_date = compute_work_date(row.record_date, row.record_time)

    pos_sales = getattr(row, "pos_sales", None)
    effective_txn_count = normalize_settlement_transaction_count(
        row.transaction_count,
        row.cash_sales,
        pos_sales,
    )
    if effective_txn_count != row.transaction_count:
        row.transaction_count = effective_txn_count

    breakdown = compute_unit_breakdown(
        cash_sales=row.cash_sales,
        pos_sales=pos_sales,
        credit_sales=row.credit_sales,
        other_payment=getattr(row, "other_payment", None),
        transaction_count=effective_txn_count,
    )
    row.unit_breakdown_status = breakdown["unit_breakdown_status"]
    row.unit_breakdown_json = breakdown["unit_breakdown_json"]
    row.cash_unit_count = breakdown["cash_unit_count"]
    row.pos_unit_count = breakdown["pos_unit_count"]

    row.amount_ones_digit_ok = compute_settlement_ones_digit_ok(row)

    blocking_errors = compute_settlement_blocking_errors(row)
    warnings = compute_settlement_warnings(row)
    row.blocking_errors = blocking_errors or None
    row.warnings = warnings or None
    row.validation_errors = blocking_errors or None
    row.confirm_required = bool(blocking_errors)
