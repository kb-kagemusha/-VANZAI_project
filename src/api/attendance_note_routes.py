"""報告の記録と支払確認用の注意事項。金額・予定・PDFを変更しない（DEC-090）。"""
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.attendance_note import AttendanceNote
from src.models.enums import Permission
from src.models.line_daily import WorkerScheduleEntry
from src.models.master import User, Worker
from src.models.transaction import Payout
from src.services.audit import AuditService
from src.services.auth import has_permission

router = APIRouter(prefix="/api/attendance-notes", tags=["Attendance notes"])


def _require(user, permission):
    if user.role == "worker" or not has_permission(user, permission):
        raise HTTPException(403, "遅刻・キャンセル記録を操作する権限がありません")


def _bounds(period_key: str):
    try:
        first = datetime.strptime(period_key, "%Y%m").date().replace(day=1)
        last = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        return first, last
    except ValueError:
        raise HTTPException(422, "対象月はYYYYMM形式で指定してください")


def _serialize(row):
    if row.kind == "late":
        hours, minutes = divmod(row.late_minutes, 60)
        duration = (f"{hours}時間" if hours else "") + (f"{minutes}分" if minutes else "")
        summary = f"{duration}遅刻"
        payment_note = "遅刻時の支払額を確認してください"
    else:
        summary = "本人都合でキャンセル" if row.cause == "personal" else "台風・天候による中止" if row.cause == "weather" else "キャンセル・中止"
        payment_note = "本人都合：当日の支払対象外" if row.cause == "personal" else "受諾済みの報酬は満額保証" if row.cause == "weather" else "中止理由と支払の扱いを確認してください"
    return {key: getattr(row, key) for key in (
        "id", "schedule_entry_id", "series_id", "worker_id", "work_date", "project_name", "worker_name", "is_test",
        "kind", "cause", "late_minutes", "reason", "reported_by", "actor_name", "created_at", "voided_at", "void_reason"
    )} | {"summary": summary, "payment_note": payment_note}


@router.get("/events")
def events(period_key: str = Query(pattern=r"^\d{6}$"), is_test: bool = False,
           current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _require(current_user, Permission.ATTENDANCE_NOTE_READ)
    first, last = _bounds(period_key)
    rows = (db.query(WorkerScheduleEntry.series_id, func.max(WorkerScheduleEntry.project_name).label("project_name"))
            .filter(WorkerScheduleEntry.work_date >= first, WorkerScheduleEntry.work_date < last, WorkerScheduleEntry.is_test == is_test)
            .group_by(WorkerScheduleEntry.series_id).order_by("project_name", WorkerScheduleEntry.series_id).all())
    return {"items": [{"series_id": row.series_id, "project_name": row.project_name} for row in rows]}


@router.get("/schedules")
def schedules(series_id: str, day: date, is_test: bool = False,
              current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _require(current_user, Permission.ATTENDANCE_NOTE_READ)
    rows = (db.query(WorkerScheduleEntry, Worker.name).join(Worker, Worker.id == WorkerScheduleEntry.worker_id)
            .filter(WorkerScheduleEntry.series_id == series_id, WorkerScheduleEntry.work_date == day,
                    WorkerScheduleEntry.is_test == is_test)
            .order_by(Worker.name, WorkerScheduleEntry.created_at.desc(), WorkerScheduleEntry.id).all())
    # 改訂前の予定も残し、既に取り消した日の報告も記録できる。同じ本人・勤務グループの旧版は候補を重複させない。
    chosen = {}
    for entry, name in rows:
        key = (entry.worker_id, entry.work_group_id)
        previous = chosen.get(key)
        if previous is None or (previous[0].status not in ("active", "changing") and entry.status in ("active", "changing")):
            chosen[key] = (entry, name)
    return {"items": [{"id": e.id, "worker_id": e.worker_id, "worker_name": name,
                        "start_time": e.start_time, "end_time": e.end_time, "status": e.status}
                       for e, name in chosen.values()]}


@router.get("")
def list_notes(period_key: str = Query(pattern=r"^\d{6}$"), worker_id: str | None = None,
               is_test: bool = False, include_voided: bool = False, series_id: str | None = None,
               limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
               current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # 支払閲覧者も本人・対象月の注意事項を読める。登録候補の閲覧権限とは分離する。
    if not has_permission(current_user, Permission.ATTENDANCE_NOTE_READ):
        _require(current_user, Permission.PAYOUT_READ)
    else:
        _require(current_user, Permission.ATTENDANCE_NOTE_READ)
    first, last = _bounds(period_key)
    query = db.query(AttendanceNote).filter(AttendanceNote.work_date >= first, AttendanceNote.work_date < last,
                                           AttendanceNote.is_test == is_test)
    if worker_id:
        query = query.filter(AttendanceNote.worker_id == worker_id)
    if series_id:
        query = query.filter(AttendanceNote.series_id == series_id)
    if not include_voided:
        query = query.filter(AttendanceNote.voided_at.is_(None))
    total = query.count()
    rows = query.order_by(AttendanceNote.work_date, AttendanceNote.worker_name, AttendanceNote.created_at, AttendanceNote.id).offset(offset).limit(limit).all()
    return {"items": [_serialize(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/payment-summary")
def payment_summary(period_key: str = Query(pattern=r"^\d{6}$"),
                    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _require(current_user, Permission.PAYOUT_READ)
    first, last = _bounds(period_key)
    counts = dict(db.query(AttendanceNote.worker_id, func.count(AttendanceNote.id))
                  .filter(AttendanceNote.work_date >= first, AttendanceNote.work_date < last,
                          AttendanceNote.is_test.is_(False), AttendanceNote.voided_at.is_(None))
                  .group_by(AttendanceNote.worker_id).all())
    payouts = db.query(Payout).filter(Payout.period_key == period_key, Payout.deleted_at.is_(None)).all()
    result = {}
    for payout in payouts:
        worker_id = payout.worker_id or (payout.recipient_id if payout.recipient_type == "worker" else None)
        if worker_id and counts.get(worker_id):
            result[payout.id] = {"worker_id": worker_id, "count": counts[worker_id]}
    return {"total": sum(counts.values()), "payouts": result}


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule_entry_id: str = Field(min_length=1, max_length=26)
    kind: Literal["late", "cancel"]
    cause: Literal["personal", "weather", "other"]
    late_minutes: int | None = Field(default=None, ge=1, le=10080, strict=True)
    reason: str = Field(min_length=1, max_length=1000)
    reported_by: str = Field(min_length=1, max_length=200)

    @field_validator("reason", "reported_by")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("空白だけでは登録できません")
        return value.strip()


@router.post("", status_code=201)
def create_note(body: NoteBody, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _require(current_user, Permission.ATTENDANCE_NOTE_WRITE)
    if (body.kind == "late") != (body.late_minutes is not None):
        raise HTTPException(422, "遅刻の場合だけ遅刻時間（分）を入力してください")
    entry = db.get(WorkerScheduleEntry, body.schedule_entry_id)
    if entry is None:
        raise HTTPException(404, "受諾済みの稼働予定が見つかりません")
    row = AttendanceNote(
        schedule_entry_id=entry.id, worker_id=entry.worker_id, series_id=entry.series_id, work_date=entry.work_date,
        project_name=entry.project_name, worker_name=db.get(Worker, entry.worker_id).name, is_test=entry.is_test,
        kind=body.kind, cause=body.cause, late_minutes=body.late_minutes, reason=body.reason,
        reported_by=body.reported_by, actor_user_id=current_user.id,
        actor_name=current_user.display_name or current_user.username,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "この予定の同じ種類の記録は登録済みです。訂正は元の記録を取り消してから登録してください")
    AuditService(db).log("attendance_note_recorded", target_type="attendance_note", target_id=row.id,
                         actor=current_user.username, actor_role=current_user.role, reason=body.reason,
                         after_value={"schedule_entry_id": entry.id, "worker_id": entry.worker_id, "series_id": entry.series_id,
                                      "work_date": entry.work_date.isoformat(), "kind": row.kind, "cause": row.cause,
                                      "late_minutes": row.late_minutes, "reported_by": row.reported_by, "is_test": row.is_test})
    db.commit()
    return _serialize(row)


class VoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/{note_id}/void")
def void_note(note_id: str, body: VoidBody, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    _require(current_user, Permission.ATTENDANCE_NOTE_WRITE)
    if not body.reason.strip():
        raise HTTPException(422, "取消理由を入力してください")
    row = db.query(AttendanceNote).filter(AttendanceNote.id == note_id).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "記録が見つかりません")
    if row.voided_at is not None:
        raise HTTPException(409, "既に取り消されています")
    row.voided_at = datetime.now(timezone.utc)
    row.voided_by_user_id = current_user.id
    row.void_reason = body.reason.strip()
    AuditService(db).log("attendance_note_voided", target_type="attendance_note", target_id=row.id,
                         actor=current_user.username, actor_role=current_user.role, reason=row.void_reason,
                         before_value={"active": True}, after_value={"active": False})
    db.commit()
    return _serialize(row)
