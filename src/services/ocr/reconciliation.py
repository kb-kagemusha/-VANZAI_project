"""HQ CSV reconciliation against OCR extracted rows."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from src.models.ocr import OcrExtractedRow


@dataclass
class HqCsvRow:
    index: int
    payload: dict[str, str]


@dataclass
class ReconciliationMatch:
    match_status: str
    ocr_row_id: str | None
    hq_row_index: int | None
    hq_payload: dict[str, str] | None
    amount_diff: Decimal | None
    notes: str | None = None


def parse_hq_csv(content: bytes) -> list[HqCsvRow]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[HqCsvRow] = []
    for index, row in enumerate(reader, start=1):
        rows.append(HqCsvRow(index=index, payload={k: (v or "").strip() for k, v in row.items()}))
    return rows


def _get_mapped(payload: dict[str, str], mapping: dict[str, str], field: str) -> str:
    column = mapping.get(field)
    if not column:
        return ""
    return payload.get(column, "").strip()


def _parse_decimal(value: str) -> Decimal | None:
    if not value:
        return None
    cleaned = value.replace("¥", "").replace("￥", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def reconcile_rows(
    ocr_rows: list[OcrExtractedRow],
    hq_rows: list[HqCsvRow],
    column_mapping: dict[str, str],
) -> list[ReconciliationMatch]:
    """Match OCR rows to HQ CSV using configurable column mapping."""
    key_fields = ("transaction_no", "receipt_no")
    hq_by_key: dict[tuple[str, str], HqCsvRow] = {}
    for hq in hq_rows:
        txn = _get_mapped(hq.payload, column_mapping, "transaction_no")
        receipt = _get_mapped(hq.payload, column_mapping, "receipt_no")
        if txn or receipt:
            hq_by_key[(txn, receipt)] = hq

    matches: list[ReconciliationMatch] = []
    matched_hq_indices: set[int] = set()

    for ocr in ocr_rows:
        key = (ocr.transaction_no or "", ocr.receipt_no or "")
        hq = hq_by_key.get(key)
        if hq is None and ocr.amount is not None and ocr.record_date:
            date_col = column_mapping.get("record_date")
            amount_col = column_mapping.get("amount")
            for candidate in hq_rows:
                if candidate.index in matched_hq_indices:
                    continue
                if date_col and candidate.payload.get(date_col, "")[:10].replace("-", "/") != ocr.record_date.isoformat().replace("-", "/"):
                    continue
                hq_amount = _parse_decimal(_get_mapped(candidate.payload, column_mapping, "amount"))
                if hq_amount is not None and hq_amount == ocr.amount:
                    hq = candidate
                    break

        if hq is None:
            matches.append(
                ReconciliationMatch(
                    match_status="ocr_only",
                    ocr_row_id=ocr.id,
                    hq_row_index=None,
                    hq_payload=None,
                    amount_diff=None,
                )
            )
            continue

        matched_hq_indices.add(hq.index)
        hq_amount = _parse_decimal(_get_mapped(hq.payload, column_mapping, "amount"))
        amount_diff = None
        status = "matched"
        if ocr.amount is not None and hq_amount is not None and ocr.amount != hq_amount:
            status = "amount_diff"
            amount_diff = ocr.amount - hq_amount

        matches.append(
            ReconciliationMatch(
                match_status=status,
                ocr_row_id=ocr.id,
                hq_row_index=hq.index,
                hq_payload=hq.payload,
                amount_diff=amount_diff,
            )
        )

    for hq in hq_rows:
        if hq.index in matched_hq_indices:
            continue
        matches.append(
            ReconciliationMatch(
                match_status="hq_only",
                ocr_row_id=None,
                hq_row_index=hq.index,
                hq_payload=hq.payload,
                amount_diff=None,
            )
        )

    return matches


def summarize_matches(matches: list[ReconciliationMatch]) -> dict[str, int]:
    summary = {
        "matched": 0,
        "ocr_only": 0,
        "hq_only": 0,
        "amount_diff": 0,
    }
    for match in matches:
        summary[match.match_status] = summary.get(match.match_status, 0) + 1
    return summary
