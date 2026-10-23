"""DEC-074: admin secrecy, append-only amounts, frozen monthly lines, duplicate prevention."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import importlib.util
from io import StringIO

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from alembic.operations import Operations
from alembic.migration import MigrationContext
from src.api.jwt_auth import create_user_with_hashed_password
from src.models.access_policy import RoleAccessPolicy
from src.models.master import Client
from src.models.order_request import OrderRequestDocument
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoice, OrderBillingInvoiceLine, OrderBillingTaxRule, OrderBillingIssuer
from src.models.transaction import Invoice
from src.services.document_storage import DocumentStorage
from tests.test_api_order_requests import _auth, _worker, pdf_root  # noqa: F401
from tests.test_line_daily import _create_confirm, _payload, _revise_confirm


@pytest.fixture
def admin_user(db_session):
    user = create_user_with_hashed_password(db_session, "billing_admin", "billing_admin@example.com", "pass123", "admin")
    db_session.add(OrderBillingTaxRule(id="standard-10-floor-v1", rate=Decimal("0.10"), rounding="floor_yen"))
    db_session.add(OrderBillingIssuer(id="default", revision=1, name="株式会社VANZAI", postal_code="116-0002",
        address="東京都荒川区荒川1丁目39-11 東京アルバタワー1703", registration_number="", bank_details="", payment_terms=""))
    db_session.commit()
    return user


def source(api, db, user, client, *, kind="formal"):
    worker = _worker(db, "依頼先")
    body = _payload([worker.id], kind=kind)
    body["internal_source"] = {"client_id": client.id, "client_staff_id": None}
    created = api.post("/api/order-requests", json=body, headers=_auth(user.username))
    assert created.status_code == 200, created.text
    result = api.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(user.username))
    assert result.status_code == 200, result.text
    return result.json()


def save(api, user, version, client, amount="10001", **kwargs):
    body = {"client_id": client.id, "billing_month": "202611", "amount": amount, "expected_revision": 0, "reason": ""}
    body.update(kwargs)
    return api.post(f"/api/order-billing/orders/{version['id']}/confirm", headers=_auth(user.username), json=body)


def generate(api, user, client):
    return api.post("/api/order-billing/invoices", headers=_auth(user.username), json={"client_id": client.id, "billing_month": "202611", "billing_date": "2026-11-30"})


def test_latest_formal_confirmed_only_and_zero_is_not_missing(api_client, db_session, admin_user, client, pdf_root):
    first = source(api_client, db_session, admin_user, client)
    source(api_client, db_session, admin_user, client, kind="test")
    cancelled = source(api_client, db_session, admin_user, client)
    response = api_client.post(f"/api/order-requests/versions/{cancelled['id']}/cancel", headers=_auth(admin_user.username), json={"reason": "中止"})
    assert response.status_code == 200, response.text
    hidden = source(api_client, db_session, admin_user, client)
    db_session.get(OrderRequestDocument, hidden["document_id"]).deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    auth = _auth(admin_user.username)
    assert api_client.get("/api/order-billing/summary", headers=auth).json()["missing_count"] == 1
    assert save(api_client, admin_user, first, client, "0").status_code == 200
    assert api_client.get("/api/order-billing/summary", headers=auth).json()["missing_count"] == 0
    revised = _revise_confirm(api_client, admin_user, first["id"])
    rows = api_client.get("/api/order-billing/orders?status=all", headers=auth).json()["items"]
    assert len(rows) == 1 and rows[0]["version_id"] == revised["id"] and rows[0]["amount"] is None
    assert api_client.get("/api/order-billing/summary", headers=auth).json()["missing_count"] == 1
    assert save(api_client, admin_user, first, client).status_code == 409
    assert db_session.query(Invoice).count() == 0  # Existing actual-based invoices are untouched.


@pytest.mark.parametrize("role", ["ops", "accounting", "site_manager", "worker"])
def test_all_new_apis_are_admin_only_even_with_financial_permissions(api_client, db_session, role):
    user = create_user_with_hashed_password(db_session, f"member_{role}", f"{role}@example.com", "pass123", role)
    db_session.add(RoleAccessPolicy(role=role, permissions=["order_read", "order_write", "invoice_read", "invoice_generate", "audit_log_read"]))
    db_session.commit()
    for path in ("summary", "clients", "issuer", "orders", "orders/unknown/history", "invoices", "invoices/unknown", "invoices/unknown/pdf"):
        assert api_client.get(f"/api/order-billing/{path}", headers=_auth(user.username)).status_code == 403
    assert api_client.post("/api/order-billing/invoices", headers=_auth(user.username), json={"client_id": "unknown", "billing_month": "202611", "billing_date": "2026-11-30"}).status_code == 403
    assert api_client.get("/api/order-billing/summary").status_code == 401
    assert api_client.put("/api/order-billing/issuer", headers=_auth(user.username), json={"expected_revision": 1, "name": "変更"}).status_code == 403


def test_amounts_append_history_and_detect_stale_or_invalid_input(api_client, db_session, admin_user, client, pdf_root):
    row = source(api_client, db_session, admin_user, client)
    assert save(api_client, admin_user, row, client, "-1").status_code == 422
    assert save(api_client, admin_user, row, client, "NaN").status_code == 422
    assert save(api_client, admin_user, row, client, "1.001").status_code == 422
    assert save(api_client, admin_user, row, client, billing_month="202613").status_code == 422
    assert save(api_client, admin_user, row, client).status_code == 200
    assert save(api_client, admin_user, row, client).status_code == 409
    assert save(api_client, admin_user, row, client, "20000", expected_revision=1).status_code == 400
    assert save(api_client, admin_user, row, client, "20000", expected_revision=1, reason="クライアントと金額合意").status_code == 200
    history = api_client.get(f"/api/order-billing/orders/{row['id']}/history", headers=_auth(admin_user.username)).json()["items"]
    assert [r["amount"] for r in history] == ["20000.00", "10001.00"]
    assert db_session.query(OrderBillingAmount).count() == 2


def test_monthly_lines_rounding_idempotency_and_frozen_issued_pdf(api_client, db_session, admin_user, client, pdf_root):
    first = source(api_client, db_session, admin_user, client)
    second = source(api_client, db_session, admin_user, client)
    assert save(api_client, admin_user, first, client).status_code == 200
    assert save(api_client, admin_user, second, client, "2.95").status_code == 200
    response = generate(api_client, admin_user, client)
    assert response.status_code == 200, response.text
    invoice = response.json()
    assert invoice["subtotal"] == "10003.95" and invoice["tax_amount"] == "1000.00" and invoice["total_amount"] == "11003.95"
    assert generate(api_client, admin_user, client).json()["id"] == invoice["id"]
    assert db_session.query(OrderBillingInvoice).count() == 1 and db_session.query(OrderBillingInvoiceLine).count() == 2
    assert save(api_client, admin_user, first, client, "20000", expected_revision=1, reason="変更").status_code == 409
    draft_key = db_session.get(OrderBillingInvoice, invoice["id"]).pdf_object_key
    auth = _auth(admin_user.username)
    issued = api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue", headers=auth)
    assert issued.status_code == 200, issued.text
    pdf = api_client.get(f"/api/order-billing/invoices/{invoice['id']}/pdf", headers=auth).content
    assert pdf.startswith(b"%PDF")
    client.name = "後から変えた会社名"
    db_session.commit()
    assert api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue", headers=auth).status_code == 200
    assert api_client.get(f"/api/order-billing/invoices/{invoice['id']}/pdf", headers=auth).content == pdf
    assert generate(api_client, admin_user, client).status_code == 409
    assert api_client.post(f"/api/order-billing/invoices/{invoice['id']}/cancel-draft", headers=auth, json={"reason": "変更"}).status_code == 409
    stored = db_session.get(OrderBillingInvoice, invoice["id"])
    assert DocumentStorage().exists(draft_key) and draft_key != stored.pdf_object_key


def test_cancelled_draft_preserves_lines_pdf_and_regenerates_next_version(api_client, db_session, admin_user, client, pdf_root):
    row = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, row, client)
    first = generate(api_client, admin_user, client).json()
    old_key = db_session.get(OrderBillingInvoice, first["id"]).pdf_object_key
    auth = _auth(admin_user.username)
    cancelled = api_client.post(f"/api/order-billing/invoices/{first['id']}/cancel-draft", headers=auth, json={"reason": "金額を確認し直す"})
    assert cancelled.status_code == 200, cancelled.text
    assert DocumentStorage().exists(old_key)
    assert save(api_client, admin_user, row, client, "50000", expected_revision=1, reason="再合意").status_code == 200
    second = generate(api_client, admin_user, client)
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2 and second.json()["parent_invoice_id"] == first["id"]
    assert second.json()["subtotal"] == "50000.00"
    assert db_session.query(OrderBillingInvoiceLine).count() == 2


def test_order_revised_or_new_amount_after_draft_blocks_issuance(api_client, db_session, admin_user, client, pdf_root):
    first = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, first, client)
    invoice = generate(api_client, admin_user, client).json()
    extra = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, extra, client)
    auth = _auth(admin_user.username)
    response = api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue", headers=auth)
    assert response.status_code == 409 and "追加" in response.json()["detail"]
    _revise_confirm(api_client, admin_user, first["id"])
    response = api_client.post(f"/api/order-billing/invoices/{invoice['id']}/issue", headers=auth)
    assert response.status_code == 409 and "変更・取消" in response.json()["detail"]


def test_billing_audit_values_do_not_leak_to_non_admins(api_client, db_session, admin_user, client, pdf_root):
    row = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, row, client)
    user = create_user_with_hashed_password(db_session, "audit_reader", "audit@example.com", "pass123", "ops")
    db_session.add(RoleAccessPolicy(role="ops", permissions=["audit_log_read"]))
    db_session.commit()
    response = api_client.post("/api/audit/search", headers=_auth(user.username), json={"target_type": "order_billing_amount"})
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_additive_migration_keeps_existing_rows_and_seeds_tax_master():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261023c001_order_billing.py"
    spec = importlib.util.spec_from_file_location("billing_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE order_request_versions (id VARCHAR(26) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO order_request_versions VALUES ('existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert connection.execute(text("SELECT id FROM order_request_versions")).scalar() == "existing"
        assert connection.execute(text("SELECT rate, rounding FROM order_billing_tax_rules")).one() == (0.1, "floor_yen")
        assert connection.execute(text("SELECT name, postal_code FROM order_billing_issuer")).one() == ("株式会社VANZAI", "116-0002")
        assert "order_billing_invoice_lines" in inspect(connection).get_table_names()


def test_client_month_isolation_and_reciprocal_invoice_guard(api_client, db_session, admin_user, client, pdf_root):
    from src.services import invoice_service
    from src.exceptions import ValidationException
    first = source(api_client, db_session, admin_user, client)
    other_month = source(api_client, db_session, admin_user, client)
    second_client = Client(name="別の依頼元")
    db_session.add(second_client)
    db_session.commit()
    other_client = source(api_client, db_session, admin_user, second_client)
    save(api_client, admin_user, first, client, "100")
    save(api_client, admin_user, other_month, client, "200", billing_month="202612")
    save(api_client, admin_user, other_client, second_client, "300")
    draft = generate(api_client, admin_user, client).json()
    assert draft["subtotal"] == "100.00"
    with pytest.raises(ValidationException, match="二重請求"):
        invoice_service.generate_invoice(db_session, client.id, None, "202611", date(2026, 11, 30), admin_user.id)
    legacy = Invoice(client_id=second_client.id, period_key="202611", billing_date=date(2026, 11, 30),
                     subtotal=Decimal("1"), tax_amount=Decimal("0"), total_amount=Decimal("1"))
    db_session.add(legacy)
    db_session.commit()
    blocked = generate(api_client, admin_user, second_client)
    assert blocked.status_code == 409 and "二重請求" in blocked.json()["detail"]
    legacy.document_type = "estimate"
    db_session.commit()
    assert generate(api_client, admin_user, second_client).json()["subtotal"] == "300.00"


def test_missing_stored_pdf_is_not_regenerated(api_client, db_session, admin_user, client, pdf_root):
    row = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, row, client)
    draft = generate(api_client, admin_user, client).json()
    invoice = db_session.get(OrderBillingInvoice, draft["id"])
    invoice.pdf_object_key = "missing.pdf"
    db_session.commit()
    response = api_client.get(f"/api/order-billing/invoices/{draft['id']}/pdf", headers=_auth(admin_user.username))
    assert response.status_code == 404
    assert invoice.pdf_object_key == "missing.pdf"


def test_database_claim_prevents_duplicate_series_even_without_api(api_client, db_session, admin_user, client, pdf_root):
    row = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, row, client)
    invoice = generate(api_client, admin_user, client).json()
    line = db_session.query(OrderBillingInvoiceLine).filter_by(invoice_id=invoice["id"]).one()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(OrderBillingInvoiceLine(invoice_id=line.invoice_id, amount_id=line.amount_id, series_id=line.series_id,
            active_series_id=line.series_id, line_number=2, description="重複", document_number=line.document_number,
            work_date_label=line.work_date_label, amount=line.amount))
        db_session.flush()


def test_migration_postgres_ddl_has_partial_unique_and_series_claim():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261023c001_order_billing.py"
    spec = importlib.util.spec_from_file_location("billing_pg_ddl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        module.upgrade()
    ddl = output.getvalue()
    assert "WHERE status <> 'cancelled'" in ddl
    assert "UNIQUE (active_series_id)" in ddl
    assert "DROP TABLE" not in ddl and "ALTER TABLE" not in ddl


def test_editable_issuer_is_snapshotted_and_conflicts_are_rejected(api_client, db_session, admin_user, client, pdf_root):
    auth = _auth(admin_user.username)
    settings = api_client.get("/api/order-billing/issuer", headers=auth).json()
    assert settings["name"] == "株式会社VANZAI" and settings["postal_code"] == "116-0002"
    row = source(api_client, db_session, admin_user, client)
    save(api_client, admin_user, row, client)
    draft = generate(api_client, admin_user, client).json()
    settings.pop("revision")
    settings.update(name="変更後の発行元", bank_details="検証用銀行\n口座名義：テスト", payment_terms="請求月の翌月末まで")
    response = api_client.put("/api/order-billing/issuer", headers=auth, json={**settings, "expected_revision": 1})
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert api_client.put("/api/order-billing/issuer", headers=auth, json={**settings, "expected_revision": 1}).status_code == 409
    detail = api_client.get(f"/api/order-billing/invoices/{draft['id']}", headers=auth).json()
    assert detail["issuer_snapshot"]["name"] == "株式会社VANZAI"
    assert api_client.post(f"/api/order-billing/invoices/{draft['id']}/cancel-draft", headers=auth, json={"reason": "新しい発行元で再作成"}).status_code == 200
    recreated = generate(api_client, admin_user, client).json()
    assert recreated["issuer_snapshot"]["name"] == "変更後の発行元"
    assert recreated["issuer_snapshot"]["bank_details"] == settings["bank_details"]
