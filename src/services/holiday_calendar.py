"""Shared calendar: Cabinet Office CSV is authoritative inside its coverage; later years stay library candidates."""
import csv
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import calendar as monthcalendar
import urllib.request

import jpholiday
from sqlalchemy.exc import IntegrityError

from src.models.holiday_calendar import HolidayCalendarDay, HolidayCsvImport
from src.services.audit import AuditService
from src.services.order_request_service import OrderRequestError

JST = ZoneInfo("Asia/Tokyo")
CABINET_CSV_URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
SOURCE_CABINET = "cabinet_csv"
SOURCE_MANUAL = "manual"


def calendar(db, start: date, end: date) -> list[dict]:
    if end < start or (end - start).days > 3660:
        raise OrderRequestError(422, "祝日を確認する期間は開始日から10年以内にしてください")
    covered_until = _coverage_end(db)
    saved = {row.day: row for row in db.query(HolidayCalendarDay).filter(
        HolidayCalendarDay.day >= start, HolidayCalendarDay.day <= end).all()}
    result = []
    day = start
    while day <= end:
        row = saved.get(day)
        if row:
            result.append({"day": day.isoformat(), "is_holiday": row.is_holiday, "name": row.name,
                           "revision": row.revision, "source": row.source})
        elif covered_until is None or day > covered_until:
            name = jpholiday.is_holiday_name(day) or ""
            if name:
                result.append({"day": day.isoformat(), "is_holiday": True, "name": name, "revision": 0, "source": "library"})
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
    row.source = SOURCE_MANUAL
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


def import_status(db, *, today: date | None = None) -> dict:
    row = _latest_import(db)
    today = today or datetime.now(JST).date()
    if row is None:
        return {"imported": False, "label": None, "needs_refresh": True,
                "notice": "内閣府の祝日CSVはまだ取り込まれていません。祝日一覧の正本として取り込んでください。"}
    imported = row.imported_at if row.imported_at.tzinfo else row.imported_at.replace(tzinfo=timezone.utc)
    imported = imported.astimezone(JST)
    start = f"{row.coverage_start.year}年{row.coverage_start.month}月"
    end = f"{row.coverage_end.year}年{row.coverage_end.month}月"
    needs_refresh = row.coverage_end < _add_months(today, 3)
    return {
        "imported": True,
        "label": f"内閣府CSV取込：{imported.year}年{imported.month}月{imported.day}日、{start}〜{end}分",
        "needs_refresh": needs_refresh,
        "notice": f"取り込み済みの祝日は{end}までです。残り3か月を切ったので、内閣府のCSVを取り込んでください。" if needs_refresh else None,
    }


def import_official_csv(db, *, actor, source_url: str = CABINET_CSV_URL) -> dict:
    return import_cabinet_csv(db, actor=actor, raw=_fetch_cabinet_csv(source_url), source_url=source_url)


def import_cabinet_csv(db, *, actor, raw: bytes, source_url: str) -> dict:
    official = _parse_cabinet_csv(raw)
    previous = _latest_import(db)
    previous_days = _json_map(previous.official_days) if previous else {}
    current_days = {day.isoformat(): name for day, name in official.items()}
    added, removed, renamed = _changes(previous_days, current_days)
    saved = {row.day: row for row in db.query(HolidayCalendarDay).all()}
    now = datetime.now(timezone.utc)
    for day, name in official.items():
        row = saved.get(day)
        if row and row.source == SOURCE_MANUAL:
            continue
        if row:
            row.is_holiday = True
            row.name = name
            row.source = SOURCE_CABINET
            row.revision += 1
            row.updated_by = actor.id
            row.updated_at = now
        else:
            db.add(HolidayCalendarDay(day=day, is_holiday=True, name=name, source=SOURCE_CABINET,
                revision=1, updated_by=actor.id, updated_at=now))
    coverage_start, coverage_end = min(official), max(official)
    for day, row in saved.items():
        if row.source == SOURCE_MANUAL or day in official:
            continue
        if row.source == SOURCE_CABINET or coverage_start <= day <= coverage_end:
            db.delete(row)
    record = HolidayCsvImport(imported_at=now, actor_user_id=actor.id, source_url=source_url,
        coverage_start=coverage_start, coverage_end=coverage_end, imported_count=len(official),
        added_days=added, removed_days=removed, renamed_days=renamed, official_days=current_days)
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise OrderRequestError(409, "祝日CSVの取り込みが競合しました。もう一度取り込んでください") from exc
    AuditService(db).log("holiday_csv_imported", target_type="holiday_csv_import", target_id=record.id,
        actor=actor.username, actor_role=actor.role,
        after_value={"source_url": source_url, "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(), "imported_count": len(official),
            "added_days": added, "removed_days": removed, "renamed_days": renamed})
    return import_status(db)


def _coverage_end(db) -> date | None:
    row = _latest_import(db)
    return row.coverage_end if row else None


def _latest_import(db) -> HolidayCsvImport | None:
    return db.query(HolidayCsvImport).order_by(HolidayCsvImport.imported_at.desc(), HolidayCsvImport.id.desc()).first()


def _fetch_cabinet_csv(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "VANZAI/holiday-calendar"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except Exception as exc:
        raise OrderRequestError(502, "内閣府の祝日CSVを取得できませんでした。時間をおいて再度取り込んでください") from exc
    if not raw:
        raise OrderRequestError(422, "内閣府の祝日CSVが空です。取得元を確認してください")
    return raw


def _parse_cabinet_csv(raw: bytes) -> dict[date, str]:
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp932")
    official: dict[date, str] = {}
    for row in csv.reader(content.splitlines()):
        if len(row) < 2 or not row[0].strip():
            continue
        try:
            parts = [int(part) for part in row[0].strip().replace("-", "/").split("/")]
            day = date(*parts)
        except (ValueError, TypeError):
            continue
        name = row[1].strip()
        if not name:
            continue
        if len(name) > 200:
            raise OrderRequestError(422, "CSVの祝日名が長すぎます。取得元を確認してください")
        official[day] = name
    if not official:
        raise OrderRequestError(422, "CSVに祝日がありません。取得元を確認してください")
    return official


def _changes(previous: dict[str, str], current: dict[str, str]) -> tuple[list[dict], list[dict], list[dict]]:
    added = [{"day": day, "name": current[day]} for day in sorted(set(current) - set(previous))]
    removed = [{"day": day, "name": previous[day]} for day in sorted(set(previous) - set(current))]
    renamed = [{"day": day, "before": previous[day], "after": current[day]}
               for day in sorted(set(previous) & set(current)) if previous[day] != current[day]]
    return added, removed, renamed


def _json_map(value) -> dict[str, str]:
    if isinstance(value, str):
        import json
        value = json.loads(value)
    return {str(key): str(name) for key, name in (value or {}).items()}


def _add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, monthcalendar.monthrange(year, month)[1]))
