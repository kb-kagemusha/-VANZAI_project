"""Service-level tests for paygate_settlement lifecycle: parse -> confirm -> void /
reconciliation_eligible toggling, and semantic duplicate detection (計画書 v4 Phase 1a/1b)."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.services.ocr.paddle_engine import run_ocr_from_text
from src.services.ocr_service import OcrService

SETTLEMENT_TEXT = """
日本たばこ産業株式会社
精算
2026/06/13 19:10:23
端末番号: 98f0ec2f-fc54-4e00-a503-2ecb6659c7be
端末識別番号: f353
小計 ¥8,820
合計 ¥8,820
現金売上 ¥6,860
PAYGATE POS ¥1,960
通常取引数 9
消費税 ¥802
内税額 ¥802
"""


def _upload_and_parse(db_session, service: OcrService, text: str, filename: str = "receipt.png"):
    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(text)):
            image, _ = service.upload_image(
                file_bytes=text.encode("utf-8") + filename.encode(),
                file_name=filename,
                source_type="paygate_settlement",
                uploaded_by="tester",
            )
            db_session.flush()
            job = service.parse_images(image_ids=[image.id], executed_by="tester")
            db_session.flush()
    return job


def test_settlement_row_parsed_with_derived_fields(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT)
    rows, total = service.list_rows(source_type="paygate_settlement")
    assert total == 1
    row = rows[0]
    assert row.terminal_short_id == "f353"
    assert row.pos_sales == Decimal("1960")
    assert row.cash_sales == Decimal("6860")
    assert row.work_date == date(2026, 6, 13)
    assert row.reconciliation_eligible is True
    assert row.branch_id == "UNASSIGNED"
    assert row.duplicate_receipt_candidate is False


def test_settlement_row_confirmable_without_transaction_or_receipt_no(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT)
    rows, _ = service.list_rows(source_type="paygate_settlement")
    row = rows[0]
    assert row.transaction_no is None
    assert row.receipt_no is None

    confirmed_count = service.confirm_rows([row.id], actor="tester")
    assert confirmed_count == 1
    db_session.flush()
    assert row.status == "confirmed"


def test_duplicate_settlement_receipt_flags_candidate(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="receipt1.png")
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="receipt2.png")
    rows, total = service.list_rows(source_type="paygate_settlement")
    assert total == 2
    assert all(row.duplicate_receipt_candidate for row in rows)
    assert all("duplicate_receipt_candidate" in (row.warnings or []) for row in rows)


def test_void_row_requires_reason_and_marks_ineligible(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT)
    rows, _ = service.list_rows(source_type="paygate_settlement")
    row = rows[0]
    service.confirm_rows([row.id], actor="tester")

    with pytest.raises(ValueError):
        service.void_row(row.id, reason="  ", actor="tester")

    voided = service.void_row(row.id, reason="誤アップロード", actor="tester")
    assert voided.voided_at is not None
    assert voided.reconciliation_eligible is False


def test_set_reconciliation_eligible_conflict_is_prevented(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="a.png")
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="b.png")
    rows, _ = service.list_rows(source_type="paygate_settlement")
    row_a, row_b = rows[0], rows[1]

    service.confirm_rows([row_a.id], actor="tester")
    # exclude row_a from reconciliation first so row_b can take the unique key.
    service.set_reconciliation_eligible(row_a.id, eligible=False, excluded_reason="重複のため除外", actor="tester")
    db_session.flush()

    service.confirm_rows([row_b.id], actor="tester")
    db_session.flush()
    # row_b remains reconciliation_eligible=True by default and should be the sole eligible row.
    assert row_b.reconciliation_eligible is True

    # Re-enabling row_a while row_b already occupies the same key must fail via the
    # DB partial unique index (safety net for accidental duplicate eligibility).
    with pytest.raises(ValueError):
        service.set_reconciliation_eligible(row_a.id, eligible=True, excluded_reason=None, actor="tester")


def test_settlement_reparse_updates_existing_pending_row(db_session):
    service = OcrService(db_session)
    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="reparse.png")
    rows, total = service.list_rows(source_type="paygate_settlement")
    assert total == 1
    row = rows[0]
    row.terminal_short_id = "wrong"
    row.transaction_count = None
    db_session.flush()

    _upload_and_parse(db_session, service, SETTLEMENT_TEXT, filename="reparse.png")
    rows, total = service.list_rows(source_type="paygate_settlement")
    assert total == 1
    assert rows[0].id == row.id
    assert rows[0].terminal_short_id == "f353"
    assert rows[0].transaction_count == 9
