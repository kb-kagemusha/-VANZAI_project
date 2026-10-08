"""Backward-compatible re-export. Prefer ocr_field_confidence."""
from src.services.ocr.parsers.ocr_field_confidence import (  # noqa: F401
    build_settlement_field_confidence,
    clamp_confidence,
    confidence_tone,
)
