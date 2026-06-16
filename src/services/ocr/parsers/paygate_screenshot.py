"""Parser for Paygate transaction history screenshots."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.services.ocr.dedupe import dedupe_paygate_screenshot_rows
from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})")
_AMOUNT_RE = re.compile(r"[¥￥]\s*([\d,]+)")
_TXN_RE = re.compile(r"取引番号\s*(\d{6,8})")
_RECEIPT_RE = re.compile(r"レシート番号\s*(\d{10,15})")
_PAYMENT_RE = re.compile(r"決済方法\s*(\S+)")


def _parse_amount(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


class PaygateScreenshotParser(BaseOcrParser):
    source_type = "paygate_screenshot"

    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        text = ocr_result.full_text
        rows: list[ParsedOcrRow] = []
        blocks = re.split(r"(?=\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})", text)

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            dt_match = _DATETIME_RE.search(block)
            if not dt_match:
                continue

            record_date = datetime.strptime(dt_match.group(1), "%Y/%m/%d").date()
            record_time = dt_match.group(2)
            amount_match = _AMOUNT_RE.search(block)
            txn_match = _TXN_RE.search(block)
            receipt_match = _RECEIPT_RE.search(block)
            payment_match = _PAYMENT_RE.search(block)

            amount = _parse_amount(amount_match.group(1) if amount_match else None)
            confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

            row = ParsedOcrRow(
                source_type=self.source_type,
                record_date=record_date,
                record_time=record_time,
                amount=amount,
                transaction_no=txn_match.group(1) if txn_match else None,
                receipt_no=receipt_match.group(1) if receipt_match else None,
                payment_method=payment_match.group(1) if payment_match else None,
                confidence=avg_conf,
                raw_payload={"block": block},
            )
            rows.append(row)

        deduped_rows, _ = dedupe_paygate_screenshot_rows(rows)
        return deduped_rows
