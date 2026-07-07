"""Tests for OCR public upload links."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models.ocr  # noqa: F401
from src.models.base import Base
from src.models.ocr import OcrUploadLink
from src.services.ocr.upload_validation import validate_upload_image_bytes
from src.services.ocr_upload_link_service import (
    OcrUploadLinkService,
    hash_upload_token,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_validate_upload_rejects_empty():
    result = validate_upload_image_bytes(b"")
    assert result.ok is False
    assert result.error_code == "empty"


def test_validate_upload_accepts_minimal_jpeg():
    from PIL import Image
    import io

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(buffer, format="JPEG")
    result = validate_upload_image_bytes(buffer.getvalue(), original_filename="test.jpg")
    assert result.ok is True
    assert result.mime_type == "image/jpeg"


def test_hash_upload_token_is_stable():
    assert hash_upload_token("abc") == hash_upload_token("abc")
    assert hash_upload_token("abc") != hash_upload_token("def")


def test_create_upload_link_returns_token(db_session):
    service = OcrUploadLinkService(db_session)
    link, token = service.create_link(
        created_by="tester",
        label="test",
        expires_in_days=7,
        public_memo=None,
        internal_memo=None,
        default_source_type="required",
        period_key=None,
        max_upload_count=10,
    )
    db_session.commit()
    assert link.token_suffix == token[-6:]
    assert link.id
    assert service.get_link_by_token(token) is not None


def test_revoked_link_blocks_session(db_session):
    service = OcrUploadLinkService(db_session)
    link, token = service.create_link(
        created_by="tester",
        label=None,
        expires_in_days=1,
        public_memo=None,
        internal_memo=None,
        default_source_type="required",
        period_key=None,
        max_upload_count=None,
    )
    _, session_token = service.create_session(link)
    service.revoke_link(link.id, actor="admin")
    db_session.commit()
    with pytest.raises(PermissionError):
        service.resolve_session(session_token)


def test_rate_limit_blocks_after_limit(db_session):
    from src.services.ocr_upload_link_service import _increment_rate_limit

    for _ in range(5):
        assert _increment_rate_limit(db_session, "test:scope", limit=5) is True
    assert _increment_rate_limit(db_session, "test:scope", limit=5) is False


def test_uploader_display_name_rules():
    from src.services.ocr_service import OcrService

    assert OcrService._uploader_display_name("田中", "external", "public_link") == "田中"
    assert OcrService._uploader_display_name(None, "ops_user", None) == "管理者"
    assert OcrService._uploader_display_name(None, "external", "public_link") is None


def test_public_upload_requires_uploader_name(db_session, monkeypatch):
    monkeypatch.setenv("OCR_PUBLIC_PAYGATE_PRECHECK_ENABLED", "false")
    from io import BytesIO

    from PIL import Image

    service = OcrUploadLinkService(db_session)
    link, _ = service.create_link(
        created_by="tester",
        label=None,
        expires_in_days=1,
        public_memo=None,
        internal_memo=None,
        default_source_type="required",
        period_key=None,
        max_upload_count=None,
    )
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="white").save(buffer, format="JPEG")
    with pytest.raises(ValueError, match="uploader_name_required"):
        service.handle_public_upload(
            link=link,
            source_type="paygate_settlement",
            file_bytes=buffer.getvalue(),
            file_name="test.jpg",
            public_uploader_name="  ",
            client_ip=None,
            user_agent=None,
        )


def test_paygate_precheck_disabled_skips(db_session, monkeypatch):
    monkeypatch.setenv("OCR_PUBLIC_PAYGATE_PRECHECK_ENABLED", "false")
    from src.services.ocr.paygate_screenshot_gate import (
        evaluate_paygate_screenshot_gate,
        is_public_paygate_precheck_enabled,
    )

    assert is_public_paygate_precheck_enabled() is False
    result = evaluate_paygate_screenshot_gate(db_session, b"not-an-image")
    assert result.passed is True
    assert result.skipped is True
    assert result.skip_reason == "feature_disabled"
