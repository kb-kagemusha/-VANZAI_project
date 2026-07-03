"""Parser for Paygate settlement (精算) receipt photos."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.parsers.settlement_amount import sanitize_settlement_amount
from src.services.ocr.settlement_processing import (
    apply_settlement_derived_fields,
    normalize_settlement_transaction_count,
)

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})")
_SETTLEMENT_DATE_RE = re.compile(r"精算日\s*[：:]?\s*(\d{4}/\d{2}/\d{2})")
_SETTLEMENT_TIME_RE = re.compile(r"精算時間\s*[：:]?\s*(\d{2}:\d{2}:\d{2})")
# NOTE: "PAYGATE POS" / "その他支払い" ラベルの実際の印字書式は Phase 0 で実レシートを
# 追加サンプリングして確認する（現状はユーザーヒアリングに基づく想定書式）。
_AMOUNT_LABEL_RE = re.compile(
    r"(?:[-－]\s*)?"
    r"(小計|合計|現金売上|クレジット売上|PAYGATE[\s　]*POS|その他支払い|消費税|内税額)"
    r"\s*(?:[¥￥]\s*)?"
    r"([\d,]+)"
)
_UUID_BODY_RE = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)
# 端末番号(UUID)は感熱紙幅で2行に折り返されることが多い
_TERMINAL_RE = re.compile(
    rf"端末\s*番号\s*[：:]?\s*(?:\n\s*)?({_UUID_BODY_RE})",
    re.IGNORECASE,
)
_TERMINAL_SPLIT_RE = re.compile(
    rf"端末\s*番号\s*[：:]?\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-)\s*(?:\n\s*)?"
    rf"([0-9a-fA-F]{{12}})",
    re.IGNORECASE,
)
_TERMINAL_FALLBACK_RE = re.compile(
    rf"端末\s*番号[\s\S]{{0,120}}?({_UUID_BODY_RE})",
    re.IGNORECASE,
)
_TXN_COUNT_PATTERNS = (
    re.compile(r"通常\s*取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常\s*取引数\s*[：:]?\s*\n\s*(\d+)"),
    re.compile(r"通常取引数\s*[：:]?\s*\n\s*(\d+)"),
)
# 端末識別番号（例: f353 / 0ed7）。端末番号(UUID)とは別項目。
_TERMINAL_SHORT_ID_PATTERNS = (
    re.compile(r"端末\s*識別番号\s*[：:]?\s*([0-9a-zA-Z]{2,10})\b", re.IGNORECASE),
    re.compile(
        r"端末\s*識別番号\s*[：:]?\s*(?:\n|\r\n)\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"T4-\d{4}-\d{4}-\d{4}\s*\n\s*([0-9a-fA-F]{4})\b",
        re.IGNORECASE,
    ),
    # 端末識別番号ラベルが落ち、UUID直前の1行に短IDだけ印字されるケース
    re.compile(
        r"(?:^|\n)\s*([0-9a-fA-F]{4})\s*\n\s*端末\s*番号",
        re.IGNORECASE | re.MULTILINE,
    ),
)
# 登録番号 T4-xxxx の数字列（3000 等）と区別するため純数字4桁は除外
_REGISTRATION_SEGMENT_RE = re.compile(r"^\d{4}$")
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


def _is_plausible_terminal_short_id(value: str) -> bool:
    """登録番号 T4-xxxx-xxxx-3000 の末尾4桁と区別する。"""
    if not re.fullmatch(r"[0-9a-zA-Z]{2,10}", value):
        return False
    if _REGISTRATION_SEGMENT_RE.fullmatch(value):
        return False
    # 端末識別番号は英字を含む hex が多い（0ed7, f353）。純数字4桁は登録番号断片の誤検知。
    if value.isdigit():
        return False
    return bool(re.search(r"[a-zA-Z]", value))


def _extract_terminal_id(text: str) -> str | None:
    split_match = _TERMINAL_SPLIT_RE.search(text)
    if split_match:
        return f"{split_match.group(1)}{split_match.group(2)}".lower()

    terminal_match = _TERMINAL_RE.search(text)
    if terminal_match:
        return terminal_match.group(1).lower()

    fallback = _TERMINAL_FALLBACK_RE.search(text)
    if fallback:
        return fallback.group(1).lower()
    return None


def _extract_terminal_short_id(text: str) -> str | None:
    for pattern in _TERMINAL_SHORT_ID_PATTERNS:
        match = pattern.search(text)
        if match and _is_plausible_terminal_short_id(match.group(1)):
            return match.group(1).lower()
    return None


def _extract_transaction_count(text: str) -> int | None:
    for pattern in _TXN_COUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _normalize_terminal_uuid_lines(text: str) -> str:
    """UUID が2行に折り返された OCR テキストを1行に結合する。"""
    return _TERMINAL_SPLIT_RE.sub(
        lambda match: f"端末番号: {match.group(1)}{match.group(2)}",
        text,
    )


def _normalize_settlement_text(text: str) -> str:
    """OCR誤認識の軽微な正規化（精算レシート専用）。"""
    normalized = text.replace("\r\n", "\n")
    normalized = normalized.replace("　", " ")
    # 「-PAYGATE POS」「- PAYGATEPOS」等を統一ラベルへ
    normalized = re.sub(
        r"[-－]\s*PAYGATE\s*POS",
        "PAYGATE POS",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"PAYGATEPOS", "PAYGATE POS", normalized, flags=re.IGNORECASE)
    normalized = _normalize_terminal_uuid_lines(normalized)
    return normalized


def _extract_settlement_datetime(text: str) -> tuple[date | None, str | None, str]:
    dt_match = _DATETIME_RE.search(text)
    if dt_match:
        return (
            datetime.strptime(dt_match.group(1), "%Y/%m/%d").date(),
            dt_match.group(2),
            "ocr_strict",
        )

    date_match = _SETTLEMENT_DATE_RE.search(text)
    time_match = _SETTLEMENT_TIME_RE.search(text)
    record_date = None
    record_time = None
    if date_match:
        record_date = datetime.strptime(date_match.group(1), "%Y/%m/%d").date()
    if time_match:
        record_time = time_match.group(1)

    if record_date and record_time:
        return record_date, record_time, "ocr_strict"
    if record_date or record_time:
        return record_date, record_time, "fuzzy"
    return None, None, "missing"


class PaygateSettlementParser(BaseOcrParser):
    source_type = "paygate_settlement"

    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        text = _normalize_settlement_text(ocr_result.full_text)
        if "精算" not in text and "現金売上" not in text:
            return []

        record_date, record_time, parsed_datetime_source = _extract_settlement_datetime(text)

        amounts: dict[str, Decimal | None] = {}
        amount_corrections: dict[str, str] = {}
        for label, value in _AMOUNT_LABEL_RE.findall(text):
            amount, corrected_from = sanitize_settlement_amount(value)
            key = _canonical_label(label)
            amounts[key] = amount
            if corrected_from:
                amount_corrections[key] = corrected_from

        txn_count_match = _extract_transaction_count(text)
        terminal_id = _extract_terminal_id(text)
        terminal_short_id = _extract_terminal_short_id(text)
        store_match = _STORE_RE.search(text)

        raw_txn_count = txn_count_match
        transaction_count = normalize_settlement_transaction_count(
            raw_txn_count,
            amounts.get("cash"),
            amounts.get("pos"),
        )

        confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        total = amounts.get("total")
        amount_meta: dict[str, str] = {"amount_source": "ocr"} if total is not None else {}
        if amount_corrections.get("total"):
            amount_meta["amount_corrected_from"] = amount_corrections["total"]
            amount_meta["amount_source"] = "corrected_ocr"

        parsed = ParsedOcrRow(
            source_type=self.source_type,
            record_date=record_date,
            record_time=record_time,
            amount=total,
            terminal_id=terminal_id,
            terminal_short_id=terminal_short_id,
            cash_sales=amounts.get("cash"),
            credit_sales=amounts.get("credit"),
            pos_sales=amounts.get("pos"),
            other_payment=amounts.get("other"),
            transaction_count=transaction_count,
            tax_included=amounts.get("tax_included") or amounts.get("tax"),
            subtotal=amounts.get("subtotal"),
            store_name=store_match.group(1) if store_match else None,
            confidence=avg_conf,
            raw_payload={
                "amounts": {k: str(v) for k, v in amounts.items() if v is not None},
                **({"amount_corrections": amount_corrections} if amount_corrections else {}),
                **amount_meta,
            },
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
