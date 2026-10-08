"""OCR API tests with mocked OCR engine."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.ocr import OcrExtractedRow, OcrSourceImage
from src.services.ocr.parsers.paygate_payment import PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE
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
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch(
                    "src.services.ocr_service.run_ocr",
                    return_value=run_ocr_from_text(PAYGATE_TEXT),
                ):
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


SETTLEMENT_LIKE_TEXT_WITHOUT_PAYMENT = """
2026/05/08 22:21:07
¥980
取引番号 1154100
レシート番号 7782464677325
小計 980
合計 980
"""


def test_ocr_parse_paygate_screenshot_rejects_missing_payment_method_label(
    api_client,
    db_session,
    accounting_user,
):
    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch(
                    "src.services.ocr_service.run_ocr",
                    return_value=run_ocr_from_text(SETTLEMENT_LIKE_TEXT_WITHOUT_PAYMENT),
                ):
                    upload = api_client.post(
                        "/api/ocr/images",
                        data={"source_type": "paygate_screenshot"},
                        files={"file": ("wrong.png", b"fake-image-bytes", "image/png")},
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
                    assert parse.json()["row_count"] == 0
                    assert parse.json()["failed_count"] == 1

                    images = api_client.get(
                        "/api/ocr/images",
                        headers=_auth_header(accounting_user.username),
                    )
                    assert images.status_code == 200
                    image = next(item for item in images.json()["items"] if item["id"] == image_id)
                    assert image["parse_status"] == "failed"
                    assert image["error_message"] == PAYGATE_SCREENSHOT_MISSING_PAYMENT_METHOD_MESSAGE


def test_ocr_parse_dedupes_overlapping_paygate_screenshots(api_client, db_session, accounting_user):
    partial_text = """
2026/05/08 22:21:07
¥980
取引番号 1154100
"""
    full_text = PAYGATE_TEXT

    with patch("src.services.ocr_service.preprocess_for_ocr", return_value=object()):
        with patch("src.services.ocr_service.preprocess_blue_amount_channel", return_value=object()):
            with patch("src.services.ocr_service.preprocess_upscaled_for_ocr", return_value=object()):
                with patch(
                    "src.services.ocr_service.run_ocr",
                    side_effect=[
                        run_ocr_from_text(partial_text),
                        run_ocr_from_text(partial_text),
                        run_ocr_from_text(partial_text),
                        run_ocr_from_text(full_text),
                        run_ocr_from_text(full_text),
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


def test_ocr_upload_restores_soft_deleted_duplicate(api_client, accounting_user):
    headers = _auth_header(accounting_user.username)
    payload = {"source_type": "paygate_screenshot"}
    files = {"file": ("restore-me.png", b"restore-image-bytes", "image/png")}

    upload = api_client.post("/api/ocr/images", data=payload, files=files, headers=headers)
    image_id = upload.json()["id"]

    deleted = api_client.request(
        "DELETE",
        "/api/ocr/images",
        json={"image_ids": [image_id]},
        headers=headers,
    )
    assert deleted.status_code == 200

    restored = api_client.post("/api/ocr/images", data=payload, files=files, headers=headers)
    assert restored.status_code == 200
    assert restored.json()["id"] == image_id
    assert restored.json()["reused_existing"] is True

    listing = api_client.get("/api/ocr/images", headers=headers)
    assert any(item["id"] == image_id for item in listing.json()["items"])


def test_ocr_upload_returns_reused_existing_for_duplicate_sha(api_client, accounting_user):
    headers = _auth_header(accounting_user.username)
    payload = {"source_type": "paygate_screenshot"}
    files = {"file": ("dup.png", b"same-image-bytes", "image/png")}

    first = api_client.post("/api/ocr/images", data=payload, files=files, headers=headers)
    second = api_client.post("/api/ocr/images", data=payload, files=files, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["reused_existing"] is True


def test_ocr_delete_images_soft_deletes(api_client, accounting_user):
    headers = _auth_header(accounting_user.username)
    upload = api_client.post(
        "/api/ocr/images",
        data={"source_type": "paygate_screenshot"},
        files={"file": ("delete-me.png", b"delete-image", "image/png")},
        headers=headers,
    )
    image_id = upload.json()["id"]

    deleted = api_client.request(
        "DELETE",
        "/api/ocr/images",
        json={"image_ids": [image_id]},
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1

    listing = api_client.get("/api/ocr/images", headers=headers)
    assert listing.status_code == 200
    assert all(item["id"] != image_id for item in listing.json()["items"])


def test_ocr_delete_images_cascades_related_rows(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="cascade-delete.png",
        storage_key="images/cascade-delete.jpg",
        sha256="cascade-delete-sha",
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
        transaction_no="1154099",
        status="pending_review",
        confirm_required=True,
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    headers = _auth_header(accounting_user.username)
    deleted = api_client.request(
        "DELETE",
        "/api/ocr/images",
        json={"image_ids": [image.id]},
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1

    listing = api_client.get("/api/ocr/rows", headers=headers)
    assert listing.status_code == 200
    assert all(item["id"] != row.id for item in listing.json()["items"])


def test_ocr_delete_rows_soft_deletes(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="row-delete.png",
        storage_key="images/row-delete.jpg",
        sha256="row-delete-sha",
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
        transaction_no="1154099",
        status="pending_review",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    headers = _auth_header(accounting_user.username)
    deleted = api_client.request(
        "DELETE",
        "/api/ocr/rows",
        json={"row_ids": [row.id]},
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_count"] == 1

    listing = api_client.get("/api/ocr/rows", headers=headers)
    assert listing.status_code == 200
    assert all(item["id"] != row.id for item in listing.json()["items"])


def test_ocr_rename_image_filename(api_client, accounting_user):
    headers = _auth_header(accounting_user.username)
    upload = api_client.post(
        "/api/ocr/images",
        data={"source_type": "paygate_screenshot"},
        files={"file": ("old-name.png", b"rename-image", "image/png")},
        headers=headers,
    )
    image_id = upload.json()["id"]

    renamed = api_client.patch(
        f"/api/ocr/images/{image_id}",
        json={"original_filename": "new-name.png"},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["original_filename"] == "new-name.png"


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


def test_ocr_export_all_csv_route(api_client, db_session, accounting_user):
    """/exports/all.csv が {period_key}.csv に誤マッチしないこと。"""
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_settlement",
        original_filename="settlement.jpg",
        storage_key="images/settlement.jpg",
        sha256="settlement1",
        size_bytes=10,
        parse_status="completed",
        uploaded_by=accounting_user.username,
    )
    row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=image.id,
        source_type="paygate_settlement",
        period_key="202607",
        record_date=date(2026, 7, 4),
        record_time="22:57:57",
        amount=Decimal("15680"),
        subtotal=Decimal("15680"),
        cash_sales=Decimal("5880"),
        pos_sales=Decimal("9800"),
        terminal_short_id="0b21",
        status="confirmed",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    response = api_client.get(
        "/api/ocr/exports/all.csv",
        params={"source_type": "paygate_settlement"},
        headers=_auth_header(accounting_user.username),
    )
    assert response.status_code == 200
    assert "paygate_settlement" in response.text
    assert "15680" in response.text
    assert 'filename="ocr_all_paygate_settlement.csv"' in response.headers.get("content-disposition", "")


def test_ocr_export_settlement_csv_route(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_settlement",
        original_filename="settlement2.jpg",
        storage_key="images/settlement2.jpg",
        sha256="settlement2",
        size_bytes=10,
        parse_status="completed",
        uploaded_by=accounting_user.username,
    )
    row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=image.id,
        source_type="paygate_settlement",
        period_key="202607",
        record_date=date(2026, 7, 4),
        record_time="22:57:57",
        amount=Decimal("15680"),
        terminal_short_id="0b21",
        status="confirmed",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    response = api_client.get(
        "/api/ocr/exports/settlement.csv",
        headers=_auth_header(accounting_user.username),
    )
    assert response.status_code == 200
    assert "terminal_short_id" in response.text
    assert "0b21" in response.text


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


def test_confirm_rejects_confirm_required_rows(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="x.png",
        storage_key="images/test3.jpg",
        sha256="ghi789",
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
        amount_inferred=True,
        amount_source="fallback_default",
        datetime_source="ocr_strict",
        confirm_required=True,
        status="pending_review",
    )
    ok_row = OcrExtractedRow(
        id=generate_ulid(),
        source_image_id=image.id,
        source_type="paygate_screenshot",
        period_key="202605",
        record_date=date(2026, 5, 9),
        record_time="10:00:00",
        amount=Decimal("980"),
        transaction_no="1154101",
        receipt_no="7782464677326",
        amount_inferred=False,
        amount_source="ocr",
        datetime_source="ocr_strict",
        confirm_required=False,
        status="pending_review",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.add(ok_row)
    db_session.commit()

    headers = _auth_header(accounting_user.username)
    response = api_client.post(
        "/api/ocr/rows/confirm",
        json={"row_ids": [row.id, ok_row.id]},
        headers=headers,
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert row.id in body["rejected_row_ids"]
    assert "amount_inferred" in body["reasons"][row.id]

    db_session.refresh(ok_row)
    assert ok_row.status == "pending_review"


def test_update_row_manual_edit_clears_confirm_required(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="x.png",
        storage_key="images/test4.jpg",
        sha256="jkl012",
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
        record_time="20:52:1",
        amount=Decimal("980"),
        transaction_no="1154100",
        receipt_no="7782464677325",
        amount_inferred=True,
        amount_source="fallback_default",
        datetime_source="fuzzy",
        confirm_required=True,
        status="pending_review",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    headers = _auth_header(accounting_user.username)
    response = api_client.patch(
        f"/api/ocr/rows/{row.id}",
        json={
            "record_date": "2026-05-08",
            "record_time": "20:52:59",
            "amount": "980",
            "transaction_no": "1154100",
            "receipt_no": "7782464677325",
            "payment_method": "現金",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["manually_edited"] is True
    assert body["amount_source"] == "manual"
    assert body["datetime_source"] == "manual"
    assert body["confirm_required"] is False


def test_list_rows_includes_metadata_fields(api_client, db_session, accounting_user):
    image = OcrSourceImage(
        id=generate_ulid(),
        source_type="paygate_screenshot",
        original_filename="x.png",
        storage_key="images/test5.jpg",
        sha256="mno345",
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
        amount_inferred=False,
        amount_source="ocr",
        datetime_source="ocr_strict",
        confirm_required=False,
        manually_edited=False,
        status="pending_review",
    )
    db_session.add(image)
    db_session.add(row)
    db_session.commit()

    response = api_client.get(
        "/api/ocr/rows",
        headers=_auth_header(accounting_user.username),
    )
    assert response.status_code == 200
    item = next(entry for entry in response.json()["items"] if entry["id"] == row.id)
    assert item["amount_source"] == "ocr"
    assert item["confirm_required"] is False
