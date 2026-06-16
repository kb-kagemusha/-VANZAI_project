"""CSV export for OCR extracted rows."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from src.models.ocr import OcrExtractedRow

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
    "status",
    "image_id",
    "row_id",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


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
                "status": row.status,
                "image_id": row.source_image_id,
                "row_id": row.id,
            }
        )
    return buffer.getvalue()
