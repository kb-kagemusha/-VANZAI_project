"""Paygate screenshot receipt number extraction."""
from __future__ import annotations

import re

from src.services.ocr.parsers.paygate_amount import normalize_amount_text

_RECEIPT_LABEL_RE = re.compile(r"レ.{1,5}番号")
_PAYGATE_RECEIPT_LENGTH = 13


def normalize_receipt_digits(raw: str) -> str:
    return re.sub(r"\D", "", normalize_amount_text(raw))


def correct_paygate_receipt_digits(digits: str) -> str:
    """Fix common OCR misreads of Paygate receipt numbers (781… prefix)."""
    if len(digits) < _PAYGATE_RECEIPT_LENGTH:
        return digits
    trimmed = digits[:_PAYGATE_RECEIPT_LENGTH]
    if trimmed.startswith("781"):
        return trimmed
    if trimmed.startswith("101"):
        return "781" + trimmed[3:]
    if trimmed.startswith("701"):
        return "781" + trimmed[3:]
    return trimmed


def extract_paygate_receipt_no(block: str) -> str | None:
    """Extract 13-digit Paygate receipt number; tolerate OCR label/digit noise."""
    label_match = _RECEIPT_LABEL_RE.search(block)
    if label_match:
        segment = block[label_match.end() :].split("決済方法", 1)[0]
        lines = [line.strip() for line in segment.splitlines() if line.strip()]
        candidates: list[str] = []

        inline = re.search(r"([0-9０-９日]{10,18})", segment)
        if inline:
            candidates.append(inline.group(1))

        for line in lines[:3]:
            if _RECEIPT_LABEL_RE.search(line):
                continue
            if re.search(r"[0-9０-９日]", line):
                candidates.append(line)

        for raw in candidates:
            digits = correct_paygate_receipt_digits(normalize_receipt_digits(raw))
            if len(digits) < 10:
                continue
            if len(digits) >= _PAYGATE_RECEIPT_LENGTH and re.fullmatch(
                r"7[78]\d{11}", digits[:_PAYGATE_RECEIPT_LENGTH]
            ):
                return digits[:_PAYGATE_RECEIPT_LENGTH]
            if 10 <= len(digits) <= 15:
                return digits

    for raw in re.findall(r"[107][0-9０-９]{12,16}", block):
        digits = correct_paygate_receipt_digits(normalize_receipt_digits(raw))
        if len(digits) >= _PAYGATE_RECEIPT_LENGTH and re.fullmatch(
            r"7[78]\d{11}", digits[:_PAYGATE_RECEIPT_LENGTH]
        ):
            return digits[:_PAYGATE_RECEIPT_LENGTH]

    return None
