"""Validation rules for parsed OCR rows."""
from __future__ import annotations

from decimal import Decimal

from src.services.ocr.models import ParsedOcrRow


def validate_parsed_row(row: ParsedOcrRow) -> list[str]:
    errors: list[str] = []

    if row.record_date is None:
        errors.append("record_date is missing")

    if row.source_type == "paygate_screenshot":
        if row.transaction_no and len(row.transaction_no) not in {6, 7, 8}:
            errors.append("transaction_no digit count is invalid")
        if row.receipt_no and len(row.receipt_no) not in {12, 13, 14, 15}:
            errors.append("receipt_no digit count is invalid")
        if row.amount is None:
            errors.append("amount is missing")

    if row.source_type == "paygate_settlement":
        if row.amount is None:
            errors.append("settlement total amount is missing")
        if row.subtotal and row.amount and row.subtotal != row.amount:
            if row.cash_sales and row.cash_sales == row.amount:
                pass
            else:
                errors.append("subtotal and total do not match")
        if row.cash_sales and row.amount and row.cash_sales != row.amount and row.credit_sales in {None, Decimal(0)}:
            errors.append("cash_sales and total do not match")
        if row.transaction_count is not None and row.transaction_count < 0:
            errors.append("transaction_count is invalid")

    return errors
