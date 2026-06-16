"""Parser for Paygate settlement (精算) receipt photos."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})")
_AMOUNT_LABEL_RE = re.compile(
    r"(小計|合計|現金売上|クレジット売上|消費税|内税額)\s*[¥￥]?\s*([\d,]+)"
)
_TXN_COUNT_RE = re.compile(r"通常取引数\s*(\d+)")
_TERMINAL_RE = re.compile(
    r"端末番号[：:]\s*([0-9a-fA-F\-]{8,})"
)
_STORE_RE = re.compile(r"(日本たばこ産業株式会社|[\u4e00-\u9fff]{2,30}株式会社)")


def _parse_amount(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


class PaygateSettlementParser(BaseOcrParser):
    source_type = "paygate_settlement"

    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        text = ocr_result.full_text.replace("\r\n", "\n")
        if "精算" not in text and "現金売上" not in text:
            return []

        dt_match = _DATETIME_RE.search(text)
        record_date = None
        record_time = None
        if dt_match:
            record_date = datetime.strptime(dt_match.group(1), "%Y/%m/%d").date()
            record_time = dt_match.group(2)

        amounts: dict[str, Decimal | None] = {}
        for label, value in _AMOUNT_LABEL_RE.findall(text):
            amounts[label] = _parse_amount(value)

        txn_count_match = _TXN_COUNT_RE.search(text)
        terminal_match = _TERMINAL_RE.search(text)
        store_match = _STORE_RE.search(text)

        confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        total = amounts.get("合計") or amounts.get("現金売上") or amounts.get("小計")
        return [
            ParsedOcrRow(
                source_type=self.source_type,
                record_date=record_date,
                record_time=record_time,
                amount=total,
                terminal_id=terminal_match.group(1) if terminal_match else None,
                cash_sales=amounts.get("現金売上"),
                credit_sales=amounts.get("クレジット売上"),
                transaction_count=int(txn_count_match.group(1)) if txn_count_match else None,
                tax_included=amounts.get("内税額") or amounts.get("消費税"),
                subtotal=amounts.get("小計"),
                store_name=store_match.group(1) if store_match else None,
                confidence=avg_conf,
                raw_payload={"amounts": {k: str(v) for k, v in amounts.items() if v is not None}},
            )
        ]
