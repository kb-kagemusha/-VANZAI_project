"""LINE申請の審査API。管理画面のログインが必要で、登録用Bearerでは呼ばない。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.enums import Permission
from src.models.master import User
from src.services.audit import AuditService
from src.services.auth import AuthorizationError, check_permission
from src.services.line_registration_review import LineRegistrationReviewService, LineReviewError

router = APIRouter(prefix="/api/line/registration/reviews", tags=["LINE registration review"])


class LineRegistrationReviewDecision(BaseModel):
    comparison_ticket: str


class LineRegistrationReviewReject(BaseModel):
    reason: str


class LineRegistrationReviewChoice(BaseModel):
    decision: Literal["create_new", "existing"]
    worker_id: str | None = None


def _failure(db: Session, *, request_id: str | None, actor: str, category: str) -> None:
    if not request_id:
        return
    try:
        AuditService(db).log(
            "line_registration_review_rejected",
            target_type="registration_request",
            target_id=request_id,
            actor=actor,
            reason=category,
        )
        db.commit()
    except Exception:
        db.rollback()


def _reject(db: Session, exc: LineReviewError, actor: str) -> HTTPException:
    db.rollback()
    if exc.status_code >= 400 and exc.category not in {"reason", "not_line"}:
        _failure(db, request_id=exc.request_id, actor=actor, category=exc.category)
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/{request_id}")
def get_line_registration_review(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        return LineRegistrationReviewService(db).view(request_id, current_user)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="この操作の権限がありません。") from exc
    except LineReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{request_id}/candidates")
def search_line_registration_candidates(
    request_id: str,
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        return {"candidates": LineRegistrationReviewService(db).candidates(request_id, q)}
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="この操作の権限がありません。") from exc
    except LineReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{request_id}/choice")
def choose_line_registration_target(
    request_id: str,
    body: LineRegistrationReviewChoice,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        return LineRegistrationReviewService(db).choose(request_id, current_user, body.decision, body.worker_id)
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="この操作の権限がありません。") from exc
    except LineReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{request_id}/approve")
def approve_line_registration(
    request_id: str,
    body: LineRegistrationReviewDecision,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        result = LineRegistrationReviewService(db).approve(request_id, body.comparison_ticket, current_user)
        db.commit()
        return result
    except LineReviewError as exc:
        raise _reject(db, exc, current_user.username) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="この操作の権限がありません。") from exc
    except OperationalError as exc:
        db.rollback()
        _failure(db, request_id=request_id, actor=current_user.username, category="lock_timeout")
        raise HTTPException(status_code=409, detail="ほかの処理がこの申請を使っています。もう一度開いてください。") from exc
    except IntegrityError as exc:
        db.rollback()
        _failure(db, request_id=request_id, actor=current_user.username, category="link_conflict")
        raise HTTPException(
            status_code=409,
            detail="LINEの紐付けが同時に変わったため、承認できません。最新の内容を読み込んでください。",
        ) from exc
    except Exception as exc:
        db.rollback()
        _failure(db, request_id=request_id, actor=current_user.username, category="database_error")
        raise HTTPException(status_code=500, detail="審査を確定できませんでした。") from exc


@router.post("/{request_id}/reject")
def reject_line_registration(
    request_id: str,
    body: LineRegistrationReviewReject,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        result = LineRegistrationReviewService(db).reject(request_id, current_user, body.reason)
        db.commit()
        return result
    except LineReviewError as exc:
        raise _reject(db, exc, current_user.username) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="この操作の権限がありません。") from exc
    except OperationalError as exc:
        db.rollback()
        _failure(db, request_id=request_id, actor=current_user.username, category="lock_timeout")
        raise HTTPException(status_code=409, detail="ほかの処理がこの申請を使っています。もう一度開いてください。") from exc
