"""Parser for Paygate settlement (精算) receipt photos."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.settlement_processing import apply_settlement_derived_fields

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})")
# NOTE: "PAYGATE POS" / "その他支払い" ラベルの実際の印字書式は Phase 0 で実レシートを
# 追加サンプリングして確認する（現状はユーザーヒアリングに基づく想定書式）。
_AMOUNT_LABEL_RE = re.compile(
    r"(小計|合計|現金売上|クレジット売上|PAYGATE[\s　]*POS|その他支払い|消費税|内税額)"
    r"\s*[¥￥]?\s*([\d,]+)"
)
_TXN_COUNT_RE = re.compile(r"通常取引数\s*(\d+)")
_TERMINAL_RE = re.compile(
    r"端末番号[：:]\s*([0-9a-fA-F\-]{8,})"
)
# 端末識別番号（例: f353）。端末番号(UUID)とは別項目。書式はPhase 0で要再確認。
_TERMINAL_SHORT_ID_RE = re.compile(r"端末識別番号[：:]?\s*([A-Za-z0-9]{2,10})")
_STORE_RE = re.compile(r"(日本たばこ産業株式会社|[\u4e00-\u9fff]{2,30}株式会社)")

_LABEL_CANONICAL = {
    "小計": "subtotal",
    "合計": "total",
    "現金売上": "cash",
    "クレジット売上": "credit",
    "消費税": "tax",
    "内税額": "tax_included",
    "その他支払い": "other",
}


def _canonical_label(label: str) -> str:
    normalized = label.replace("　", "").replace(" ", "").upper()
    if normalized == "PAYGATEPOS":
        return "pos"
    return _LABEL_CANONICAL.get(label, label)


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
        parsed_datetime_source = "missing"
        if dt_match:
            record_date = datetime.strptime(dt_match.group(1), "%Y/%m/%d").date()
            record_time = dt_match.group(2)
            parsed_datetime_source = "ocr_strict"

        amounts: dict[str, Decimal | None] = {}
        for label, value in _AMOUNT_LABEL_RE.findall(text):
            amounts[_canonical_label(label)] = _parse_amount(value)

        txn_count_match = _TXN_COUNT_RE.search(text)
        terminal_match = _TERMINAL_RE.search(text)
        terminal_short_match = _TERMINAL_SHORT_ID_RE.search(text)
        store_match = _STORE_RE.search(text)

        confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        total = amounts.get("total") or amounts.get("cash") or amounts.get("subtotal")
        amount_meta = {"amount_source": "ocr"} if total is not None else {}

        parsed = ParsedOcrRow(
            source_type=self.source_type,
            record_date=record_date,
            record_time=record_time,
            amount=total,
            terminal_id=terminal_match.group(1) if terminal_match else None,
            terminal_short_id=terminal_short_match.group(1) if terminal_short_match else None,
            cash_sales=amounts.get("cash"),
            credit_sales=amounts.get("credit"),
            pos_sales=amounts.get("pos"),
            other_payment=amounts.get("other"),
            transaction_count=int(txn_count_match.group(1)) if txn_count_match else None,
            tax_included=amounts.get("tax_included") or amounts.get("tax"),
            subtotal=amounts.get("subtotal"),
            store_name=store_match.group(1) if store_match else None,
            confidence=avg_conf,
            raw_payload={"amounts": {k: str(v) for k, v in amounts.items() if v is not None}, **amount_meta},
        )
        apply_settlement_derived_fields(parsed)
        # validation_errors (legacy column) is mirrored from blocking_errors by
        # apply_settlement_derived_fields above; normalize None -> [] for callers
        # that expect a list (e.g. CSV export, generic UI badges).
        parsed.validation_errors = parsed.validation_errors or []
        meta = metadata_from_parsed_fields(
            record_date=parsed.record_date,
            record_time=parsed.record_time,
            amount=parsed.amount,
            transaction_no=parsed.transaction_no,
            receipt_no=parsed.receipt_no,
            amount_meta=amount_meta,
            parsed_datetime_source=parsed_datetime_source,
            validation_errors=parsed.blocking_errors or None,
        )
        parsed.amount_inferred = meta.amount_inferred
        parsed.amount_source = meta.amount_source
        parsed.datetime_source = meta.datetime_source
        # confirm_required for paygate_settlement is governed solely by blocking_errors
        # (see settlement_processing.apply_settlement_derived_fields / confirm_metadata
        # source_type branching). The generic metadata's confirm_required is ignored here.
        return [parsed]
