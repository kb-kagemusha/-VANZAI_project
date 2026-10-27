"""当日の起床状況（A1、DEC-064）。テスト用の予定と報告は含めない。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.enums import Permission
from src.models.line_daily import (
    ENTRY_ACTIVE,
    ENTRY_CHANGING,
    WAKE_CONTACT_RESOLVED,
    WAKE_CONTACT_RESULTS,
    WakeContactLog,
    WakeReport,
    WorkerScheduleEntry,
)
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.master import User, Worker
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.auth import has_permission

router = APIRouter(prefix="/api/line-daily", tags=["LINE daily"])

from src.services.wake_status import build_wake_status, wake_next_action


def test_settings_admin(user=Depends(get_current_active_user)):
    if getattr(user.role, "value", user.role) != "admin":
        raise HTTPException(403, "テスト通知の設定は全体管理者だけが変更できます。")
    return user


class WakeTestSettingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    enabled_until: datetime | None = None
    revision: int = Field(ge=0)


@router.get("/test-notification-settings")
def read_test_notification_settings(response: Response, user: User = Depends(test_settings_admin), db: Session = Depends(get_db)):
    from src.services.wake_test_notifications import view
    response.headers["Cache-Control"] = "no-store"
    return view(db)


@router.put("/test-notification-settings")
def save_test_notification_settings(body: WakeTestSettingBody, response: Response, user: User = Depends(test_settings_admin), db: Session = Depends(get_db)):
    from src.services.wake_test_notifications import update
    response.headers["Cache-Control"] = "no-store"
    result = update(db, user, **body.model_dump())
    db.commit()
    return result


@router.get("/wake-status")
def wake_status(
    day: date | None = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not has_permission(current_user, Permission.WAKE_STATUS_READ):
        raise HTTPException(status_code=403, detail="起床状況を見る権限がありません")
    return build_wake_status(db, day)


class WakeContactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    worker_id: str = Field(min_length=1, max_length=26)
    result: str = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=500)
    is_test: bool = False


@router.post("/wake-contacts")
def record_wake_contact(
    body: WakeContactBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """起床の目視確認で連絡した結果を記録する（W-2）。追記のみで、取り消しは新しい記録で行う。"""
    if not has_permission(current_user, Permission.WAKE_STATUS_READ):
        raise HTTPException(status_code=403, detail="起床状況を見る権限がありません")
    if body.result not in WAKE_CONTACT_RESULTS or body.result == "claimed":
        raise HTTPException(status_code=400, detail="連絡の結果を選び直してください")
    if db.get(Worker, body.worker_id) is None:
        raise HTTPException(status_code=404, detail="稼働者が見つかりません")
    log = WakeContactLog(
        worker_id=body.worker_id,
        contact_date=body.day,
        is_test=body.is_test,
        result=body.result,
        note=body.note.strip() or None,
        actor_user_id=current_user.id,
        actor_name=getattr(current_user, "display_name", None) or current_user.username,
        created_at=ws.now_utc(),
    )
    db.add(log)
    db.flush()
    AuditService(db).log(
        "wake_contact_recorded",
        target_type="wake_contact_log",
        target_id=log.id,
        actor=current_user.username,
        actor_role=getattr(current_user.role, "value", current_user.role),
        after_value={"worker_id": log.worker_id, "date": log.contact_date.isoformat(), "result": log.result, "note": log.note},
    )
    db.commit()
    return {
        "id": log.id,
        "result": log.result,
        "result_label": WAKE_CONTACT_RESULTS[log.result],
        "note": log.note,
        "actor_name": log.actor_name,
        "created_at": log.created_at,
    }
