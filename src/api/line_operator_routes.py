"""LINE-only bearer purpose; never accepts an admin/worker JWT as operator identity."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.services.line_operator import LineOperatorService, OperatorError
from src.services import worker_schedule as ws
from src.services.audit import AuditService


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/line/operator", tags=["LINE operator"], dependencies=[Depends(no_store)])


class ClaimBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    worker_id: str = Field(min_length=1, max_length=26)
    takeover: bool = False


class ContactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    worker_id: str = Field(min_length=1, max_length=26)
    result: str = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=500)


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=1, max_length=10000)


def read_log(db, staff, user, view, allowed=True):
    AuditService(db).log("operator_portal_read" if allowed else "operator_portal_read_denied", target_type="vanzai_staff", target_id=staff.id, actor=user.id, actor_role=user.role, after_value={"view": view})
    db.commit()


def access(request: Request, db: Session = Depends(get_db)):
    value = request.headers.get("authorization", "")
    try:
        staff, user = LineOperatorService(db).authenticate(value[7:] if value.startswith("Bearer ") else "")
        return db, staff, user
    except OperatorError as exc:
        raise HTTPException(exc.status, exc.message) from None


@router.post("/session")
def session(body: SessionBody, db: Session = Depends(get_db)):
    try:
        result = LineOperatorService(db).issue(body.id_token)
        db.commit()
        return result
    except OperatorError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.message) from None


@router.get("/me")
def me(context=Depends(access)):
    db, staff, user = context
    result = LineOperatorService(db).me(staff, user)
    read_log(db, staff, user, "profile")
    return result


@router.get("/wake-status")
def wake(day: date | None = Query(None, alias="date"), context=Depends(access)):
    db, staff, user = context
    try:
        result = LineOperatorService(db).wake(user, day or ws.today_jst())
    except OperatorError as exc:
        read_log(db, staff, user, "wake", False)
        raise HTTPException(exc.status, exc.message) from None
    read_log(db, staff, user, "wake")
    return result


@router.get("/calendar")
def calendar(start: date, end: date, kind: str = Query("orders", pattern="^(orders|availability)$"), context=Depends(access)):
    db, staff, user = context
    try:
        result = LineOperatorService(db).calendar(user, start, end, kind)
    except OperatorError as exc:
        read_log(db, staff, user, "calendar:" + kind, False)
        raise HTTPException(exc.status, exc.message) from None
    read_log(db, staff, user, "calendar:" + kind)
    return result


def _write(db, action):
    try:
        result = action()
        db.commit()
        return result
    except OperatorError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.message) from None


@router.post("/wake-contacts/claim")
def claim(body: ClaimBody, context=Depends(access)):
    """「私が連絡します」。引き受けた人にだけ電話番号を返す（0.53.8、DEC-125）。"""
    db, staff, user = context
    return _write(db, lambda: LineOperatorService(db).claim(staff, user, body.day, body.worker_id, body.takeover))


@router.post("/wake-contacts")
def record_contact(body: ContactBody, context=Depends(access)):
    db, staff, user = context
    return _write(db, lambda: LineOperatorService(db).record(staff, user, body.day, body.worker_id, body.result, body.note))


@router.get("/orders")
def orders(start: date, end: date, context=Depends(access)):
    db, staff, user = context
    try:
        result = LineOperatorService(db).orders(user, start, end)
    except OperatorError as exc:
        read_log(db, staff, user, "orders", False)
        raise HTTPException(exc.status, exc.message) from None
    read_log(db, staff, user, "orders")
    return result


@router.post("/orders/{version_id}/pdf-link")
def order_pdf_link(version_id: str, context=Depends(access)):
    db, staff, user = context
    return _write(db, lambda: LineOperatorService(db).pdf_link(staff, user, version_id))


@router.get("/order-files/{token}")
def order_file(token: str, db: Session = Depends(get_db)):
    """短命リンク（10分）。LINE内のブラウザでPDFを開けるように、認証ヘッダーではなくリンクの鍵で確かめる。"""
    from src.services.order_request_pdf import attachment_content_disposition
    try:
        content, filename = LineOperatorService(db).read_file(token)
        db.commit()
    except OperatorError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.message) from None
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": attachment_content_disposition(filename), "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
