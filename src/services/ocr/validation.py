"""Validation rules for parsed OCR rows."""
from __future__ import annotations

import re
from decimal import Decimal

from src.services.ocr.confirm_metadata import STRICT_TIME_RE
from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.parsers.settlement_amount import is_valid_settlement_unit_sales_amount
from src.services.ocr.parsers.settlement_terminal_id import (
    is_valid_settlement_terminal_short_id,
    terminal_id_is_partial_from_payload,
)

_PAYGATE_TXN_RE = re.compile(r"^1\d{6}$")
_PAYGATE_RECEIPT_RE = re.compile(r"^(77\d{11}|78\d{11})$")


def is_paygate_row_saveable(row: ParsedOcrRow) -> bool:
    """Save only when date, transaction_no, and receipt_no are all present and valid."""
    if row.source_type != "paygate_screenshot":
        return True
    if row.record_date is None:
        return False
    if not row.transaction_no or not _PAYGATE_TXN_RE.fullmatch(row.transaction_no):
        return False
    if not row.receipt_no or not _PAYGATE_RECEIPT_RE.fullmatch(row.receipt_no):
        return False
    return True


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
        if row.record_time is None:
            errors.append("record_time is missing")
        elif not STRICT_TIME_RE.fullmatch(row.record_time):
            errors.append("record_time format is invalid (expected HH:MM:SS)")

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
        if row.record_time and not STRICT_TIME_RE.fullmatch(row.record_time):
            errors.append("record_time format is invalid (expected HH:MM:SS)")

    return errors


# --- paygate_settlement 専用: ブロッキングエラー / 警告の分離 ---------------------
# 計画書 v4 §2.5 の指摘に基づき、OCR確定を止めるべき致命的エラー(blocking_errors)と
# 確定は止めないが要注意な事項(warnings)を分離する。paygate_screenshot には適用しない。

_UNIT_PRICES_YEN = (980, 1480, 2980)


def _ones_digit_is_bad(value: Decimal | None) -> bool:
    """3種の単価(¥980/¥1,480/¥2,980)はいずれも10の倍数のため、1の位が0以外なら異常値。"""
    if value is None:
        return False
    return int(value) % 10 != 0


def compute_settlement_ones_digit_ok(row) -> bool | None:
    """全ての金額項目の1の位が0であれば True。金額が1件も存在しなければ None。"""
    amounts = [
        getattr(row, "amount", None),
        getattr(row, "cash_sales", None),
        getattr(row, "pos_sales", None),
        getattr(row, "credit_sales", None),
        getattr(row, "other_payment", None),
    ]
    present = [value for value in amounts if value is not None]
    if not present:
        return None
    return not any(_ones_digit_is_bad(value) for value in present)


def compute_settlement_blocking_errors(row) -> list[str]:
    """paygate_settlement 行のOCR確定をブロックすべき致命的エラーを返す。"""
    errors: list[str] = []

    field_labels = {
        "amount": "amount",
        "cash_sales": "cash_sales",
        "pos_sales": "pos_sales",
        "credit_sales": "credit_sales",
        "other_payment": "other_payment",
    }
    for field_name, label in field_labels.items():
        value = getattr(row, field_name, None)
        if _ones_digit_is_bad(value):
            errors.append(f"{label}_ones_digit_invalid")

    for field_name, code in (
        ("cash_sales", "cash_sales_unit_invalid"),
        ("pos_sales", "pos_sales_unit_invalid"),
    ):
        value = getattr(row, field_name, None)
        if value is not None and value > 0 and not is_valid_settlement_unit_sales_amount(value):
            errors.append(code)

    amount = getattr(row, "amount", None)
    components = [
        getattr(row, "cash_sales", None),
        getattr(row, "credit_sales", None),
        getattr(row, "pos_sales", None),
        getattr(row, "other_payment", None),
    ]
    if amount is not None and any(component is not None for component in components):
        total_components = sum((component or Decimal(0)) for component in components)
        if total_components != amount:
            errors.append("amount_breakdown_mismatch")

    transaction_count = getattr(row, "transaction_count", None)
    if transaction_count is not None and transaction_count < 0:
        errors.append("transaction_count_invalid")

    if getattr(row, "amount", None) is None:
        errors.append("settlement_amount_missing")

    subtotal = getattr(row, "subtotal", None)
    amount = getattr(row, "amount", None)
    if subtotal is not None and amount is not None and subtotal > amount:
        errors.append("subtotal_exceeds_total")

    short_id = getattr(row, "terminal_short_id", None)
    if not short_id:
        errors.append("missing_terminal_short_id")
    elif not is_valid_settlement_terminal_short_id(short_id):
        errors.append("invalid_terminal_short_id")

    raw_payload = getattr(row, "raw_payload", None)
    if terminal_id_is_partial_from_payload(raw_payload):
        errors.append("terminal_id_partial")

    return errors


def compute_settlement_warnings(row) -> list[str]:
    """paygate_settlement 行のOCR確定はブロックしないが、要注意な事項を返す。"""
    warnings: list[str] = []
    if getattr(row, "duplicate_receipt_candidate", False):
        warnings.append("duplicate_receipt_candidate")
    return warnings
