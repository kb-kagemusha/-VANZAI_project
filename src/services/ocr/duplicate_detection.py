"""Semantic duplicate detection for Paygate settlement receipts.

画像のSHA256一致だけでは、別角度撮影・トリミング・再圧縮された同一レシートの重複を
防げない（計画書 v4 §2.6）。そのため、OCR抽出後の主要項目が一致する場合は
`duplicate_receipt_candidate` として警告フラグを立てる（自動除外はしない）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.ocr import OcrExtractedRow


def find_duplicate_receipt_candidate(
    session: Session,
    *,
    terminal_short_id: str | None,
    record_date: date | None,
    record_time: str | None,
    amount: Decimal | None,
    transaction_count: int | None,
    exclude_row_id: str | None = None,
) -> str | None:
    """Return the id of an existing non-deleted settlement row sharing the same key
    fields, or None. Requires all key fields to be present to avoid false positives.
    """
    if not (terminal_short_id and record_date and record_time and amount is not None and transaction_count is not None):
        return None

    query = select(OcrExtractedRow.id).where(
        OcrExtractedRow.source_type == "paygate_settlement",
        OcrExtractedRow.deleted_at.is_(None),
        OcrExtractedRow.terminal_short_id == terminal_short_id,
        OcrExtractedRow.record_date == record_date,
        OcrExtractedRow.record_time == record_time,
        OcrExtractedRow.amount == amount,
        OcrExtractedRow.transaction_count == transaction_count,
    )
    if exclude_row_id:
        query = query.where(OcrExtractedRow.id != exclude_row_id)

    return session.execute(query).scalars().first()
