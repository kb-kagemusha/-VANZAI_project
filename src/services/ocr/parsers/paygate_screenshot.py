"""Parser for Paygate transaction history screenshots."""
from __future__ import annotations

import re

from src.services.ocr.confirm_metadata import metadata_from_parsed_fields
from src.services.ocr.dedupe import dedupe_paygate_screenshot_rows
from src.services.ocr.models import OcrEngineResult, ParsedOcrRow
from src.services.ocr.parsers.base import BaseOcrParser
from src.services.ocr.parsers.ocr_field_confidence import build_paygate_screenshot_field_confidence
from src.services.ocr.parsers.paygate_amount import extract_paygate_amount
from src.services.ocr.parsers.paygate_consensus import apply_paygate_image_consensus
from src.services.ocr.parsers.paygate_datetime import extract_paygate_datetime, normalize_paygate_ocr_text
from src.services.ocr.parsers.paygate_payment import normalize_paygate_payment_method
from src.services.ocr.parsers.paygate_receipt import extract_paygate_receipt_no
from src.services.ocr.validation import is_paygate_row_saveable, validate_parsed_row

_TXN_RE = re.compile(r"取引番号[\s\n]*(\d{6,8})")
_TXN_STANDALONE_RE = re.compile(r"(?<!\d)(1\d{6})(?!\d)")
_RECEIPT_ANCHOR_RE = re.compile(r"[107][0-9０-９]{12,14}")
_DATETIME_LINE_RE = re.compile(
    r"\d{4}[/,，.\-]\d{2}[/,，.\-]\d{2}[\s\n]+\d{2}:\d{2}:\d{2}"
)
_PAYMENT_RE = re.compile(r"決済方法[\s\n]*(\S+)")


def _extract_transaction_no(block: str) -> str | None:
    for line in block.splitlines():
        stripped = line.strip()
        if _TXN_STANDALONE_RE.fullmatch(stripped):
            return stripped

    standalone = _TXN_STANDALONE_RE.search(block)
    if standalone:
        return standalone.group(1)

    label_match = _TXN_RE.search(block)
    if label_match:
        candidate = label_match.group(1)
        if len(candidate) == 7 and _TXN_STANDALONE_RE.fullmatch(candidate):
            return candidate
        if len(candidate) == 6:
            extended = re.search(rf"(?<!\d){re.escape(candidate)}\d(?!\d)", block)
            if extended and _TXN_STANDALONE_RE.fullmatch(extended.group(0)):
                return extended.group(0)
    return None


def _iter_paygate_blocks(text: str) -> list[str]:
    normalized = normalize_paygate_ocr_text(text)
    blocks: list[str] = []
    seen: set[str] = set()

    def _add_block(part: str) -> None:
        part = part.strip()
        if not part or part in seen:
            return
        if _extract_transaction_no(part) or _DATETIME_LINE_RE.search(part):
            blocks.append(part)
            seen.add(part)

    split_patterns = (
        r"(?=\d{4}[/,，.\-]\d{2}[/,，.\-]\d{2}[\s\n]+\d{2}:\d{2}:\d{2})",
        r"(?=\d{4}[/,，.\-]\d{2}[/,，.\-]\d{2})",
        r"(?=取引番号)",
    )
    for pattern in split_patterns:
        for part in re.split(pattern, normalized):
            _add_block(part)

    for match in _RECEIPT_ANCHOR_RE.finditer(normalized):
        start = max(0, match.start() - 220)
        end = min(len(normalized), match.end() + 40)
        _add_block(normalized[start:end])

    return blocks


class PaygateScreenshotParser(BaseOcrParser):
    source_type = "paygate_screenshot"

    def parse(self, ocr_result: OcrEngineResult) -> list[ParsedOcrRow]:
        normalized_text = normalize_paygate_ocr_text(ocr_result.full_text)
        rows: list[ParsedOcrRow] = []

        for block in _iter_paygate_blocks(normalized_text):
            transaction_no = _extract_transaction_no(block)
            if not transaction_no:
                continue

            record_date, record_time, parsed_datetime_source = extract_paygate_datetime(block)
            amount, amount_meta = extract_paygate_amount(
                block,
                record_time or "",
                ocr_result.lines,
                has_transaction=True,
            )
            receipt_no = extract_paygate_receipt_no(block)
            payment_match = _PAYMENT_RE.search(block)
            payment_raw = payment_match.group(1) if payment_match else None
            confidences = [line.confidence for line in ocr_result.lines if line.confidence > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

            raw_payload = {"block": block, **amount_meta}
            if parsed_datetime_source in {"fuzzy", "missing"}:
                raw_payload["datetime_inferred"] = "fuzzy_or_missing"

            parsed = ParsedOcrRow(
                source_type=self.source_type,
                record_date=record_date,
                record_time=record_time,
                amount=amount,
                transaction_no=transaction_no,
                receipt_no=receipt_no,
                payment_method=normalize_paygate_payment_method(payment_raw),
                confidence=avg_conf,
                raw_payload=raw_payload,
            )
            parsed.validation_errors = validate_parsed_row(parsed)
            meta = metadata_from_parsed_fields(
                record_date=parsed.record_date,
                record_time=parsed.record_time,
                amount=parsed.amount,
                transaction_no=parsed.transaction_no,
                receipt_no=parsed.receipt_no,
                amount_meta=amount_meta,
                parsed_datetime_source=parsed_datetime_source,
                validation_errors=parsed.validation_errors or None,
            )
            parsed.amount_inferred = meta.amount_inferred
            parsed.amount_source = meta.amount_source
            parsed.datetime_source = meta.datetime_source
            parsed.confirm_required = meta.confirm_required
            field_confidence, field_sources = build_paygate_screenshot_field_confidence(
                ocr_result,
                parsed,
                amount_meta=amount_meta,
            )
            parsed.raw_payload["field_confidence"] = field_confidence
            parsed.raw_payload["field_sources"] = field_sources
            if not is_paygate_row_saveable(parsed):
                continue
            rows.append(parsed)

        apply_paygate_image_consensus(rows)
        deduped_rows, _ = dedupe_paygate_screenshot_rows(rows)
        return deduped_rows
