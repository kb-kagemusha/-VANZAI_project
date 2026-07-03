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

_DATETIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2})\s*(\d{2}:\d{2}:\d{2})")
_SETTLEMENT_DATE_RE = re.compile(r"精算日\s*[：:]?\s*(\d{4}/\d{2}/\d{2})")
_SETTLEMENT_TIME_RE = re.compile(r"精算時間\s*[：:]?\s*(\d{2}:\d{2}:\d{2})")
_UUID_BODY_RE = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)
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
    rf"端末\s*番号[\s\S]{{0,200}}?({_UUID_BODY_RE})",
    re.IGNORECASE,
)
_TXN_COUNT_PATTERNS = (
    re.compile(r"通常\s*取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常取引数\s*[：:]?\s*(\d+)"),
    re.compile(r"通常\s*取引数\s*[：:]?\s*\n\s*(\d+)\s*(?:\n|$)"),
    re.compile(r"通常取引数\s*[：:]?\s*\n\s*(\d+)\s*(?:\n|$)"),
)
_TERMINAL_SHORT_ID_PATTERNS = (
    re.compile(r"端末\s*識別番号\s*[：:]?\s*([0-9a-zA-Z]{2,10})\b", re.IGNORECASE),
    re.compile(
        r"端末\s*識別番号\s*[：:]?\s*(?:\n|\r\n)\s*([0-9a-zA-Z]{2,10})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*([0-9a-fA-F]{4})\s*\n\s*端末\s*番号",
        re.IGNORECASE | re.MULTILINE,
    ),
)
_REGISTRATION_SEGMENT_RE = re.compile(r"^\d{4}$")
_STORE_RE = re.compile(r"(日本たばこ産業株式会社|[\u4e00-\u9fff]{2,30}株式会社)")
_OCR_HEX_FIXES = str.maketrans(
    {
        "\u00e1": "a",
        "\u00e0": "a",
        "\u00e2": "a",
        "\u00e4": "a",
        "\u00c1": "a",
        "\u00c0": "a",
        "\u00c2": "a",
        "\u00c4": "a",
    }
)

_AMOUNT_FIELD_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("subtotal", ("小計",)),
    ("total", ("合計",)),
    ("cash", ("現金売上",)),
    ("credit", ("クレジット売上", "クレヅット売上")),
    ("pos", ("PAYGATE POS",)),
    ("other", ("その他支払い",)),
    ("tax", ("消費税",)),
    ("tax_included", ("内税額",)),
)


def _canonical_label(label: str) -> str:
    normalized = label.replace("　", "").replace(" ", "").upper()
    if normalized == "PAYGATEPOS":
        return "pos"
    return {
        "小計": "subtotal",
        "合計": "total",
        "現金売上": "cash",
        "クレジット売上": "credit",
        "クレヅット売上": "credit",
        "消費税": "tax",
        "内税額": "tax_included",
        "その他支払い": "other",
    }.get(label, label)


def _is_plausible_terminal_short_id(value: str) -> bool:
    if not re.fullmatch(r"[0-9a-zA-Z]{2,10}", value):
        return False
    if _REGISTRATION_SEGMENT_RE.fullmatch(value):
        return False
    if value.isdigit():
        return False
    return bool(re.search(r"[a-zA-Z]", value))


def _clean_hex_line(line: str) -> str:
    line = line.translate(_OCR_HEX_FIXES)
    return re.sub(r"[^0-9a-fA-F-]", "", line.strip())


def _format_uuid(hex_only: str) -> str:
    return (
        f"{hex_only[:8]}-{hex_only[8:12]}-{hex_only[12:16]}-"
        f"{hex_only[16:20]}-{hex_only[20:32]}"
    ).lower()


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

    if "端末" not in text:
        return None
    parts = re.split(r"端末\s*番号", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return None
    section = re.split(r"(?:^|\n)\s*小計", parts[1], maxsplit=1, flags=re.IGNORECASE)[0]
    chunks: list[str] = []
    for line in section.splitlines():
        cleaned = _clean_hex_line(line).strip("-")
        if len(cleaned) < 4:
            continue
        if not re.fullmatch(r"[0-9a-fA-F-]+", cleaned):
            continue
        chunks.append(cleaned)
    if not chunks:
        return None

    joined = ""
    for chunk in chunks:
        if not joined:
            joined = chunk
        elif joined.endswith("-") or chunk.startswith("-"):
            joined += chunk.lstrip("-")
        else:
            joined += "-" + chunk
    joined = re.sub(r"-+", "-", joined).strip("-").lower()
    hex_only = joined.replace("-", "")
    if len(hex_only) == 32:
        return _format_uuid(hex_only)
    if len(hex_only) >= 12:
        return joined
    return None


def _short_id_from_terminal_id(terminal_id: str | None) -> str | None:
    if not terminal_id:
        return None
    first_segment = terminal_id.split("-", 1)[0]
    if len(first_segment) == 8 and re.fullmatch(r"[0-9a-f]{8}", first_segment):
        candidate = first_segment[:4]
        if _is_plausible_terminal_short_id(candidate):
            return candidate
    return None


def _extract_terminal_short_id(text: str, terminal_id: str | None = None) -> str | None:
    for pattern in _TERMINAL_SHORT_ID_PATTERNS:
        match = pattern.search(text)
        if match and _is_plausible_terminal_short_id(match.group(1)):
            return match.group(1).lower()
    return _short_id_from_terminal_id(terminal_id)


def _extract_transaction_count(text: str) -> int | None:
    for pattern in _TXN_COUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _infer_transaction_count_from_sales(
    cash_sales: Decimal | None,
    pos_sales: Decimal | None,
    ocr_count: int | None,
) -> int | None:
    if ocr_count and ocr_count > 0:
        return ocr_count
    normalized = normalize_settlement_transaction_count(ocr_count, cash_sales, pos_sales)
    if normalized is not None and normalized > 0:
        return normalized
    cash_yen = int(cash_sales or 0)
    pos_yen = int(pos_sales or 0)
    if cash_yen > 0 and pos_yen == 0 and cash_yen % 980 == 0:
        units = cash_yen // 980
        if 1 <= units <= 99:
            return units
    return normalized


def _extract_labeled_amount(text: str, labels: tuple[str, ...]) -> tuple[Decimal | None, str | None]:
    for label in labels:
        escaped = re.escape(label)
        patterns = (
            rf"(?:^|\n)\s*(?:[-－]\s*)?{escaped}\s*(?:[¥￥]\s*)?([\d,/]+)",
            rf"(?:^|\n)\s*(?:[-－]\s*)?{escaped}\s*\n\s*(?:[¥￥]\s*)?([\d,/]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return sanitize_settlement_amount(match.group(1))
    return None, None


def _extract_settlement_amounts(text: str) -> tuple[dict[str, Decimal | None], dict[str, str]]:
    amounts: dict[str, Decimal | None] = {}
    corrections: dict[str, str] = {}
    for key, labels in _AMOUNT_FIELD_SPECS:
        amount, corrected_from = _extract_labeled_amount(text, labels)
        if amount is not None:
            amounts[key] = amount
        if corrected_from:
            corrections[key] = corrected_from
    return amounts, corrections


def _normalize_terminal_uuid_lines(text: str) -> str:
    return _TERMINAL_SPLIT_RE.sub(
        lambda match: f"端末番号: {match.group(1)}{match.group(2)}",
        text,
    )


def _normalize_settlement_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = normalized.replace("　", " ")
    normalized = re.sub(
        r"[-－]\s*PAYGATE\s*\n\s*POS",
        "PAYGATE POS",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"[-－]\s*PAYGATE\s*POS",
        "PAYGATE POS",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"PAYGATE\s*\n\s*POS", "PAYGATE POS", normalized, flags=re.IGNORECASE)
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
        amounts, amount_corrections = _extract_settlement_amounts(text)
        terminal_id = _extract_terminal_id(text)
        terminal_short_id = _extract_terminal_short_id(text, terminal_id)
        store_match = _STORE_RE.search(text)

        transaction_count = _infer_transaction_count_from_sales(
            amounts.get("cash"),
            amounts.get("pos"),
            _extract_transaction_count(text),
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
        return [parsed]
