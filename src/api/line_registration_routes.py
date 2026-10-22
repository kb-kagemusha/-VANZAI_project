"""公式LINEの稼働者登録API。管理画面のログインとは別のBearerだけを受け付ける。"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.services import line_id_token as _token
from src.domain.line_registration_entry import registration_entry_ready, registration_liff_id, registration_login_channel_id
from src.domain.line_registration_input import LineRegistrationInputError
from src.services.audit import AuditService
from src.services.line_registration_receipt import dispatch_registration_receipt
from src.services.line_registration import (
    CLOSED_MESSAGE,
    LineRegistrationAuthError,
    LineRegistrationClosed,
    LineRegistrationRejected,
    LineRegistrationService,
)

router = APIRouter(prefix="/api/line/registration", tags=["LINE registration"])
VERIFY_URL = _token.VERIFY_URL
LINE_ID_TOKEN_EXPIRED = _token.LINE_ID_TOKEN_EXPIRED
line_verify_error_message = _token.line_verify_error_message


def assert_line_id_token_usable(payload: dict, channel_id: str, now: datetime) -> str:
    try:
        return _token.assert_line_id_token_usable(payload, channel_id, now)
    except _token.LineIdTokenError as exc:
        raise LineRegistrationAuthError(exc.message) from None


class LineRegistrationSessionRequest(BaseModel):
    id_token: str


class LineRegistrationSubmitRequest(BaseModel):
    last_name: str | None = None
    first_name: str | None = None
    last_name_furigana: str | None = None
    first_name_furigana: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: str | None = None
    postal_code: str | None = None
    prefecture: str | None = None
    address1: str | None = None
    address2: str | None = None
    nearest_station: str | None = None
    station_walk_minutes: str | None = None
    additional_stations: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relationship: str | None = None


def verify_line_id_token(id_token: str) -> str:
    """登録の入口用。登録の受付が閉じていれば先に断る。検証そのものは共通（src/services/line_id_token.py）。"""
    if not registration_entry_ready():
        raise LineRegistrationClosed()
    try:
        return _token.verify_id_token(id_token, registration_login_channel_id())
    except _token.LineIdTokenError as exc:
        raise LineRegistrationAuthError(exc.message) from None


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="本人確認が必要です。")
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="本人確認が必要です。")
    return token


def _failure_audit(db: Session, exc: LineRegistrationRejected) -> None:
    try:
        AuditService(db).log(
            "line_registration_submit_rejected",
            target_type="registration_request",
            target_id=exc.request_id,
            actor="line-registration",
            reason=exc.category,
        )
        db.commit()
    except Exception:
        db.rollback()


@router.get("/entry")
def registration_entry():
    ready = registration_entry_ready()
    return {"enabled": ready, "liff_id": registration_liff_id() if ready else None}


@router.post("/sessions")
def create_registration_session(body: LineRegistrationSessionRequest, db: Session = Depends(get_db)):
    try:
        subject = verify_line_id_token(body.id_token)
        token, expires_at, linked, tag = LineRegistrationService(db).issue_session(subject)
        db.commit()
    except LineRegistrationClosed as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=exc.message) from exc
    except LineRegistrationAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except Exception:
        db.rollback()
        raise
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "linked": linked,
        "subject_tag": tag,
    }


@router.get("/form")
def registration_form(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        response.headers["Cache-Control"] = "no-store"
        state = LineRegistrationService(db).form_state(_bearer(request))
    except LineRegistrationClosed as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    except LineRegistrationAuthError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except LineRegistrationRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return state


@router.post("/submissions")
def submit_registration(body: LineRegistrationSubmitRequest, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    sent = set(body.model_fields_set)
    try:
        result = LineRegistrationService(db).submit(
            _bearer(request),
            request.headers.get("idempotency-key", ""),
            body.model_dump(),
            sent,
            form_ticket=request.headers.get("x-registration-form-ticket", ""),
        )
        db.commit()
    except LineRegistrationClosed as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=exc.message) from exc
    except LineRegistrationAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except LineRegistrationInputError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except LineRegistrationRejected as exc:
        db.rollback()
        _failure_audit(db, exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="申請を確定できませんでした。") from None
    if result.saved:
        background_tasks.add_task(dispatch_registration_receipt, result.request_id, sessionmaker(bind=db.get_bind()))
    return {
        "request_id": result.request_id,
        "status": result.status,
        "saved": result.saved,
        "message": result.message,
    }


def registration_closed_message() -> str:
    return CLOSED_MESSAGE
