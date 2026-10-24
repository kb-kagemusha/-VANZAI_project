"""Best-effort source_type classification for public OCR uploads."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from src.services.ocr.models import OcrEngineResult
from src.services.ocr.parsers.paygate_payment import paygate_screenshot_has_payment_method_label
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.parsers.paygate_settlement import PaygateSettlementParser, _SETTLEMENT_SIGNAL_RE
from src.services.ocr.public_upload_ocr import run_public_upload_preview_ocr

PUBLIC_AUTO_SOURCE_TYPE = "auto"


def classify_public_upload_source_type(ocr_result: OcrEngineResult) -> str:
    """Classify an upload as paygate_screenshot or paygate_settlement from OCR text."""
    text = ocr_result.full_text or ""
    has_payment_label = paygate_screenshot_has_payment_method_label(text)
    screenshot_rows = PaygateScreenshotParser().parse(ocr_result)
    settlement_rows = PaygateSettlementParser().parse(ocr_result)

    screenshot_score = 0
    settlement_score = 0

    if has_payment_label:
        screenshot_score += 6
    if screenshot_rows:
        screenshot_score += 3
        screenshot_score += sum(1 for row in screenshot_rows if row.payment_method)
    if re.search(r"取引番号", text):
        screenshot_score += 2

    if settlement_rows:
        settlement_score += 5
    if _SETTLEMENT_SIGNAL_RE.search(text):
        settlement_score += 2
    if re.search(r"精算", text) and re.search(r"小[計訳訁餁]|[合今会][計訳訁]", text):
        settlement_score += 2

    if has_payment_label:
        return "paygate_screenshot"
    if settlement_rows and settlement_score >= screenshot_score:
        return "paygate_settlement"
    if screenshot_rows and screenshot_score > settlement_score:
        return "paygate_screenshot"
    if settlement_score > screenshot_score:
        return "paygate_settlement"
    if _SETTLEMENT_SIGNAL_RE.search(text):
        return "paygate_settlement"
    return "paygate_screenshot"


def detect_public_upload_source_type(
    session: Session,
    file_bytes: bytes,
) -> tuple[str, OcrEngineResult | None, str]:
    """Run OCR and classify. Returns (source_type, ocr_result, reason)."""
    ocr_result, skip_reason = run_public_upload_preview_ocr(session, file_bytes)
    if ocr_result is None:
        return "paygate_screenshot", None, skip_reason or "ocr_unavailable"
    return classify_public_upload_source_type(ocr_result), ocr_result, "auto_detected"
