"""Shared test wake send window. No row or expired window always means off."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from src.models.line_daily import WakeTestNotificationSetting
from src.services import worker_schedule as ws
from src.services.audit import AuditService

LOCK_KEY = 261027540  # Same transaction lock as the monitor; saving off waits for in-flight sends.


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def lock(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})


def setting(db):
    return db.query(WakeTestNotificationSetting).filter_by(id=1).populate_existing().one_or_none()


def active(row, now=None):
    now = utc(now or ws.now_utc())
    return bool(row and row.enabled_from and row.enabled_until and utc(row.enabled_from) <= now < utc(row.enabled_until))


def view(db):
    row = setting(db)
    return {"enabled": active(row), "enabled_from": utc(row.enabled_from) if row else None,
            "enabled_until": utc(row.enabled_until) if row else None, "revision": row.revision if row else 0,
            "updated_at": utc(row.updated_at) if row else None, "updated_by": row.updated_by if row else None}


def update(db, user, *, enabled, enabled_until, revision):
    from fastapi import HTTPException
    lock(db)
    row = setting(db)
    if revision != (row.revision if row else 0):
        raise HTTPException(409, "別の画面で設定が変更されました。最新の設定を読み直してください。")
    now = ws.now_utc()
    until = utc(enabled_until)
    if enabled and (enabled_until is None or enabled_until.tzinfo is None or not now < until <= now + timedelta(hours=24)):
        raise HTTPException(422, "終了時刻は現在より後、24時間以内で指定してください（時差情報が必要です）。")
    if not enabled and enabled_until is not None:
        raise HTTPException(422, "送らない場合は終了時刻を空にしてください。")
    before = view(db)
    if row is None:
        row = WakeTestNotificationSetting(id=1, revision=0)
        db.add(row)
    # Keep the start when extending an active window, so the same due events remain eligible.
    row.enabled_from = utc(row.enabled_from) if enabled and active(row, now) else now if enabled else None
    row.enabled_until = until if enabled else None
    row.updated_at, row.updated_by = now, user.username
    row.revision += 1
    db.flush()
    after = view(db)
    serial = lambda values: {k: v.isoformat() if isinstance(v, datetime) else v for k, v in values.items()}
    AuditService(db).log("wake_test_notifications_changed", target_type="wake_test_notification_settings", actor=user.username,
                         actor_role=getattr(user.role, "value", user.role), before_value=serial(before), after_value=serial(after))
    return after
