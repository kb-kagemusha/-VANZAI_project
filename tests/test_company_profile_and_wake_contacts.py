"""会社情報（請求書の発行元への連携）と、起床の目視確認の補助 W-1〜W-3（0.49.8、DEC-082）。"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from src.api.jwt_auth import create_user_with_hashed_password
from src.api.line_daily_routes import wake_next_action
from src.models.base import generate_ulid
from src.models.enums import InvoiceStatus
from src.models.line_daily import WakeContactLog
from src.models.master import Client
from src.models.order_billing import OrderBillingIssuer
from src.models.transaction import AuditLog, Invoice
from src.services import invoice_service
from src.services.company_profile import issuer_lines
from src.services.pdf_generator import PDFGenerator
from tests.test_api_line_order_requests import (  # noqa: F401  （fixture の再利用）
    FakeLine,
    _auth,
    fake_line,
    line_env,
    ops_user,
    pdf_root,
)
from tests.test_line_daily import _accepted_today


def _issuer(db_session):
    db_session.add(OrderBillingIssuer(id="default", revision=1, name="株式会社VANZAI", postal_code="116-0002",
        address="東京都荒川区荒川1丁目39-11", registration_number="T1234567890123", bank_details="", payment_terms="",
        phone="03-0000-0000", email="info@example.com", representative="代表 太郎"))
    db_session.commit()


# ---- W-3 今すること -------------------------------------------------------------

DAY = date(2026, 11, 2)


def _at(hour, minute=0):
    return datetime(2026, 11, 2, hour, minute)


def test_next_action_follows_runbook_steps():
    start = time(9, 0)
    step = lambda now, latest=None: wake_next_action(target=DAY, first_start=start, reported=False, latest_result=latest, now=now)  # noqa: E731
    assert step(_at(6, 30))["step"] == "wait" and step(_at(6, 30))["label"] == "07:00 からLINEで連絡"
    assert step(_at(7, 0))["label"] == "LINEで連絡する"
    assert step(_at(7, 10), "line_sent")["label"] == "返事を待つ（07:30 から電話）"
    assert step(_at(7, 30))["label"] == "電話する"
    assert step(_at(7, 40), "no_answer")["label"].startswith("もう一度電話する")
    assert step(_at(8, 0))["step"] == "site"
    assert step(_at(8, 10), "site_notified")["label"] == "現場へ連絡済み。返事を待つ"
    assert step(_at(9, 0))["step"] == "started"
    assert step(_at(8, 0), "confirmed_awake")["step"] == "resolved"
    assert step(_at(8, 0), "absent")["label"] == "欠勤"
    reported = wake_next_action(target=DAY, first_start=start, reported=True, latest_result=None, now=_at(8, 0))
    assert reported["step"] == "reported"
    # 先に対応すべき順：開始を過ぎた > 現場へ連絡 > 電話 > LINE > 返事待ち > 時刻前 > 報告あり
    order = [step(_at(9, 0)), step(_at(8, 0)), step(_at(7, 30)), step(_at(7, 0)), step(_at(7, 10), "line_sent"), step(_at(6, 0)), reported]
    assert [o["priority"] for o in order] == sorted(o["priority"] for o in order)


# ---- W-1・W-2 ------------------------------------------------------------------

def test_wake_status_shows_phone_and_records_contacts(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    worker.phone = "090-1111-2222"
    db_session.commit()
    auth = _auth(ops_user.username)
    status = api_client.get("/api/line-daily/wake-status", headers=auth).json()
    item = status["items"][0]
    assert item["phone"] == "090-1111-2222"
    assert item["contacts"] == [] and "step" in item["next_action"]

    today = status["date"]
    bad = api_client.post("/api/line-daily/wake-contacts", headers=auth, json={"day": today, "worker_id": worker.id, "result": "other"})
    assert bad.status_code == 400
    saved = api_client.post("/api/line-daily/wake-contacts", headers=auth,
        json={"day": today, "worker_id": worker.id, "result": "confirmed_awake", "note": "7:35 本人と話した"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["result_label"] == "電話で起床を確認"

    item = api_client.get("/api/line-daily/wake-status", headers=auth).json()["items"][0]
    assert [c["result"] for c in item["contacts"]] == ["confirmed_awake"]
    assert item["contacts"][0]["note"] == "7:35 本人と話した"
    assert item["next_action"]["step"] in ("resolved", "reported")
    db_session.expire_all()
    assert db_session.query(WakeContactLog).count() == 1
    assert db_session.query(AuditLog).filter(AuditLog.action == "wake_contact_recorded").count() == 1


def test_wake_contacts_require_wake_status_permission(api_client, db_session, pdf_root, line_env, fake_line):
    create_user_with_hashed_password(db_session, "acct_only", "acct_only@example.com", "pass123", "accounting")
    response = api_client.post("/api/line-daily/wake-contacts", headers=_auth("acct_only"),
        json={"day": "2026-11-02", "worker_id": "x", "result": "line_sent"})
    assert response.status_code == 403


# ---- 会社情報 -------------------------------------------------------------------

def test_company_profile_is_admin_only_and_updates_issuer(api_client, db_session):
    _issuer(db_session)
    create_user_with_hashed_password(db_session, "company_admin", "company_admin@example.com", "pass123", "admin")
    create_user_with_hashed_password(db_session, "company_ops", "company_ops@example.com", "pass123", "ops")
    assert api_client.get("/api/company-profile", headers=_auth("company_ops")).status_code == 403
    auth = _auth("company_admin")
    profile = api_client.get("/api/company-profile", headers=auth).json()
    assert profile["phone"] == "03-0000-0000" and profile["representative"] == "代表 太郎"
    revision = profile.pop("revision")
    profile.update(phone="03-1234-5678", address="東京都千代田区1-1")
    updated = api_client.put("/api/company-profile", headers=auth, json={**profile, "expected_revision": revision})
    assert updated.status_code == 200, updated.text
    assert updated.json()["phone"] == "03-1234-5678" and updated.json()["revision"] == revision + 1
    # 請求書の発行元設定と同じ内容
    assert api_client.get("/api/order-billing/issuer", headers=auth).json()["address"] == "東京都千代田区1-1"
    stale = api_client.put("/api/company-profile", headers=auth, json={**profile, "expected_revision": revision})
    assert stale.status_code == 409


def test_issued_invoice_keeps_company_profile_at_issue_time(db_session):
    _issuer(db_session)
    client = Client(id=generate_ulid(), name="請求先")
    db_session.add(client)
    db_session.flush()
    draft = Invoice(id=generate_ulid(), client_id=client.id, period_key="202611", billing_date=date(2026, 11, 30), version=1,
        status=InvoiceStatus.PREPARING.value, subtotal=Decimal("1000"), tax_amount=Decimal("100"), total_amount=Decimal("1100"))
    db_session.add(draft)
    db_session.commit()
    issued = invoice_service.issue_invoice(db_session, draft.id, "tester")
    db_session.commit()
    assert issued.issuer_snapshot["phone"] == "03-0000-0000"

    row = db_session.get(OrderBillingIssuer, "default")
    row.phone = "03-9999-9999"
    row.revision += 1
    db_session.commit()
    db_session.refresh(issued)
    assert issued.issuer_snapshot["phone"] == "03-0000-0000"  # 発行後に会社情報を変えても、発行済みは変わらない
    reissued = invoice_service.reissue_invoice(session=db_session, invoice_id=issued.id, user_id="tester")
    assert reissued.issuer_snapshot["phone"] == "03-9999-9999"  # 再発行は新しい発行

    pdf = PDFGenerator().generate_invoice_pdf(issued, [], issuer=issued.issuer_snapshot)
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_issuer_lines_skip_empty_fields():
    assert issuer_lines(None) == []
    assert issuer_lines({"name": "株式会社VANZAI", "phone": "", "address": "東京都"}) == ["株式会社VANZAI", "東京都"]
    lines = issuer_lines({"name": "A", "postal_code": "116-0002", "phone": "03", "email": "a@b", "representative": "代表", "registration_number": "T1"})
    assert lines == ["A", "代表者：代表", "〒116-0002", "TEL：03", "メール：a@b", "登録番号：T1"]
