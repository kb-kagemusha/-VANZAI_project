"""当日の起床状況（A1、DEC-064）。テスト用の予定と報告は含めない。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.jwt_auth import get_current_active_user
from src.models.enums import Permission
from src.models.line_daily import ENTRY_ACTIVE, ENTRY_CHANGING, WakeReport, WorkerScheduleEntry
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.master import User, Worker
from src.services import worker_schedule as ws
from src.services.auth import has_permission

router = APIRouter(prefix="/api/line-daily", tags=["LINE daily"])


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
    linked = (
        {row[0] for row in db.query(LineWorkerLink.worker_id).filter(LineWorkerLink.worker_id.in_(worker_ids), LineWorkerLink.status == LINK_ACTIVE)}
        if worker_ids
        else set()
    )
    items = []
    for worker_id, rows in by_worker.items():
        report = reports.get(worker_id)
        worker = workers.get(worker_id)
        items.append({
            "worker_id": worker_id,
            "worker_name": worker.name if worker is not None else "",
            "line_linked": worker_id in linked,
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
    items.sort(key=lambda i: (i["wake_reported_at"] is not None, i["first_start"] or "99:99", i["worker_name"]))
    return {
        "date": target.isoformat(),
        "total": len(items),
        "reported": sum(1 for i in items if i["wake_reported_at"] is not None),
        "items": items,
    }
