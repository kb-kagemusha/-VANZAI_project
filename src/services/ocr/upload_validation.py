"""Validate uploaded image bytes for public OCR upload."""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

OCR_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_HEIC_EXTENSIONS = {".heic", ".heif"}
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),
)

HEIC_REJECTION_MESSAGE = (
    "iPhoneでアップロードできない場合は、カメラ設定を「互換性優先」にするか、"
    "JPEGとして保存してから再度お試しください。"
)


@dataclass(frozen=True)
class UploadValidationResult:
    ok: bool
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    error_code: str | None = None
    error_message: str | None = None


def _detect_mime(file_bytes: bytes) -> str | None:
    for signature, mime in _SIGNATURES:
        if file_bytes.startswith(signature):
            return mime
    if len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_upload_image_bytes(file_bytes: bytes, *, original_filename: str | None = None) -> UploadValidationResult:
    if not file_bytes:
        return UploadValidationResult(ok=False, error_code="empty", error_message="Empty file")
    if len(file_bytes) > OCR_UPLOAD_MAX_BYTES:
        return UploadValidationResult(ok=False, error_code="too_large", error_message="File too large")

    suffix = ""
    if original_filename and "." in original_filename:
        suffix = "." + original_filename.rsplit(".", 1)[-1].lower()
    if suffix in _HEIC_EXTENSIONS:
        return UploadValidationResult(
            ok=False,
            error_code="heic",
            error_message=HEIC_REJECTION_MESSAGE,
        )

    mime = _detect_mime(file_bytes)
    if mime is None:
        return UploadValidationResult(
            ok=False,
            error_code="unsupported_type",
            error_message="Unsupported image format",
        )

    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            image.verify()
        with Image.open(io.BytesIO(file_bytes)) as image:
            width, height = image.size
    except UnidentifiedImageError:
        return UploadValidationResult(
            ok=False,
            error_code="invalid_image",
            error_message="Invalid image file",
        )

    max_side = max(width, height)
    if max_side > 4096:
        return UploadValidationResult(
            ok=False,
            error_code="too_large",
            error_message="Image dimensions too large",
        )

    return UploadValidationResult(ok=True, mime_type=mime, width=width, height=height)
