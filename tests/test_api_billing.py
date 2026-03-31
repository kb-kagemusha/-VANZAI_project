"""billing mutation endpoints (generate/issue/confirm) の認証・認可テスト"""
import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.enums import UserRole


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
