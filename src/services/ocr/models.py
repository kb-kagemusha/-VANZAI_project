"""Internal DTOs for OCR pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class OcrTextLine:
    text: str
    confidence: float = 0.0
    box: list[list[float]] | None = None


@dataclass
class OcrEngineResult:
    lines: list[OcrTextLine] = field(default_factory=list)
    full_text: str = ""


@dataclass
class ParsedOcrRow:
    source_type: str
    record_date: date | None = None
    record_time: str | None = None
    amount: Decimal | None = None
    transaction_no: str | None = None
    receipt_no: str | None = None
    payment_method: str | None = None
    terminal_id: str | None = None
    cash_sales: Decimal | None = None
    credit_sales: Decimal | None = None
    transaction_count: int | None = None
    tax_included: Decimal | None = None
    subtotal: Decimal | None = None
    store_name: str | None = None
    confidence: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def period_key(self) -> str | None:
        if self.record_date is None:
            return None
        return self.record_date.strftime("%Y%m")
