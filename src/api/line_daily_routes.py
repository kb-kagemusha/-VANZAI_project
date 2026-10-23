"""当日の起床状況（A1、DEC-064）。テスト用の予定と報告は含めない。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
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

# 起床の目視確認の時刻（手順書 docs/runbook/WAKE_VISUAL_CHECK_RUNBOOK.md §3。最初の開始の何分前か）
WAKE_STEP_LINE_MINUTES = 120
WAKE_STEP_CALL_MINUTES = 90
WAKE_STEP_SITE_MINUTES = 60


def wake_next_action(*, target: date, first_start, reported: bool, latest_result: str | None, now: datetime) -> dict:
    """今すること（W-3）。now は日本時間の時刻（tz なし）。

    step：reported（報告あり）/ resolved（電話で起床を確認・欠勤）/ wait（まだ時刻前）/
    line（LINEで連絡）/ call（電話）/ site（現場へ連絡）/ started（開始時刻を過ぎた）/ none（時刻なし・過去の日）
    priority は小さいほど先に対応する。
    """
    if reported:
        return {"step": "reported", "label": "", "priority": 90, "next_at": None}
    if latest_result in WAKE_CONTACT_RESOLVED:
        return {"step": "resolved", "label": WAKE_CONTACT_RESULTS[latest_result], "priority": 80, "next_at": None}
    if first_start is None:
        return {"step": "none", "label": "開始時刻がありません。依頼書を確認してください", "priority": 70, "next_at": None}
    start = datetime.combine(target, first_start)
    line_at = start - timedelta(minutes=WAKE_STEP_LINE_MINUTES)
    call_at = start - timedelta(minutes=WAKE_STEP_CALL_MINUTES)
    site_at = start - timedelta(minutes=WAKE_STEP_SITE_MINUTES)
    if now >= start:
        return {"step": "started", "label": "開始時刻を過ぎています。現場へ確認してください", "priority": 0, "next_at": None}
    if now >= site_at:
        if latest_result == "site_notified":
            return {"step": "site", "label": "現場へ連絡済み。返事を待つ", "priority": 5, "next_at": None}
        return {"step": "site", "label": "現場へ連絡する（代わりの人の相談）", "priority": 1, "next_at": None}
    if now >= call_at:
        if latest_result == "no_answer":
            return {"step": "call", "label": f"もう一度電話する（{site_at:%H:%M} から現場へ連絡）", "priority": 2, "next_at": site_at.strftime("%H:%M")}
        return {"step": "call", "label": "電話する", "priority": 2, "next_at": site_at.strftime("%H:%M")}
    if now >= line_at:
        if latest_result in ("line_sent", "no_answer"):
            return {"step": "line", "label": f"返事を待つ（{call_at:%H:%M} から電話）", "priority": 6, "next_at": call_at.strftime("%H:%M")}
        return {"step": "line", "label": "LINEで連絡する", "priority": 3, "next_at": call_at.strftime("%H:%M")}
    return {"step": "wait", "label": f"{line_at:%H:%M} からLINEで連絡", "priority": 50, "next_at": line_at.strftime("%H:%M")}


def _hm(value) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _span(entry: WorkerScheduleEntry) -> tuple[datetime, datetime] | None:
    if entry.start_time is None or entry.end_time is None:
        return None
    start = datetime.combine(entry.work_date, entry.start_time)
    end = datetime.combine(entry.work_date + timedelta(days=1 if entry.end_next_day else 0), entry.end_time)
    return start, end


def _overlaps(entries: list[WorkerScheduleEntry]) -> bool:
    spans = sorted(s for s in (_span(e) for e in entries) if s is not None)
    return any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1))


@router.get("/wake-status")
def wake_status(
    day: date | None = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not has_permission(current_user, Permission.WAKE_STATUS_READ):
        raise HTTPException(status_code=403, detail="起床状況を見る権限がありません")
    target = day or ws.today_jst()
    entries = (
        db.query(WorkerScheduleEntry)
        .filter(
            WorkerScheduleEntry.work_date == target,
            WorkerScheduleEntry.is_test.is_(False),
            or_(WorkerScheduleEntry.status == ENTRY_ACTIVE, WorkerScheduleEntry.status == ENTRY_CHANGING),
        )
        .order_by(WorkerScheduleEntry.start_time, WorkerScheduleEntry.id)
        .all()
    )
    by_worker: dict[str, list[WorkerScheduleEntry]] = {}
    for entry in entries:
        by_worker.setdefault(entry.worker_id, []).append(entry)
    worker_ids = set(by_worker)
    reports = {
        r.worker_id: r
        for r in db.query(WakeReport).filter(WakeReport.report_date == target, WakeReport.is_test.is_(False)).all()
    }
    workers = {w.id: w for w in db.query(Worker).filter(Worker.id.in_(worker_ids)).all()} if worker_ids else {}
    contacts: dict[str, list[WakeContactLog]] = {}
    if worker_ids:
        for log in (
            db.query(WakeContactLog)
            .filter(WakeContactLog.contact_date == target, WakeContactLog.worker_id.in_(worker_ids))
            .order_by(WakeContactLog.created_at, WakeContactLog.id)
            .all()
        ):
            contacts.setdefault(log.worker_id, []).append(log)
    now_jst = ws.now_utc().astimezone(ws.JST).replace(tzinfo=None)
    is_today = target == ws.today_jst()
    linked = (
        {row[0] for row in db.query(LineWorkerLink.worker_id).filter(LineWorkerLink.worker_id.in_(worker_ids), LineWorkerLink.status == LINK_ACTIVE)}
        if worker_ids
        else set()
    )
    items = []
    for worker_id, rows in by_worker.items():
        report = reports.get(worker_id)
        worker = workers.get(worker_id)
        logs = contacts.get(worker_id, [])
        latest = logs[-1].result if logs else None
        if is_today:
            action = wake_next_action(target=target, first_start=rows[0].start_time, reported=report is not None, latest_result=latest, now=now_jst)
        elif target > ws.today_jst():
            action = (
                {"step": "reported", "label": "", "priority": 90, "next_at": None}
                if report is not None
                else {"step": "future", "label": "当日に確認", "priority": 50, "next_at": None}
            )
        else:
            action = {"step": "none", "label": "", "priority": 90 if report is not None else 60, "next_at": None}
        items.append({
            "worker_id": worker_id,
            "worker_name": worker.name if worker is not None else "",
            "phone": (worker.phone or None) if worker is not None else None,
            "line_linked": worker_id in linked,
            "next_action": action,
            "contacts": [
                {
                    "id": log.id,
                    "result": log.result,
                    "result_label": WAKE_CONTACT_RESULTS.get(log.result, log.result),
                    "note": log.note,
                    "actor_name": log.actor_name,
                    "created_at": log.created_at,
                }
                for log in logs
            ],
            "first_start": _hm(rows[0].start_time),
            "overlap_warning": _overlaps(rows),
            "entries": [
                {
                    "id": e.id,
                    "document_id": e.document_id,
                    "start_time": _hm(e.start_time),
                    "end_time": _hm(e.end_time),
                    "end_next_day": e.end_next_day,
                    "project_name": e.project_name,
                    "site_name": e.site_name,
                    "meeting_place": e.meeting_place,
                    "status": e.status,
                }
                for e in rows
            ],
            "wake_reported_at": report.event_occurred_at if report is not None else None,
            "wake_late_received": report.late_received if report is not None else False,
        })
    # 今連絡すべき人を上に（W-3）。同じ段階なら開始の早い順
    items.sort(key=lambda i: (i["next_action"]["priority"], i["first_start"] or "99:99", i["worker_name"]))
    return {
        "date": target.isoformat(),
        "total": len(items),
        "reported": sum(1 for i in items if i["wake_reported_at"] is not None),
        "items": items,
    }


class WakeContactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    worker_id: str = Field(min_length=1, max_length=26)
    result: str = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=500)


@router.post("/wake-contacts")
def record_wake_contact(
    body: WakeContactBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """起床の目視確認で連絡した結果を記録する（W-2）。追記のみで、取り消しは新しい記録で行う。"""
    if not has_permission(current_user, Permission.WAKE_STATUS_READ):
        raise HTTPException(status_code=403, detail="起床状況を見る権限がありません")
    if body.result not in WAKE_CONTACT_RESULTS:
        raise HTTPException(status_code=400, detail="連絡の結果を選び直してください")
    if db.get(Worker, body.worker_id) is None:
        raise HTTPException(status_code=404, detail="稼働者が見つかりません")
    log = WakeContactLog(
        worker_id=body.worker_id,
        contact_date=body.day,
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
