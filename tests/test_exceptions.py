"""
カスタム例外のテスト
仕様参照: AGENTS.md - カスタム例外フレームワーク
"""
import pytest
from src.exceptions import (
    VANZAIException,
    PriceNotResolvedException,
    ClosingViolationException,
    DuplicateImportException,
    InvalidCSVFormatException,
    AssignmentCanceledException,
    InvoiceAlreadyIssuedException,
    PayoutAlreadyPaidException,
    PermissionDeniedException,
    RecordNotFoundException,
    ValidationException,
)


def test_base_exception_hierarchy():
    """すべてのカスタム例外がVANZAIExceptionを継承していること"""
    exceptions = [
        PriceNotResolvedException("test"),
        ClosingViolationException("test"),
        DuplicateImportException("test"),
        InvalidCSVFormatException("test"),
        AssignmentCanceledException("test"),
        InvoiceAlreadyIssuedException("test"),
        PayoutAlreadyPaidException("test"),
        PermissionDeniedException("test"),
        RecordNotFoundException("test"),
        ValidationException("test"),
    ]
    
    for exc in exceptions:
        assert isinstance(exc, VANZAIException)
        assert isinstance(exc, Exception)


def test_exception_message():
    """例外がメッセージを正しく保持すること"""
    exc = InvalidCSVFormatException("Invalid work_date format")
    assert str(exc) == "Invalid work_date format"
    assert exc.message == "Invalid work_date format"


def test_exception_code():
    """例外がコードを持つこと"""
    exc = ClosingViolationException("Already closed")
    assert exc.code == "CLOSING_VIOLATION"


def test_exception_details():
    """例外が詳細情報を保持できること"""
    details = {"project_id": "proj123", "period_key": "202601"}
    exc = ClosingViolationException("Already closed", details=details)
    assert exc.details == details
    assert exc.details["project_id"] == "proj123"


def test_record_not_found_exception():
    """RecordNotFoundExceptionが型とIDを保持すること"""
    exc = RecordNotFoundException("Invoice not found", details={"entity_type": "Invoice", "entity_id": "inv123"})
    assert "Invoice" in str(exc)
    assert exc.details["entity_type"] == "Invoice"
    assert exc.details["entity_id"] == "inv123"
    assert exc.details["entity_type"] == "Invoice"
    assert exc.details["entity_id"] == "inv123"


def test_price_not_resolved_exception():
    """PriceNotResolvedException詳細テスト"""
    details = {"worker_id": "w001", "role_id": "r001", "work_date": "2026-01-27"}
    exc = PriceNotResolvedException("Price not found", details=details)
    assert exc.code == "PRICE_NOT_RESOLVED"
    assert exc.details["worker_id"] == "w001"


def test_duplicate_import_exception():
    """DuplicateImportException詳細テスト"""
    details = {"file_hash": "abc123", "existing_batch_id": "batch001"}
    exc = DuplicateImportException("File already imported", details=details)
    assert exc.code == "DUPLICATE_IMPORT"
    assert exc.details["file_hash"] == "abc123"


def test_invalid_csv_format_exception():
    """InvalidCSVFormatException詳細テスト"""
    details = {"row": 42, "field": "work_date"}
    exc = InvalidCSVFormatException("Invalid date format", details=details)
    assert exc.code == "INVALID_CSV_FORMAT"
    assert exc.details["row"] == 42


def test_closing_violation_exception():
    """ClosingViolationException詳細テスト"""
    details = {"project_id": "p001", "period_key": "202601", "status": "hard_closed"}
    exc = ClosingViolationException("Cannot modify hard closed period", details=details)
    assert exc.code == "CLOSING_VIOLATION"
    assert exc.details["status"] == "hard_closed"


def test_invoice_already_issued_exception():
    """InvoiceAlreadyIssuedException詳細テスト"""
    details = {"invoice_id": "inv001", "status": "issued"}
    exc = InvoiceAlreadyIssuedException("Invoice already issued", details=details)
    assert exc.code == "INVOICE_ALREADY_ISSUED"
    assert exc.details["invoice_id"] == "inv001"


def test_payout_already_paid_exception():
    """PayoutAlreadyPaidException詳細テスト"""
    details = {"payout_id": "pay001", "status": "paid"}
    exc = PayoutAlreadyPaidException("Payout already paid", details=details)
    assert exc.code == "PAYOUT_ALREADY_PAID"
    assert exc.details["payout_id"] == "pay001"


def test_permission_denied_exception():
    """PermissionDeniedException詳細テスト"""
    details = {"user_id": "u001", "required_permission": "INVOICE_CREATE"}
    exc = PermissionDeniedException("Permission denied", details=details)
    assert exc.code == "PERMISSION_DENIED"
    assert exc.details["required_permission"] == "INVOICE_CREATE"


def test_assignment_canceled_exception():
    """AssignmentCanceledException詳細テスト"""
    details = {"assignment_id": "asn001", "canceled_at": "2026-01-27"}
    exc = AssignmentCanceledException("Assignment canceled", details=details)
    assert exc.code == "ASSIGNMENT_CANCELED"
    assert exc.details["assignment_id"] == "asn001"


def test_validation_exception():
    """ValidationException詳細テスト"""
    details = {"field": "amount", "value": "-100", "reason": "must be positive"}
    exc = ValidationException("Invalid amount", details=details)
    assert exc.code == "VALIDATION_ERROR"
    assert exc.details["field"] == "amount"


def test_exception_repr():
    """例外のrepr表現が適切であること"""
    exc = InvalidCSVFormatException("Test error", details={"row": 10})
    repr_str = repr(exc)
    assert "InvalidCSVFormatException" in repr_str
    assert "Test error" in repr_str


def test_exception_with_empty_details():
    """detailsがNoneでも動作すること"""
    exc = ClosingViolationException("Test error")
    assert exc.details is None or exc.details == {}


def test_exception_inheritance_chain():
    """例外の継承チェーンが正しいこと"""
    exc = InvoiceAlreadyIssuedException("test")
    assert isinstance(exc, VANZAIException)
    assert isinstance(exc, Exception)
    assert isinstance(exc, BaseException)
