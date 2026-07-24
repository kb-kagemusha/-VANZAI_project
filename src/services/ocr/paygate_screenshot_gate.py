"""Best-effort Paygate screenshot gate for public upload."""
from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.services.ocr.image_preprocess import preprocess_upscaled_for_ocr
from src.services.ocr.merge_results import merge_ocr_results
from src.services.ocr.models import OcrEngineResult
from src.services.ocr.paddle_engine import run_ocr
from src.services.ocr.parsers.paygate_payment import (
    PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE,
    paygate_screenshot_has_payment_method_label,
)
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.public_upload_ocr import run_public_upload_preview_ocr


@dataclass(frozen=True)
class PaygateGateResult:
    passed: bool
    rejected: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    payment_method_count: int = 0
    message: str | None = None


def is_public_paygate_precheck_enabled() -> bool:
    value = os.getenv("OCR_PUBLIC_PAYGATE_PRECHECK_ENABLED", "true").lower()
    return value not in {"0", "false", "no"}


def evaluate_paygate_screenshot_gate(
    session: Session,
    file_bytes: bytes,
    *,
    ocr_result: OcrEngineResult | None = None,
) -> PaygateGateResult:
    """Run best-effort OCR gate. Reject only when payment-method label is clearly missing."""
    if not is_public_paygate_precheck_enabled():
        return PaygateGateResult(passed=True, skipped=True, skip_reason="feature_disabled")

    try:
        if ocr_result is None:
            ocr_result, skip_reason = run_public_upload_preview_ocr(session, file_bytes)
            if ocr_result is None:
                return PaygateGateResult(passed=True, skipped=True, skip_reason=skip_reason or "ocr_unavailable")

        parser = PaygateScreenshotParser()
        parsed_rows = parser.parse(ocr_result)
        if not parsed_rows:
            parsed_rows = parser.parse(
                merge_ocr_results(ocr_result, run_ocr(preprocess_upscaled_for_ocr(file_bytes)))
            )

        payment_method_count = sum(1 for row in parsed_rows if row.payment_method)
        if payment_method_count > 0:
            return PaygateGateResult(passed=True, payment_method_count=payment_method_count)

        if not paygate_screenshot_has_payment_method_label(ocr_result.full_text):
            if parsed_rows:
                return PaygateGateResult(
                    passed=False,
                    rejected=True,
                    payment_method_count=0,
                    message=PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE,
                )
            return PaygateGateResult(passed=True, skipped=True, skip_reason="no_rows")

        return PaygateGateResult(passed=True, payment_method_count=0)
    except Exception:
        return PaygateGateResult(passed=True, skipped=True, skip_reason="ocr_error")
