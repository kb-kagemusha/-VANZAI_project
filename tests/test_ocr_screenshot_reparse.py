"""Service-level tests for Paygate screenshot row reparse."""
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
    return job


def test_screenshot_reparse_updates_target_row_only(db_session):
    service = OcrService(db_session)
    _upload_and_parse_ss(db_session, service, PAYGATE_SCREENSHOT_TEXT, filename="ss-reparse.png")
    rows, total = service.list_rows(source_type="paygate_screenshot")
    assert total == 2
    target = next(row for row in rows if row.transaction_no == "1154100")
    target.amount = Decimal("1")
    db_session.flush()

    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(PAYGATE_SCREENSHOT_TEXT)):
                    job = service.reparse_row(row_id=target.id, executed_by="tester")
    db_session.flush()
    assert job.row_count == 1

    refreshed = db_session.get(type(target), target.id)
    all_rows, _ = service.list_rows(source_type="paygate_screenshot")
    other = next(row for row in all_rows if row.transaction_no == "1154098")
    assert refreshed.amount == Decimal("980")
    assert other.amount == Decimal("980")
