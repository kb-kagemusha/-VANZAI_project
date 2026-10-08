"""Service-level tests for OCR image reparse."""
from decimal import Decimal
from unittest.mock import patch

from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr_service import OcrService

PAYGATE_SCREENSHOT_TEXT = """
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
決済方法 現金
2026/05/08 22:20:36
¥980
取引番号 1154098
レシート番号 7782464367325
決済方法 現金
"""


def _upload_and_parse_ss(db_session, service: OcrService, text: str, filename: str = "ss.png"):
    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(text)):
                    image, _ = service.upload_image(
                        file_bytes=text.encode("utf-8"),
                        file_name=filename,
                        source_type="paygate_screenshot",
                        uploaded_by="tester",
                    )
                    db_session.flush()
                    job = service.parse_images(image_ids=[image.id], executed_by="tester")
                    db_session.flush()
    return image, job


def test_screenshot_image_reparse_replaces_all_rows(db_session):
    service = OcrService(db_session)
    image, _ = _upload_and_parse_ss(db_session, service, PAYGATE_SCREENSHOT_TEXT, filename="ss-image-reparse.png")
    rows, total = service.list_rows(source_type="paygate_screenshot")
    assert total == 2
    old_ids = {row.id for row in rows}
    for row in rows:
        row.amount = Decimal("1")
    db_session.flush()

    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(PAYGATE_SCREENSHOT_TEXT)):
                    job = service.reparse_image(image_id=image.id, executed_by="tester")
    db_session.flush()

    assert job.row_count == 2
    refreshed_rows, total = service.list_rows(source_type="paygate_screenshot")
    assert total == 2
    assert {row.id for row in refreshed_rows}.isdisjoint(old_ids)
    assert {row.transaction_no for row in refreshed_rows} == {"1154100", "1154098"}
    assert all(row.amount == Decimal("980") for row in refreshed_rows)


def test_screenshot_image_reparse_blocked_when_confirmed_exists(db_session):
    service = OcrService(db_session)
    image, _ = _upload_and_parse_ss(db_session, service, PAYGATE_SCREENSHOT_TEXT, filename="ss-image-reparse-block.png")
    rows, _ = service.list_rows(source_type="paygate_screenshot")
    rows[0].status = "confirmed"
    db_session.flush()

    try:
        service.reparse_image(image_id=image.id, executed_by="tester")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Confirmed rows prevent image reparse" in str(exc)
