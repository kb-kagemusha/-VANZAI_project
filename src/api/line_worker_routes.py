"""稼働者向けLIFF画面のAPI（統合計画 ①）。管理画面のログインとは別のBearer（稼働者セッション）だけを受け付ける。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models.line_daily import FEATURE_KEYS
from src.services.line_daily import enabled_actions
from src.services.line_worker import LineWorkerError, LineWorkerService, worker_liff_id
from src.services.line_worker_portal import LineWorkerPortal, PortalError

router = APIRouter(prefix="/api/line/worker", tags=["LINE worker"])


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str


class PickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dates: list[str]


class ReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    reason: str = ""


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="本人確認が必要です。LINEから開き直してください。")
    return header.removeprefix("Bearer ").strip()


def _error(exc: LineWorkerError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"message": exc.message, "code": exc.code})


@router.get("/entry")
def worker_entry(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    features = sorted(set(enabled_actions(db)) & set(FEATURE_KEYS))
    return {"liff_id": worker_liff_id() or None, "features": features}


@router.post("/sessions")
def create_worker_session(body: SessionRequest, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        result = LineWorkerService(db).issue_session(body.id_token)
        db.commit()
    except LineWorkerError as exc:
        db.rollback()
        raise _error(exc) from None
    return result


@router.get("/deliveries/{delivery_id}/pick")
def pick_view(delivery_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    service = LineWorkerService(db)
    try:
        _row, worker = service.authenticate(_bearer(request))
        return service.pick_view(worker, delivery_id)
    except LineWorkerError as exc:
        raise _error(exc) from None


@router.post("/deliveries/{delivery_id}/pick")
def pick_accept(
    delivery_id: str,
    body: PickRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    service = LineWorkerService(db)
    try:
        row, worker = service.authenticate(_bearer(request))
        result = service.accept_dates(row, worker, delivery_id, body.dates, idempotency_key)
        db.commit()
        service.send_pending_notice()
    except LineWorkerError as exc:
        db.rollback()
        raise _error(exc) from None
    except Exception:
        db.rollback()
        raise
    return result


# ---- Web確認画面からの返事（統合計画 ③-C、D-09）。機能 web_reply ------------------------------

@router.get("/deliveries/{delivery_id}/reply")
def reply_view(delivery_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    service = LineWorkerService(db)
    try:
        _row, worker = service.authenticate(_bearer(request))
        return service.reply_view(worker, delivery_id)
    except LineWorkerError as exc:
        raise _error(exc) from None


@router.post("/deliveries/{delivery_id}/reply")
def reply_submit(
    delivery_id: str,
    body: ReplyRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    service = LineWorkerService(db)
    try:
        row, worker = service.authenticate(_bearer(request))
        result = service.reply(row, worker, delivery_id, body.action, body.reason, idempotency_key)
        db.commit()
        # 通知の失敗で返事の確定は戻さない（送信は commit の後）
        service.send_pending_notice()
    except LineWorkerError as exc:
        db.rollback()
        raise _error(exc) from None
    except Exception:
        db.rollback()
        raise
    return result


# ---- Web確認画面（統合計画 ②、DEC-084）。閲覧専用 ---------------------------------------------

def _portal_error(exc: PortalError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"message": exc.message, "code": exc.code})


@router.get("/home")
def worker_home(request: Request, response: Response, month: str | None = Query(default=None, max_length=7), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        _row, worker = LineWorkerService(db).authenticate(_bearer(request))
        return LineWorkerPortal(db).home(worker, month)
    except LineWorkerError as exc:
        raise _error(exc) from None
    except PortalError as exc:
        raise _portal_error(exc) from None


@router.get("/orders")
def worker_orders(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        _row, worker = LineWorkerService(db).authenticate(_bearer(request))
        return LineWorkerPortal(db).orders(worker)
    except LineWorkerError as exc:
        raise _error(exc) from None
    except PortalError as exc:
        raise _portal_error(exc) from None


@router.post("/deliveries/{delivery_id}/pdf-link")
def worker_pdf_link(delivery_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        _row, worker = LineWorkerService(db).authenticate(_bearer(request))
        result = LineWorkerPortal(db).pdf_link(worker, delivery_id)
        db.commit()
        return result
    except LineWorkerError as exc:
        db.rollback()
        raise _error(exc) from None
    except PortalError as exc:
        db.rollback()
        raise _portal_error(exc) from None
