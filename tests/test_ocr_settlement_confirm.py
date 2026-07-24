"""Regression tests for the paygate_settlement confirm-rejection bug.

計画書 v4 Phase 0-Step2 / Phase 1a: `confirm_metadata.get_confirm_rejection_reasons()`
が source_type に関わらず transaction_no / receipt_no を必須としていたため、
精算レシート（paygate_settlement）の行が一切確定できなかった既知バグの動的再現・修正確認。
"""
from datetime import date
from types import SimpleNamespace

from src.services.ocr.confirm_metadata import get_confirm_rejection_reasons


def _settlement_row(**overrides) -> SimpleNamespace:
    base = dict(
        deleted_at=None,
        status="pending_review",
        source_type="paygate_settlement",
        record_date=date(2026, 6, 13),
        record_time="19:10:23",
        amount=8820,
        transaction_count=9,
        terminal_short_id="f353",
        transaction_no=None,
        receipt_no=None,
        blocking_errors=None,
        voided_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_settlement_row_without_transaction_or_receipt_no_is_confirmable():
    """既知バグの再現・修正確認: 精算行は取引番号/レシート番号が無くても確定できる。"""
    row = _settlement_row()
    reasons = get_confirm_rejection_reasons(row)
    assert reasons == []


def test_settlement_row_with_blocking_errors_is_rejected():
    row = _settlement_row(blocking_errors=["amount_breakdown_mismatch"])
    reasons = get_confirm_rejection_reasons(row)
    assert "blocking_errors" in reasons


def test_settlement_row_missing_terminal_short_id_is_rejected():
    row = _settlement_row(terminal_short_id=None)
    reasons = get_confirm_rejection_reasons(row)
    assert "missing_terminal_short_id" in reasons


def test_settlement_row_invalid_terminal_short_id_is_rejected():
    row = _settlement_row(terminal_short_id="f35")
    reasons = get_confirm_rejection_reasons(row)
    assert "invalid_terminal_short_id" in reasons


def test_settlement_row_missing_transaction_count_is_rejected():
    row = _settlement_row(transaction_count=None)
    reasons = get_confirm_rejection_reasons(row)
    assert "missing_transaction_count" in reasons


def test_settlement_voided_row_is_rejected():
    from datetime import datetime, timezone

    row = _settlement_row(voided_at=datetime.now(timezone.utc))
    reasons = get_confirm_rejection_reasons(row)
    assert "voided" in reasons


def test_screenshot_row_still_requires_transaction_and_receipt_no():
    """既存の paygate_screenshot 挙動は変更しない（回帰防止）。"""
    row = SimpleNamespace(
        deleted_at=None,
        status="pending_review",
        source_type="paygate_screenshot",
        confirm_required=False,
        validation_errors=None,
        record_date=date(2026, 6, 13),
        record_time="19:10:23",
        amount=980,
        transaction_no=None,
        receipt_no=None,
    )
    reasons = get_confirm_rejection_reasons(row)
    assert "missing_transaction_no" in reasons
    assert "missing_receipt_no" in reasons
