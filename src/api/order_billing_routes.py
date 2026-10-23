"""Strict admin-only order receivables and monthly invoices."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.master import Client, User
from src.models.order_billing import OrderBillingAmount, OrderBillingInvoice
from src.services.document_storage import DocumentStorage
from src.services.order_billing import OrderBillingService, validate_month
from src.services.order_request_service import OrderRequestError


def admin(user: User = Depends(get_current_active_user)):
    if user.role != "admin":
        raise HTTPException(403, "依頼書の請求金額と月次請求書は全体管理者だけが閲覧・操作できます")
    return user


router = APIRouter(prefix="/api/order-billing", tags=["Order Billing"], dependencies=[Depends(admin)])


class AmountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = Field(default=None, min_length=1, max_length=26)
    billing_month: str = Field(pattern=r"^[1-9]\d{3}(0[1-9]|1[0-2])$")
    amount: Decimal = Field(ge=0, max_digits=15, decimal_places=2, allow_inf_nan=False)
    incentive_amount: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2, allow_inf_nan=False)
    expected_revision: int = Field(ge=0)
    reason: str = Field(default="", max_length=2000)


class InvoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=1, max_length=26)
    billing_month: str = Field(pattern=r"^[1-9]\d{3}(0[1-9]|1[0-2])$")
    billing_date: date


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class IssuerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=1000)
    registration_number: str = Field(default="", max_length=50)
    bank_details: str = Field(default="", max_length=2000)
    payment_terms: str = Field(default="", max_length=1000)


def call(db, action):
    try:
        result = action()
        db.commit()
        return result
    except OrderRequestError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, exc.detail) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "別の処理と重なりました。一覧を更新して確認してください") from exc


def invoice_out(row):
    return {"id": row.id, "document_number": row.document_number, "client_id": row.client_id,
        "client_name": row.client_snapshot["name"], "billing_month": row.billing_month, "billing_date": row.billing_date,
        "status": row.status, "version": row.version, "parent_invoice_id": row.parent_invoice_id,
        "subtotal": str(row.subtotal), "tax_amount": str(row.tax_amount), "total_amount": str(row.total_amount),
        "tax_rate": str(row.tax_rate), "tax_rounding": row.tax_rounding, "has_pdf": bool(row.pdf_object_key),
        "issued_at": row.issued_at, "cancel_reason": row.cancel_reason, "issuer_snapshot": row.issuer_snapshot}


@router.get("/issuer")
def issuer(db: Session = Depends(get_db)):
    try:
        return OrderBillingService(db).issuer_snapshot()
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


@router.put("/issuer")
def update_issuer(body: IssuerBody, user: User = Depends(admin), db: Session = Depends(get_db)):
    service = OrderBillingService(db)
    call(db, lambda: service.update_issuer(actor=user, **body.model_dump()))
    return service.issuer_snapshot()


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    rows = OrderBillingService(db).rows()
    return {"missing_count": sum(not r["billing_ready"] for r in rows), "total": len(rows)}


@router.get("/clients")
def clients(db: Session = Depends(get_db)):
    return {"items": [{"id": c.id, "name": c.name} for c in db.query(Client).filter(Client.deleted_at.is_(None)).order_by(Client.name, Client.id).all()]}


@router.get("/orders")
def orders(status: str = Query(default="missing", pattern="^(missing|confirmed|invoice_created|all)$"),
           q: str = Query(default="", max_length=100), limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
           db: Session = Depends(get_db)):
    rows = OrderBillingService(db).rows()
    if status == "missing":
        rows = [r for r in rows if not r["billing_ready"]]
    elif status != "all":
        rows = [r for r in rows if r["status"] == status]
    if q.strip():
        rows = [r for r in rows if q.strip().casefold() in f"{r['document_number']} {r['project_name']} {r['client_name']}".casefold()]
    return {"items": rows[offset:offset + limit], "total": len(rows), "limit": limit, "offset": offset}


@router.post("/orders/{version_id}/confirm")
def confirm(version_id: str, body: AmountBody, user: User = Depends(admin), db: Session = Depends(get_db)):
    row = call(db, lambda: OrderBillingService(db).save_amount(version_id, actor=user, **body.model_dump()))
    return {"id": row.id, "revision": row.revision}


@router.get("/orders/{version_id}/history")
def history(version_id: str, db: Session = Depends(get_db)):
    rows = db.query(OrderBillingAmount).filter_by(version_id=version_id).order_by(OrderBillingAmount.revision.desc()).all()
    return {"items": [{"revision": r.revision, "client_id": r.client_id, "client_name": r.snapshot["client_name"],
                      "amount": str(r.amount), "incentive_amount": str(r.incentive_amount) if r.incentive_amount is not None else None,
                      "incentive_enabled": r.snapshot.get("incentive_enabled", False), "incentive_note": r.snapshot.get("incentive_note", ""),
                      "billing_month": r.billing_month, "reason": r.reason, "created_at": r.created_at} for r in rows]}


@router.get("/invoices")
def invoices(billing_month: str = "", limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    query = db.query(OrderBillingInvoice)
    if billing_month:
        try:
            validate_month(billing_month)
        except OrderRequestError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc
        query = query.filter_by(billing_month=billing_month)
    total = query.count()
    rows = query.order_by(OrderBillingInvoice.created_at.desc(), OrderBillingInvoice.id).offset(offset).limit(limit).all()
    return {"items": [invoice_out(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/invoices")
def generate_invoice(body: InvoiceBody, user: User = Depends(admin), db: Session = Depends(get_db)):
    return invoice_out(call(db, lambda: OrderBillingService(db).generate(actor=user, **body.model_dump())))


@router.get("/invoices/{invoice_id}")
def detail(invoice_id: str, db: Session = Depends(get_db)):
    service = OrderBillingService(db)
    try:
        row = service.get_invoice(invoice_id)
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return {**invoice_out(row), "lines": [{"id": l.id, "description": l.description, "document_number": l.document_number,
        "work_date_label": l.work_date_label, "amount": str(l.amount), "incentive_amount": str(l.incentive_amount) if l.incentive_amount is not None else None,
        "incentive_note": l.incentive_note} for l in service.lines(row)]}


@router.post("/invoices/{invoice_id}/issue")
def issue(invoice_id: str, user: User = Depends(admin), db: Session = Depends(get_db)):
    return invoice_out(call(db, lambda: OrderBillingService(db).issue(invoice_id, actor=user)))


@router.post("/invoices/{invoice_id}/cancel-draft")
def cancel(invoice_id: str, body: ReasonBody, user: User = Depends(admin), db: Session = Depends(get_db)):
    return invoice_out(call(db, lambda: OrderBillingService(db).cancel_draft(invoice_id, reason=body.reason, actor=user)))


@router.get("/invoices/{invoice_id}/pdf")
def pdf(invoice_id: str, db: Session = Depends(get_db)):
    try:
        row = OrderBillingService(db).get_invoice(invoice_id)
        if not row.pdf_object_key or not DocumentStorage().exists(row.pdf_object_key):
            raise OrderRequestError(404, "保管済みPDFがありません。上書きせず管理者へ確認してください")
        content = DocumentStorage().read_bytes(row.pdf_object_key)
    except OrderRequestError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{row.document_number}-v{row.version}.pdf"', "Cache-Control": "no-store"})
