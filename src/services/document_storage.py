"""Object storage helpers for persisted artifacts."""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path, PurePosixPath

from src.models.transaction import Invoice, Payout


class ObjectStorage:
    """Local object storage abstraction.

    The object key is kept DB-friendly so the backend can later swap the root
    to R2 or another object store without changing callers.
    """

    def __init__(self, root: Path | None = None):
        storage_root = root or Path(os.getenv("PDF_STORAGE_ROOT", "storage/pdfs"))
        self.root = storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, object_key: str, content: bytes) -> str:
        path = self.resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self.normalize_key(object_key)

    def read_bytes(self, object_key: str) -> bytes:
        return self.resolve_path(object_key).read_bytes()

    def exists(self, object_key: str) -> bool:
        return self.resolve_path(object_key).exists()

    def resolve_path(self, object_key: str) -> Path:
        normalized = self.normalize_key(object_key)
        return self.root.joinpath(*PurePosixPath(normalized).parts)

    @staticmethod
    def normalize_key(object_key: str) -> str:
        normalized = PurePosixPath(object_key.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("invalid object key")
        value = normalized.as_posix().strip("/")
        if not value:
            raise ValueError("object key is required")
        return value


class DocumentStorage(ObjectStorage):
    """Backward-compatible alias for PDF/document storage."""
    pass


def build_invoice_pdf_object_key(invoice: Invoice) -> str:
    return f"invoices/{invoice.period_key}/invoice_{invoice.id}_v{invoice.version}.pdf"



def build_payout_pdf_object_key(payout: Payout) -> str:
    return f"payouts/{payout.period_key}/payout_{payout.id}_v{payout.version}.pdf"


_ALLOWED_RECEIPT_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}


def build_receipt_object_key(expense_id: str, expense_date: date, original_name: str | None) -> str:
    raw_suffix = Path(original_name or "").suffix.lower()
    suffix = raw_suffix if raw_suffix in _ALLOWED_RECEIPT_SUFFIXES else ".bin"
    return f"receipts/{expense_date.strftime('%Y%m')}/expense_{expense_id}{suffix}"


_ALLOWED_REGISTRATION_FILE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


_ALLOWED_OCR_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def build_ocr_image_object_key(image_id: str, original_name: str | None) -> str:
    raw_suffix = Path(original_name or "").suffix.lower()
    suffix = raw_suffix if raw_suffix in _ALLOWED_OCR_SUFFIXES else ".jpg"
    return f"images/{image_id}{suffix}"


def build_registration_request_file_object_key(
    request_id: str,
    file_id: str,
    uploaded_at: date,
    original_name: str | None,
) -> str:
    raw_suffix = Path(original_name or "").suffix.lower()
    suffix = raw_suffix if raw_suffix in _ALLOWED_REGISTRATION_FILE_SUFFIXES else ".bin"
    return f"registration_requests/{uploaded_at.strftime('%Y%m')}/request_{request_id}/{file_id}{suffix}"
