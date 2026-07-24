"""Deduplication helpers for Paygate screenshot OCR rows."""
from __future__ import annotations

from src.services.ocr.models import ParsedOcrRow
from src.services.ocr.parsers.paygate_payment import count_payment_labels_in_block
from src.services.ocr.validation import validate_parsed_row


def paygate_rows_are_duplicates(left: ParsedOcrRow, right: ParsedOcrRow) -> bool:
    """Same transaction when receipt_no or transaction_no matches."""
    if left.receipt_no and right.receipt_no and left.receipt_no == right.receipt_no:
        return True
    if left.transaction_no and right.transaction_no and left.transaction_no == right.transaction_no:
        return True
    return False


def paygate_row_completeness_score(row: ParsedOcrRow) -> float:
    """Higher score means a more complete capture (prefer over partial screenshots)."""
    score = 0.0
    if row.record_date:
        score += 1.0
    if row.record_time:
        score += 1.0
    if row.amount is not None:
        score += 3.0
    if row.transaction_no:
        score += 2.0
    if row.receipt_no:
        score += 3.0
    if row.payment_method:
        score += 1.0
    score += row.confidence
    score -= len(validate_parsed_row(row)) * 2.0
    block = (row.raw_payload or {}).get("block", "")
    if isinstance(block, str):
        label_count = count_payment_labels_in_block(block)
        if label_count > 1:
            score -= 4.0
        if row.transaction_no and block.strip().startswith("20"):
            score += 1.5
        score += min(len(block) / 100.0, 2.0)
    return score


def dedupe_paygate_screenshot_rows(rows: list[ParsedOcrRow]) -> tuple[list[ParsedOcrRow], int]:
    """Merge duplicate Paygate rows, keeping the most complete record."""
    if not rows:
        return [], 0

    groups: list[list[ParsedOcrRow]] = []
    for row in rows:
        matched_group: list[ParsedOcrRow] | None = None
        for group in groups:
            if any(paygate_rows_are_duplicates(row, existing) for existing in group):
                matched_group = group
                break
        if matched_group is not None:
            matched_group.append(row)
        else:
            groups.append([row])

    deduped: list[ParsedOcrRow] = []
    skipped = 0
    for group in groups:
        best = max(group, key=paygate_row_completeness_score)
        deduped.append(best)
        skipped += len(group) - 1
    return deduped, skipped


def dedupe_paygate_screenshot_entries(
    entries: list[tuple[str, ParsedOcrRow]],
) -> tuple[list[tuple[str, ParsedOcrRow]], int]:
    """Deduplicate Paygate rows across images while keeping the source image id."""
    if not entries:
        return [], 0
    deduped_rows, skipped = dedupe_paygate_screenshot_rows([row for _, row in entries])
    result: list[tuple[str, ParsedOcrRow]] = []
    for deduped_row in deduped_rows:
        candidates = [
            (image_id, row)
            for image_id, row in entries
            if paygate_rows_are_duplicates(row, deduped_row)
        ]
        image_id, best_row = max(candidates, key=lambda item: paygate_row_completeness_score(item[1]))
        result.append((image_id, best_row))
    return result, skipped
