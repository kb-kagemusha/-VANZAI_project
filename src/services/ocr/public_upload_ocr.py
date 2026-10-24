"""Shared best-effort OCR for public upload classification and Paygate gate."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services.ocr.execution_lock import try_ocr_execution_lock
from src.services.ocr.image_preprocess import (
    preprocess_blue_amount_channel,
    preprocess_for_ocr,
    preprocess_upscaled_for_ocr,
)
from src.services.ocr.merge_results import merge_ocr_results
from src.services.ocr.models import OcrEngineResult
from src.services.ocr.paddle_engine import run_ocr


def run_public_upload_preview_ocr(
    session: Session,
    file_bytes: bytes,
    *,
    timeout_seconds: float = 5.0,
) -> tuple[OcrEngineResult | None, str | None]:
    """Run a lightweight OCR pass for public upload checks. Returns (result, skip_reason)."""
    with try_ocr_execution_lock(session, timeout_seconds=timeout_seconds) as acquired:
        if not acquired:
            return None, "lock_timeout"
        try:
            ocr_result = merge_ocr_results(
                run_ocr(preprocess_for_ocr(file_bytes)),
                run_ocr(preprocess_blue_amount_channel(file_bytes)),
                run_ocr(preprocess_upscaled_for_ocr(file_bytes)),
            )
            parser_rows_missing = not (ocr_result.full_text or "").strip()
            if parser_rows_missing:
                return ocr_result, "empty_text"
            return ocr_result, None
        except Exception:
            return None, "ocr_error"
