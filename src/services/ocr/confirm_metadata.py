"""Normalized confirm/metadata fields for OCR extracted rows.

Canonical value lists (also used in CSV export):
- amount_source: ocr | corrected_ocr | fallback_default | manual
- datetime_source: ocr_strict | fuzzy | missing | manual
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

AMOUNT_SOURCES = frozenset({"ocr", "corrected_ocr", "fallback_default", "manual"})
DATETIME_SOURCES = frozenset({"ocr_strict", "fuzzy", "missing", "manual"})
STRICT_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


@dataclass
class OcrRowMetadata:
    amount_inferred: bool = False
    amount_source: str | None = None
    datetime_source: str | None = None
    confirm_required: bool = True
    manually_edited: bool = False


def is_strict_record_time(record_time: str | None) -> bool:
    return bool(record_time and STRICT_TIME_RE.fullmatch(record_time))


def resolve_amount_from_parser_meta(
    amount_meta: dict[str, str],
) -> tuple[bool, str | None]:
    """Map parser raw_payload amount keys to normalized amount_inferred / amount_source."""
    if amount_meta.get("amount_inferred") or amount_meta.get("amount_source") == "fallback_default":
        return True, "fallback_default"
    if amount_meta.get("amount_corrected_from"):
        return False, "corrected_ocr"
    legacy = amount_meta.get("amount_source")
    if legacy in {"inline_datetime", "datetime_line", "right_row", "line"}:
        return False, "ocr"
    if legacy in AMOUNT_SOURCES:
        return legacy == "fallback_default", legacy
    return False, "ocr"


def resolve_datetime_source(
    record_date: date | None,
    record_time: str | None,
    parsed_source: str | None,
) -> str:
    if record_date is None and record_time is None:
        return "missing"
    if record_date is None or record_time is None:
        return "missing"
    if parsed_source == "manual":
        return "manual" if is_strict_record_time(record_time) else "fuzzy"
    if not is_strict_record_time(record_time):
        return "fuzzy"
    if parsed_source in DATETIME_SOURCES:
        return parsed_source
    return "ocr_strict"


def compute_confirm_required(
    *,
    amount_inferred: bool,
    amount_source: str | None,
    datetime_source: str | None,
    validation_errors: list[str] | None,
    record_date: date | None,
    record_time: str | None,
    amount: Decimal | None,
    transaction_no: str | None,
    receipt_no: str | None,
) -> bool:
    if validation_errors:
        return True
    if amount_inferred:
        return True
    if amount_source in {"corrected_ocr", "fallback_default"}:
        return True
    if datetime_source in {"fuzzy", "missing"}:
        return True
    if record_date is None:
        return True
    if record_time is None:
        return True
    if not is_strict_record_time(record_time):
        return True
    if amount is None:
        return True
    if not transaction_no:
        return True
    if not receipt_no:
        return True
    return False


def metadata_from_parsed_fields(
    *,
    record_date: date | None,
    record_time: str | None,
    amount: Decimal | None,
    transaction_no: str | None,
    receipt_no: str | None,
    amount_meta: dict[str, str] | None = None,
    parsed_datetime_source: str | None = None,
    validation_errors: list[str] | None = None,
    manually_edited: bool = False,
    amount_source_override: str | None = None,
    amount_inferred_override: bool | None = None,
    datetime_source_override: str | None = None,
) -> OcrRowMetadata:
    amount_inferred, amount_source = resolve_amount_from_parser_meta(amount_meta or {})
    if amount_source_override is not None:
        amount_source = amount_source_override
    if amount_inferred_override is not None:
        amount_inferred = amount_inferred_override

    datetime_source = datetime_source_override or resolve_datetime_source(
        record_date,
        record_time,
        parsed_datetime_source,
    )

    confirm_required = compute_confirm_required(
        amount_inferred=amount_inferred,
        amount_source=amount_source,
        datetime_source=datetime_source,
        validation_errors=validation_errors,
        record_date=record_date,
        record_time=record_time,
        amount=amount,
        transaction_no=transaction_no,
        receipt_no=receipt_no,
    )
    return OcrRowMetadata(
        amount_inferred=amount_inferred,
        amount_source=amount_source,
        datetime_source=datetime_source,
        confirm_required=confirm_required,
        manually_edited=manually_edited,
    )


def _get_screenshot_confirm_rejection_reasons(row: Any) -> list[str]:
    """paygate_screenshot: transaction_no / receipt_no が必須。"""
    reasons: list[str] = []
    if getattr(row, "confirm_required", False):
        reasons.append("confirm_required")
    if getattr(row, "validation_errors", None):
        reasons.append("validation_errors")
    if row.record_date is None:
        reasons.append("missing_record_date")
    if row.record_time is None:
        reasons.append("missing_record_time")
    if row.amount is None:
        reasons.append("missing_amount")
    if not row.transaction_no:
        reasons.append("missing_transaction_no")
    if not row.receipt_no:
        reasons.append("missing_receipt_no")
    return reasons


def _get_settlement_confirm_rejection_reasons(row: Any) -> list[str]:
    """paygate_settlement: transaction_no / receipt_no は不要（既知バグの修正）。

    計画書 v4 §1（既知バグ・レビュー①指摘）: 精算レシートには取引番号・レシート番号が
    印字されないため、これらを必須とする旧ロジックのままでは精算行が一切確定できない。
    代わりに terminal_short_id / record_date / record_time / amount / transaction_count
    の必須項目チェックと、blocking_errors（1の位チェック・金額整合チェック等）を用いる。
    unit_breakdown_status=manual/ambiguous はここでは確定をブロックしない(warningsのみ)。
    """
    reasons: list[str] = []
    if getattr(row, "blocking_errors", None):
        reasons.append("blocking_errors")
    if getattr(row, "voided_at", None) is not None:
        reasons.append("voided")
    if row.record_date is None:
        reasons.append("missing_record_date")
    if row.record_time is None:
        reasons.append("missing_record_time")
    if row.amount is None:
        reasons.append("missing_amount")
    if getattr(row, "transaction_count", None) is None:
        reasons.append("missing_transaction_count")
    if not getattr(row, "terminal_short_id", None):
        reasons.append("missing_terminal_short_id")
    return reasons


def get_confirm_rejection_reasons(row: Any) -> list[str]:
    """Return rejection reason codes for confirm_rows guard.

    Common checks (deleted / already_confirmed) apply to all source_types; the
    remaining rules branch by source_type since paygate_settlement receipts do not
    print transaction_no/receipt_no (see _get_settlement_confirm_rejection_reasons).
    """
    reasons: list[str] = []
    if getattr(row, "deleted_at", None) is not None:
        reasons.append("deleted")
    if getattr(row, "status", None) == "confirmed":
        reasons.append("already_confirmed")

    if getattr(row, "source_type", None) == "paygate_settlement":
        reasons.extend(_get_settlement_confirm_rejection_reasons(row))
    else:
        reasons.extend(_get_screenshot_confirm_rejection_reasons(row))
    return reasons


class OcrConfirmRejectedError(Exception):
    def __init__(self, reasons: dict[str, list[str]]):
        self.reasons = reasons
        self.rejected_row_ids = list(reasons.keys())
        super().__init__("Some rows cannot be confirmed")
