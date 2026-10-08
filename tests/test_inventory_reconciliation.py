"""Tests for InventoryReconciliationService (計画書 v4 Phase 2b).

Covers snapshot CRUD (adjustment_count sign convention, required reason) and the
reconciliation run's match_status classification: matched / adjusted_matched /
count_mismatch / sales_only / inventory_only.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.models.ocr import OcrExtractedRow
from src.services.inventory_reconciliation import InventoryReconciliationService
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


def _make_confirmed_settlement_row(db_session, *, transaction_count: int = 9) -> OcrExtractedRow:
    service = OcrService(db_session)
    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(SETTLEMENT_TEXT)):
            image, _ = service.upload_image(
                file_bytes=SETTLEMENT_TEXT.encode("utf-8") + b"receipt.png",
                file_name="receipt.png",
                source_type="paygate_settlement",
                uploaded_by="tester",
            )
            db_session.flush()
            service.parse_images(image_ids=[image.id], executed_by="tester")
            db_session.flush()
    rows, _ = service.list_rows(source_type="paygate_settlement")
    row = rows[0]
    if transaction_count != row.transaction_count:
        row.transaction_count = transaction_count
    service.confirm_rows([row.id], actor="tester")
    db_session.flush()
    return row


def test_create_snapshot_requires_reason_when_adjustment_nonzero(db_session):
    service = InventoryReconciliationService(db_session)
    with pytest.raises(ValueError):
        service.create_snapshot(
            branch_id="UNASSIGNED",
            terminal_short_id="f353",
            work_date=date(2026, 6, 13),
            staff_id=None,
            opening_count=20,
            closing_count=12,
            adjustment_count=1,
            adjustment_reason="  ",
            note=None,
            actor="tester",
        )


def test_inventory_decrease_uses_adjustment_sign_convention(db_session):
    service = InventoryReconciliationService(db_session)
    # 20 - 12 - 1(non-sale decrease) = 7 相当減数
    snapshot = service.create_snapshot(
        branch_id="UNASSIGNED",
        terminal_short_id="f353",
        work_date=date(2026, 6, 13),
        staff_id=None,
        opening_count=20,
        closing_count=12,
        adjustment_count=1,
        adjustment_reason="破損1個",
        note=None,
        actor="tester",
    )
    assert snapshot.inventory_decrease == 7


def test_reconciliation_matched(db_session):
    row = _make_confirmed_settlement_row(db_session, transaction_count=9)
    inv_service = InventoryReconciliationService(db_session)
    inv_service.create_snapshot(
        branch_id=row.branch_id,
        terminal_short_id=row.terminal_short_id,
        work_date=row.work_date,
        staff_id=None,
        opening_count=20,
        closing_count=11,
        adjustment_count=0,
        adjustment_reason=None,
        note=None,
        actor="tester",
    )
    db_session.flush()

    batch = inv_service.run_reconciliation(
        date_from=row.work_date, date_to=row.work_date, period_key=None, executed_by="tester"
    )
    results = inv_service.list_batch_results(batch.id)
    assert len(results) == 1
    assert results[0].match_status == "matched"
    assert results[0].diff == 0
    assert batch.matched_count == 1


def test_reconciliation_adjusted_matched(db_session):
    row = _make_confirmed_settlement_row(db_session, transaction_count=9)
    inv_service = InventoryReconciliationService(db_session)
    # opening-closing-adjustment = 20-11-1 = 8... need diff==0 -> transaction_count(9) == inventory_decrease
    # 20 - 10 - 1 = 9 -> matches transaction_count 9, with a non-zero adjustment present.
    inv_service.create_snapshot(
        branch_id=row.branch_id,
        terminal_short_id=row.terminal_short_id,
        work_date=row.work_date,
        staff_id=None,
        opening_count=20,
        closing_count=10,
        adjustment_count=1,
        adjustment_reason="破損1個",
        note=None,
        actor="tester",
    )
    db_session.flush()

    batch = inv_service.run_reconciliation(
        date_from=row.work_date, date_to=row.work_date, period_key=None, executed_by="tester"
    )
    results = inv_service.list_batch_results(batch.id)
    assert results[0].match_status == "adjusted_matched"
    assert batch.adjusted_matched_count == 1


def test_reconciliation_count_mismatch(db_session):
    row = _make_confirmed_settlement_row(db_session, transaction_count=9)
    inv_service = InventoryReconciliationService(db_session)
    inv_service.create_snapshot(
        branch_id=row.branch_id,
        terminal_short_id=row.terminal_short_id,
        work_date=row.work_date,
        staff_id=None,
        opening_count=20,
        closing_count=13,  # decrease=7, but OCR says 9 -> mismatch
        adjustment_count=0,
        adjustment_reason=None,
        note=None,
        actor="tester",
    )
    db_session.flush()

    batch = inv_service.run_reconciliation(
        date_from=row.work_date, date_to=row.work_date, period_key=None, executed_by="tester"
    )
    results = inv_service.list_batch_results(batch.id)
    assert results[0].match_status == "count_mismatch"
    assert results[0].diff == 2
    assert batch.count_mismatch_count == 1


def test_reconciliation_sales_only_when_no_snapshot(db_session):
    row = _make_confirmed_settlement_row(db_session, transaction_count=9)
    inv_service = InventoryReconciliationService(db_session)

    batch = inv_service.run_reconciliation(
        date_from=row.work_date, date_to=row.work_date, period_key=None, executed_by="tester"
    )
    results = inv_service.list_batch_results(batch.id)
    assert len(results) == 1
    assert results[0].match_status == "sales_only"
    assert batch.sales_only_count == 1


def test_reconciliation_inventory_only_when_no_ocr_row(db_session):
    inv_service = InventoryReconciliationService(db_session)
    inv_service.create_snapshot(
        branch_id="UNASSIGNED",
        terminal_short_id="f999",
        work_date=date(2026, 6, 20),
        staff_id=None,
        opening_count=10,
        closing_count=8,
        adjustment_count=0,
        adjustment_reason=None,
        note=None,
        actor="tester",
    )
    db_session.flush()

    batch = inv_service.run_reconciliation(
        date_from=date(2026, 6, 20), date_to=date(2026, 6, 20), period_key=None, executed_by="tester"
    )
    results = inv_service.list_batch_results(batch.id)
    assert len(results) == 1
    assert results[0].match_status == "inventory_only"
    assert batch.inventory_only_count == 1


def test_update_result_rejects_unknown_diff_reason_category(db_session):
    row = _make_confirmed_settlement_row(db_session, transaction_count=9)
    inv_service = InventoryReconciliationService(db_session)
    inv_service.create_snapshot(
        branch_id=row.branch_id,
        terminal_short_id=row.terminal_short_id,
        work_date=row.work_date,
        staff_id=None,
        opening_count=20,
        closing_count=13,
        adjustment_count=0,
        adjustment_reason=None,
        note=None,
        actor="tester",
    )
    db_session.flush()
    batch = inv_service.run_reconciliation(
        date_from=row.work_date, date_to=row.work_date, period_key=None, executed_by="tester"
    )
    result = inv_service.list_batch_results(batch.id)[0]

    with pytest.raises(ValueError):
        inv_service.update_result(result.id, {"diff_reason_category": "not_a_real_category"}, actor="tester")

    updated = inv_service.update_result(result.id, {"diff_reason_category": "ocr_error"}, actor="tester")
    assert updated.diff_reason_category == "ocr_error"
