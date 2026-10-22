"""稼働者向けLIFF画面のAPI（統合計画 ①）。管理画面のログインとは別のBearer（稼働者セッション）だけを受け付ける。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models.line_daily import FEATURE_KEYS
from src.services.line_daily import enabled_actions
from src.services.line_worker import LineWorkerError, LineWorkerService, worker_liff_id

router = APIRouter(prefix="/api/line/worker", tags=["LINE worker"])


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str


class PickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dates: list[str]


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
    except LineWorkerError as exc:
        db.rollback()
        raise _error(exc) from None
    except Exception:
        db.rollback()
        raise
    return result
