"""Shared calendar candidates and explicitly audited operator overrides."""
from datetime import date, datetime, timedelta, timezone

import jpholiday
from sqlalchemy.exc import IntegrityError

from src.models.holiday_calendar import HolidayCalendarDay
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestError


def calendar(db, start: date, end: date) -> list[dict]:
    if end < start or (end - start).days > 3660:
        raise OrderRequestError(422, "祝日を確認する期間は開始日から10年以内にしてください")
    saved = {row.day: row for row in db.query(HolidayCalendarDay).filter(
        HolidayCalendarDay.day >= start, HolidayCalendarDay.day <= end).all()}
    result = []
    day = start
    while day <= end:
        name = jpholiday.is_holiday_name(day) or ""
        row = saved.get(day)
        if row or name:
            result.append({"day": day.isoformat(), "is_holiday": row.is_holiday if row else True,
                           "name": row.name if row else name, "revision": row.revision if row else 0,
                           "source": row.source if row else "library"})
        day += timedelta(days=1)
    return result


def update_day(db, *, day: date, is_holiday: bool, name: str, revision: int, actor):
    row = db.query(HolidayCalendarDay).filter_by(day=day).with_for_update().one_or_none()
    if revision != (row.revision if row else 0):
        raise OrderRequestError(409, "祝日一覧が変更されました。最新の一覧を確認してください")
    before = {"is_holiday": row.is_holiday, "name": row.name, "revision": row.revision} if row else {
        "is_holiday": bool(jpholiday.is_holiday_name(day)), "name": jpholiday.is_holiday_name(day) or "", "revision": 0}
    if not row:
        row = HolidayCalendarDay(day=day, revision=0)
        db.add(row)
    row.is_holiday = is_holiday
    row.name = name.strip() if is_holiday else ""
    row.source = "manual"
    row.revision += 1
    row.updated_by = actor.id
    row.updated_at = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError as exc:
        raise OrderRequestError(409, "祝日一覧が変更されました。最新の一覧を確認してください") from exc
    AuditService(db).log("holiday_calendar_changed", target_type="holiday_calendar", target_id=day.isoformat(),
        actor=actor.username, actor_role=actor.role, before_value=before,
        after_value={"is_holiday": row.is_holiday, "name": row.name, "revision": row.revision})
    return {"day": day.isoformat(), "is_holiday": row.is_holiday, "name": row.name,
            "revision": row.revision, "source": row.source}


def confirm_calendar(db, *, start: date, end: date, days: list[str], actor):
    """Persist the candidates the operator reviewed; existing overrides stay authoritative."""
    current = calendar(db, start, end)
    actual = [item["day"] for item in current if item["is_holiday"]]
    if sorted(days) != actual or len(days) != len(set(days)):
        raise OrderRequestError(409, "祝日一覧が変更されました。最新の一覧を確認してください")
    for item in current:
        if item["revision"] != 0:
            continue
        row = HolidayCalendarDay(day=date.fromisoformat(item["day"]), is_holiday=True,
            name=item["name"], source="library", revision=1, updated_by=actor.id,
            updated_at=datetime.now(timezone.utc))
        db.add(row)
        AuditService(db).log("holiday_calendar_initialized", target_type="holiday_calendar", target_id=item["day"],
            actor=actor.username, actor_role=actor.role, after_value={"is_holiday": True, "name": item["name"], "revision": 1})
    try:
        db.flush()
    except IntegrityError as exc:
        raise OrderRequestError(409, "祝日一覧が変更されました。最新の一覧を確認してください") from exc
    return calendar(db, start, end)
