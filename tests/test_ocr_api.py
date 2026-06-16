"""OCR API tests with mocked OCR engine."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.ocr import OcrExtractedRow, OcrSourceImage
from src.services.ocr.parsers.paygate_screenshot import PaygateScreenshotParser
from src.services.ocr.paddle_engine import run_ocr_from_text


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


PAYGATE_TEXT = """
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
決済方法 現金
"""


@pytest.fixture
def accounting_user(db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="ocr_accounting",
        email="ocr_accounting@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()
    return user


def test_ocr_upload_requires_auth(api_client):
    response = api_client.post(
        "/api/ocr/images",
        data={"source_type": "paygate_screenshot"},
        files={"file": ("test.png", b"fake-image", "image/png")},
    )
    assert response.status_code == 401


def test_ocr_upload_and_parse_with_mock(api_client, db_session, accounting_user):
    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.run_ocr", return_value=run_ocr_from_text(PAYGATE_TEXT)):
            upload = api_client.post(
                "/api/ocr/images",
                data={"source_type": "paygate_screenshot"},
                files={"file": ("test.png", b"fake-image-bytes", "image/png")},
                headers=_auth_header(accounting_user.username),
            )
            assert upload.status_code == 200
            image_id = upload.json()["id"]

            parse = api_client.post(
                "/api/ocr/jobs/parse",
                json={"image_ids": [image_id]},
                headers=_auth_header(accounting_user.username),
            )
            assert parse.status_code == 200
            assert parse.json()["row_count"] == 1

            rows = api_client.get(
                "/api/ocr/rows",
                headers=_auth_header(accounting_user.username),
            )
            assert rows.status_code == 200
            assert rows.json()["total"] == 1
            assert rows.json()["items"][0]["transaction_no"] == "1154100"


def test_ocr_parse_dedupes_overlapping_paygate_screenshots(api_client, db_session, accounting_user):
    partial_text = """
2026/05/08 22:21:07
¥980
取引番号 1154100
"""
    full_text = PAYGATE_TEXT

    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch(
            "src.services.ocr_service.run_ocr",
            side_effect=[
                run_ocr_from_text(partial_text),
                run_ocr_from_text(full_text),
            ],
        ):
            upload_partial = api_client.post(
                "/api/ocr/images",
                data={"source_type": "paygate_screenshot"},
                files={"file": ("partial.png", b"partial-image", "image/png")},
                headers=_auth_header(accounting_user.username),
            )
            upload_full = api_client.post(
                "/api/ocr/images",
                data={"source_type": "paygate_screenshot"},
                files={"file": ("full.png", b"full-image", "image/png")},
                headers=_auth_header(accounting_user.username),
            )
            image_ids = [upload_partial.json()["id"], upload_full.json()["id"]]

            parse = api_client.post(
                "/api/ocr/jobs/parse",
                json={"image_ids": image_ids},
                headers=_auth_header(accounting_user.username),
            )
            assert parse.status_code == 200
            assert parse.json()["row_count"] == 1

            rows = api_client.get(
                "/api/ocr/rows",
                headers=_auth_header(accounting_user.username),
            )
            assert rows.status_code == 200
            assert rows.json()["total"] == 1
            item = rows.json()["items"][0]
            assert item["transaction_no"] == "1154100"
            assert item["receipt_no"] == "7782464677325"


def test_ocr_export_csv(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="x.png",
        storage_key="images/test.jpg",
        sha256="abc123",
        size_bytes=10,
        parse_status="completed",
        uploaded_by=accounting_user.username,
    )
    row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=image.id,
        source_type="paygate_screenshot",
        period_key="202605",
        record_date=date(2026, 5, 8),
        record_time="22:21:07",
        amount=Decimal("980"),
        transaction_no="1154100",
        receipt_no="7782464677325",
        status="confirmed",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    response = api_client.get(
        "/api/ocr/exports/202605.csv",
        headers=_auth_header(accounting_user.username),
    )
    assert response.status_code == 200
    assert "1154100" in response.text
    assert "transaction_no" in response.text


def test_ocr_reconciliation_endpoint(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="x.png",
        storage_key="images/test2.jpg",
        sha256="def456",
        size_bytes=10,
        parse_status="completed",
        uploaded_by=accounting_user.username,
    )
    row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=image.id,
        source_type="paygate_screenshot",
        period_key="202605",
        record_date=date(2026, 5, 8),
        amount=Decimal("980"),
        transaction_no="1154100",
        receipt_no="7782464677325",
        status="confirmed",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    hq_csv = "取引番号,レシート番号,金額\n1154100,7782464677325,980\n"
    response = api_client.post(
        "/api/ocr/reconciliation",
        data={
            "column_mapping": '{"transaction_no":"取引番号","receipt_no":"レシート番号","amount":"金額"}',
            "period_key": "202605",
        },
        files={"file": ("hq.csv", hq_csv.encode("utf-8-sig"), "text/csv")},
        headers=_auth_header(accounting_user.username),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched_count"] == 1
