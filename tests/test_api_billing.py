"""billing mutation endpoints (generate/issue/confirm) の認証・認可テスト"""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import InvoiceStatus, PayoutStatus, UserRole
from src.models.master import Client, ClientStaff, VanzaiStaff, Worker
from src.models.transaction import Actual, ImportBatch, Invoice, Payout, PayoutDelivery, Project, ShiftSlot, Assignment


def _auth_header(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


# ── 請求書生成 ──────────────────────────────────────────


def test_generate_invoice_requires_auth(api_client, project):
    """未認証の場合 401 を返す"""
    response = api_client.post(
        "/api/invoices/generate",
        json={"project_id": project.id, "period_key": "202601"},
    )
    assert response.status_code == 401


def test_generate_invoice_forbidden_for_viewer(api_client, db_session, project):
    """WORKER ロールは INVOICE_GENERATE 権限がないため 403 を返す"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="viewer_gen_inv",
        email="viewer_gen_inv@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/generate",
        json={"project_id": project.id, "period_key": "202601"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_generate_invoice_accounting_returns_200_or_400(api_client, db_session, project):
    """OPS ロールは権限があり 200 or 400（実績なし）を返す"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_gen_inv",
        email="accounting_gen_inv@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/generate",
        json={"project_id": project.id, "period_key": "202601"},
        headers=_auth_header(user.username),
    )
    # 実績がない場合は空の請求書（200）か業務エラー（400）が返る
    assert response.status_code in (200, 400)


def _create_import_batch(db_session, project_id: str, period_key: str) -> ImportBatch:
    batch = ImportBatch(
        id=generate_ulid(),
        submitted_by="pytest",
        submit_channel="test",
        file_name="test.csv",
        file_hash=f"hash-{project_id}-{period_key}",
        project_id=project_id,
        period_key=period_key,
        status="completed",
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def _create_actual(
    db_session,
    *,
    project: Project,
    worker: Worker,
    role_id: str,
    work_date: date,
    import_batch: ImportBatch,
) -> Actual:
    shift_slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=work_date,
    )
    db_session.add(shift_slot)
    db_session.flush()

    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role_id,
        status="confirmed",
    )
    db_session.add(assignment)
    db_session.flush()

    actual = Actual(
        id=generate_ulid(),
        project_id=project.id,
        worker_id=worker.id,
        role_id=role_id,
        assignment_id=assignment.id,
        import_batch_id=import_batch.id,
        work_date=work_date,
        period_key="202601",
        status="active",
        calc_minutes_total=480,
        calc_minutes_break=0,
        calc_minutes_billable=480,
        applied_price_sales=Decimal("2000.00"),
        applied_price_outsource=Decimal("1200.00"),
    )
    db_session.add(actual)
    db_session.flush()
    return actual


def test_generate_vanzai_staff_playing_manager_man_day_payout(api_client, db_session, client, worker, role):
    managed_project = Project(
        id=generate_ulid(),
        name="Managed Project",
        code="MP001",
        client_id=client.id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
    )
    second_project = Project(
        id=generate_ulid(),
        name="Managed Project 2",
        code="MP002",
        client_id=client.id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
    )
    db_session.add_all([managed_project, second_project])
    db_session.flush()

    staff = VanzaiStaff(
        id=generate_ulid(),
        name="PM担当者",
        role="プレイングマネージャー",
        playing_manager_fee_type="subordinate_man_days",
        is_active=True,
    )
    db_session.add(staff)
    db_session.flush()

    managed_project.vanzai_manager_id = staff.id
    second_project.vanzai_manager_id = staff.id

    import_batch_1 = _create_import_batch(db_session, managed_project.id, "202601")
    import_batch_2 = _create_import_batch(db_session, second_project.id, "202601")

    _create_actual(
        db_session,
        project=managed_project,
        worker=worker,
        role_id=role.id,
        work_date=date(2026, 1, 15),
        import_batch=import_batch_1,
    )
    _create_actual(
        db_session,
        project=second_project,
        worker=worker,
        role_id=role.id,
        work_date=date(2026, 1, 15),
        import_batch=import_batch_2,
    )

    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_pm_payout",
        email="ops_pm_payout@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/generate",
        json={
            "recipient_type": "vanzai_staff",
            "recipient_id": staff.id,
            "period_key": "202601",
            "support_fee_amount": "3000",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipient_type"] == "vanzai_staff"
    assert Decimal(payload["total_amount"]) == Decimal("5000")
    assert any(line["description"] == "現場管理報酬（配下人工×1,000円）" and Decimal(line["amount"]) == Decimal("2000") for line in payload["lines"])
    assert any(line["description"] == "運営協力費" and Decimal(line["amount"]) == Decimal("3000") for line in payload["lines"])


def test_generate_vanzai_staff_playing_manager_fixed_payout(api_client, db_session, project):
    staff = VanzaiStaff(
        id=generate_ulid(),
        name="固定PM担当者",
        role="プレイングマネージャー",
        playing_manager_fee_type="fixed_amount",
        playing_manager_fixed_fee=Decimal("100000.00"),
        is_active=True,
    )
    db_session.add(staff)

    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_fixed_pm_payout",
        email="ops_fixed_pm_payout@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/generate",
        json={
            "recipient_type": "vanzai_staff",
            "recipient_id": staff.id,
            "period_key": "202601",
            "support_fee_amount": "5000",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert Decimal(payload["total_amount"]) == Decimal("105000")
    assert any(line["description"] == "現場管理報酬（固定）" and Decimal(line["amount"]) == Decimal("100000") for line in payload["lines"])
    assert any(line["description"] == "運営協力費" and Decimal(line["amount"]) == Decimal("5000") for line in payload["lines"])


def test_generate_invoice_unknown_project_returns_404(api_client, db_session):
    """存在しない project_id は 404 を返す"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_inv_404",
        email="accounting_inv_404@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/generate",
        json={"project_id": "NOTEXIST", "period_key": "202601"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 404


def test_generate_invoice_with_issue_metadata_and_fixed_office_fee(api_client, db_session, client, project, worker, role):
    client.contact_name = "既定担当者"

    client_staff = ClientStaff(
        id=generate_ulid(),
        client_id=client.id,
        name="請求担当者",
        email="billing-contact@example.com",
        is_active=True,
    )
    db_session.add(client_staff)
    db_session.flush()

    import_batch = _create_import_batch(db_session, project.id, "202601")
    _create_actual(
        db_session,
        project=project,
        worker=worker,
        role_id=role.id,
        work_date=date(2026, 1, 15),
        import_batch=import_batch,
    )

    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_invoice_issue_meta",
        email="ops_invoice_issue_meta@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/generate",
        json={
            "project_id": project.id,
            "period_key": "202601",
            "document_type": "invoice",
            "client_staff_id": client_staff.id,
            "subject": "2026年1月分_請求テスト",
            "fixed_office_fee_amount": "5000",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "invoice"
    assert payload["subject"] == "2026年1月分_請求テスト"
    assert payload["addressee_company_name"] == client.name
    assert payload["addressee_name"] == client_staff.name
    assert Decimal(payload["fixed_office_fee_amount"]) == Decimal("5000")
    assert Decimal(payload["total_amount"]) == Decimal("23100")
    assert any(line["description"] == "固定事務局費" and Decimal(line["amount"]) == Decimal("5000") for line in payload["lines"])


# ── 請求書発行 ──────────────────────────────────────────


def test_issue_invoice_requires_auth(api_client):
    """未認証の場合 401 を返す"""
    response = api_client.post("/api/invoices/FAKE_ID/issue")
    assert response.status_code == 401


def test_issue_invoice_forbidden_for_viewer(api_client, db_session):
    """WORKER ロールは 403"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="viewer_issue_inv",
        email="viewer_issue_inv@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/FAKE_ID/issue",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_issue_invoice_accounting_returns_400_for_missing(api_client, db_session):
    """ACCOUNTING ロールで存在しない invoice_id は 400 (業務エラー)"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_issue_inv",
        email="accounting_issue_inv@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/invoices/NOTEXIST/issue",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 400


def test_issue_invoice_saves_pdf_storage_key(api_client, db_session, project, client, monkeypatch, tmp_path):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_issue_inv_success",
        email="accounting_issue_inv_success@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    invoice = Invoice(
        id=generate_ulid(),
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 1, 31),
        status=InvoiceStatus.PREPARING.value,
        version=1,
        subtotal=Decimal("10000.00"),
        tax_amount=Decimal("1000.00"),
        total_amount=Decimal("11000.00"),
    )
    db_session.add(invoice)
    db_session.commit()

    response = api_client.post(
        f"/api/invoices/{invoice.id}/issue",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    db_session.refresh(invoice)
    assert invoice.pdf_object_key == f"invoices/202601/invoice_{invoice.id}_v1.pdf"
    assert (Path(tmp_path) / invoice.pdf_object_key).exists()


def test_download_invoice_pdf_requires_auth(api_client):
    response = api_client.get("/api/invoices/FAKE_ID/pdf")
    assert response.status_code == 401


def test_download_invoice_pdf_returns_pdf(api_client, db_session, client, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_invoice_pdf",
        email="accounting_invoice_pdf@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    invoice = Invoice(
        id=generate_ulid(),
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 1, 31),
        status=InvoiceStatus.ISSUED.value,
        version=1,
        subtotal=Decimal("10000"),
        tax_amount=Decimal("1000"),
        total_amount=Decimal("11000"),
        issued_at=datetime.now(),
    )
    db_session.add(invoice)
    db_session.commit()

    response = api_client.get(
        f"/api/invoices/{invoice.id}/pdf",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_download_invoice_pdf_rejects_preparing_invoice(api_client, db_session, client, project):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_invoice_pdf_preparing",
        email="accounting_invoice_pdf_preparing@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    invoice = Invoice(
        id=generate_ulid(),
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 1, 31),
        status=InvoiceStatus.PREPARING.value,
        version=1,
        subtotal=Decimal("10000"),
        tax_amount=Decimal("1000"),
        total_amount=Decimal("11000"),
    )
    db_session.add(invoice)
    db_session.commit()

    response = api_client.get(
        f"/api/invoices/{invoice.id}/pdf",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 400


# ── 支払明細生成 ────────────────────────────────────────


def test_generate_payout_requires_auth(api_client, project, worker):
    """未認証の場合 401"""
    response = api_client.post(
        "/api/payouts/generate",
        json={"project_id": project.id, "worker_id": worker.id, "period_key": "202601"},
    )
    assert response.status_code == 401


def test_generate_payout_forbidden_for_viewer(api_client, db_session, project, worker):
    """WORKER ロールは 403"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="viewer_gen_payout",
        email="viewer_gen_payout@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/generate",
        json={"project_id": project.id, "worker_id": worker.id, "period_key": "202601"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_generate_payout_accounting_returns_200_or_400(api_client, db_session, project, worker):
    """OPS ロールは権限あり"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_gen_payout",
        email="accounting_gen_payout@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/generate",
        json={"project_id": project.id, "worker_id": worker.id, "period_key": "202601"},
        headers=_auth_header(user.username),
    )
    assert response.status_code in (200, 400)


# ── 支払確定 ────────────────────────────────────────────


def test_confirm_payout_requires_auth(api_client):
    """未認証の場合 401"""
    response = api_client.post("/api/payouts/FAKE_ID/confirm")
    assert response.status_code == 401


def test_confirm_payout_forbidden_for_viewer(api_client, db_session):
    """WORKER ロールは 403"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="viewer_confirm_payout",
        email="viewer_confirm_payout@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/NOTEXIST/confirm",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_confirm_payout_accounting_returns_400_for_missing(api_client, db_session):
    """ACCOUNTING ロールで存在しない payout_id は 400"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_confirm_payout",
        email="accounting_confirm_payout@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/NOTEXIST/confirm",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 400


def test_confirm_payout_saves_pdf_storage_key(api_client, db_session, project, worker, monkeypatch, tmp_path):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_confirm_payout_success",
        email="accounting_confirm_payout_success@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.PREPARING.value,
        version=1,
        total_amount=Decimal("9000"),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.post(
        f"/api/payouts/{payout.id}/confirm",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    db_session.refresh(payout)
    assert payout.pdf_object_key == f"payouts/202601/payout_{payout.id}_v1.pdf"
    assert (Path(tmp_path) / payout.pdf_object_key).exists()


def test_mark_payout_paid_requires_auth(api_client):
    response = api_client.post("/api/payouts/FAKE_ID/paid")
    assert response.status_code == 401


def test_mark_payout_paid_forbidden_for_viewer(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="viewer_mark_payout_paid",
        email="viewer_mark_payout_paid@example.com",
        password="secret123",
        role=UserRole.WORKER.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/NOTEXIST/paid",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_mark_payout_paid_accounting_returns_400_for_missing(api_client, db_session):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_mark_payout_paid",
        email="accounting_mark_payout_paid@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/payouts/NOTEXIST/paid",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 400


def test_mark_payout_paid_updates_status(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_mark_payout_paid_success",
        email="accounting_mark_payout_paid_success@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("9000"),
        approved_at=datetime.now(),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.post(
        f"/api/payouts/{payout.id}/paid",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "paid"
    assert payload["paid_at"] is not None


def test_download_payout_pdf_returns_pdf(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_payout_pdf",
        email="accounting_payout_pdf@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("9000"),
        approved_at=datetime.now(),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.get(
        f"/api/payouts/{payout.id}/pdf",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_download_payout_pdf_rejects_preparing_payout(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_payout_pdf_preparing",
        email="accounting_payout_pdf_preparing@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.PREPARING.value,
        version=1,
        total_amount=Decimal("9000"),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.get(
        f"/api/payouts/{payout.id}/pdf",
        headers=_auth_header(user.username),
    )
    assert response.status_code == 400


def test_deliver_payout_requires_auth(api_client):
    response = api_client.post("/api/payouts/FAKE_ID/deliver", json={})
    assert response.status_code == 401


def test_deliver_payout_records_delivery_and_saves_pdf(api_client, db_session, project, worker, monkeypatch, tmp_path):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_deliver_payout",
        email="accounting_deliver_payout@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.APPROVED.value,
        version=2,
        total_amount=Decimal("9000"),
        approved_at=datetime.now(),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.post(
        f"/api/payouts/{payout.id}/deliver",
        json={},
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["payout_id"] == payout.id
    assert payload["recipient_email"] == worker.email
    assert payload["status"] == "sent"
    assert payload["pdf_storage_key"] == f"payouts/202601/payout_{payout.id}_v2.pdf"

    db_session.refresh(payout)
    assert payout.pdf_object_key == f"payouts/202601/payout_{payout.id}_v2.pdf"
    assert (Path(tmp_path) / payout.pdf_object_key).exists()

    delivery = db_session.get(PayoutDelivery, payload["id"])
    assert delivery is not None
    assert delivery.delivered_by == user.username
    assert delivery.status == "sent"


def test_deliver_payout_accepts_recipient_override(api_client, db_session, project, worker, monkeypatch, tmp_path):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_deliver_payout_override",
        email="accounting_deliver_payout_override@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("EMAIL_DRY_RUN", "true")

    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("9000"),
        approved_at=datetime.now(),
    )
    db_session.add(payout)
    db_session.commit()

    response = api_client.post(
        f"/api/payouts/{payout.id}/deliver",
        json={
            "recipient_email": "override@example.com",
            "delivery_note": "メール差し戻し後の再送",
            "internal_note": "担当確認済み",
        },
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recipient_email"] == "override@example.com"
    assert payload["delivery_note"] == "メール差し戻し後の再送"
    assert payload["internal_note"] == "担当確認済み"

    delivery = db_session.get(PayoutDelivery, payload["id"])
    assert delivery is not None
    assert delivery.recipient_email == "override@example.com"
    assert delivery.delivery_note == "メール差し戻し後の再送"
    assert delivery.internal_note == "担当確認済み"


def test_list_payout_deliveries_returns_delivery_history(api_client, db_session, project, worker):
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_list_payout_deliveries",
        email="accounting_list_payout_deliveries@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    payout = Payout(
        id=generate_ulid(),
        worker_id=worker.id,
        project_id=project.id,
        period_key="202601",
        payment_date=date(2026, 1, 31),
        status=PayoutStatus.APPROVED.value,
        version=1,
        total_amount=Decimal("9000"),
        approved_at=datetime.now(),
        pdf_object_key="payouts/202601/test.pdf",
    )
    db_session.add(payout)
    db_session.flush()

    delivery = PayoutDelivery(
        id=generate_ulid(),
        payout_id=payout.id,
        recipient_email="dest@example.com",
        status="sent",
        provider="gmail",
        delivered_by=user.username,
        pdf_object_key_snapshot=payout.pdf_object_key,
        sent_at=datetime.now(),
    )
    db_session.add(delivery)
    db_session.commit()

    response = api_client.get(
        f"/api/payouts/{payout.id}/deliveries",
        headers=_auth_header(user.username),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == delivery.id
    assert payload["items"][0]["recipient_email"] == "dest@example.com"
    assert payload["items"][0]["pdf_storage_key"] == payout.pdf_object_key
    assert payload["items"][0]["delivery_note"] is None
    assert payload["items"][0]["internal_note"] is None


# ── 月次一括生成 ────────────────────────────────────────


def test_generate_monthly_billing_requires_auth(api_client):
    """未認証の場合 401"""
    response = api_client.post(
        "/api/billing/generate-monthly",
        json={"period_key": "202601"},
    )
    assert response.status_code == 401


def test_generate_monthly_billing_forbidden_for_accounting(api_client, db_session):
    """ACCOUNTING ロールは一括生成権限がないため 403"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_monthly_billing",
        email="accounting_monthly_billing@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/billing/generate-monthly",
        json={"period_key": "202601"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


# ── 締め処理 ────────────────────────────────────────────


def test_close_soft_requires_auth(api_client, project):
    """未認証の場合 401"""
    response = api_client.post(
        "/api/closing/soft",
        json={"project_id": project.id, "period_key": "202601", "reason": "月次確定"},
    )
    assert response.status_code == 401


def test_close_soft_ops_succeeds(api_client, db_session, project):
    """OPS ロールは soft close を実行できる"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="ops_soft_close",
        email="ops_soft_close@example.com",
        password="secret123",
        role=UserRole.OPS.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/closing/soft",
        json={"project_id": project.id, "period_key": "202601", "reason": "月次確定"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "soft_closed"
    assert payload["closed_by"] == user.username


def test_close_hard_requires_auth(api_client, project):
    """未認証の場合 401"""
    response = api_client.post(
        "/api/closing/hard",
        json={"project_id": project.id, "period_key": "202601", "approver": "user2", "reason": "月次確定"},
    )
    assert response.status_code == 401


def test_close_hard_rejects_same_approver(api_client, db_session, project):
    """本締めは実行者と承認者が同一だと 400"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_hard_close",
        email="accounting_hard_close@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    soft_response = api_client.post(
        "/api/closing/soft",
        json={"project_id": project.id, "period_key": "202601", "reason": "月次確定"},
        headers=_auth_header(user.username),
    )
    assert soft_response.status_code == 200

    hard_response = api_client.post(
        "/api/closing/hard",
        json={"project_id": project.id, "period_key": "202601", "approver": user.username, "reason": "月次確定"},
        headers=_auth_header(user.username),
    )
    assert hard_response.status_code == 400


def test_release_soft_close_requires_auth(api_client, project):
    """未認証の仮締め解除は 401"""
    response = api_client.post(
        "/api/closing/soft/release",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "再取込"},
    )
    assert response.status_code == 401


def test_release_soft_close_forbidden_for_accounting(api_client, db_session, project):
    """ACCOUNTING ロールは仮締め解除権限がないため 403"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="accounting_soft_release",
        email="accounting_soft_release@example.com",
        password="secret123",
        role=UserRole.ACCOUNTING.value,
    )
    db_session.commit()

    response = api_client.post(
        "/api/closing/soft/release",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "再取込"},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 403


def test_release_soft_close_admin_succeeds(api_client, db_session, project):
    """ADMIN は仮締め解除を実行できる"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_soft_release",
        email="admin_soft_release@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    close_response = api_client.post(
        "/api/closing/soft",
        json={"project_id": project.id, "period_key": "202601", "reason": "締め"},
        headers=_auth_header(user.username),
    )
    assert close_response.status_code == 200

    release_response = api_client.post(
        "/api/closing/soft/release",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "再取込"},
        headers=_auth_header(user.username),
    )
    assert release_response.status_code == 200
    payload = release_response.json()
    assert payload["status"] == "open"
    assert payload["release_count"] == 1
    assert payload["last_release_reason"] == "再取込"


def test_release_hard_close_requires_auth(api_client, project):
    """未認証の本締め解除は 401"""
    response = api_client.post(
        "/api/closing/hard/release",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "例外解除"},
    )
    assert response.status_code == 401


def test_release_hard_close_admin_succeeds(api_client, db_session, project):
    """ADMIN は本締め解除を実行できる"""
    user = create_user_with_hashed_password(
        db=db_session,
        username="admin_hard_release",
        email="admin_hard_release@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()

    soft_response = api_client.post(
        "/api/closing/soft",
        json={"project_id": project.id, "period_key": "202601", "reason": "締め"},
        headers=_auth_header(user.username),
    )
    assert soft_response.status_code == 200

    hard_response = api_client.post(
        "/api/closing/hard",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "締め"},
        headers=_auth_header(user.username),
    )
    assert hard_response.status_code == 200

    release_response = api_client.post(
        "/api/closing/hard/release",
        json={"project_id": project.id, "period_key": "202601", "approver": "admin2", "reason": "例外解除"},
        headers=_auth_header(user.username),
    )
    assert release_response.status_code == 200
    payload = release_response.json()
    assert payload["status"] == "soft_closed"
    assert payload["release_count"] == 1
    assert payload["last_release_reason"].startswith("HARD_CLOSE_RELEASE:")
