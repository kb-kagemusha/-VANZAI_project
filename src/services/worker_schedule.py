"""稼働予定（A1）。依頼書の系列・適用送付行・参加日の状態から、稼働予定を決定的に作り直す。

詳細設計 `docs/ops/LINE_WORKER_DAILY_OPERATIONS_DESIGN_A0_A1_2026-10-22.md` §4〜§6、DEC-063〜068。

- 呼び出し元は必ず系列のロック（lock_series）の中で使う。
- 稼働予定は派生データ。既存の行の状態は判断の根拠にしない（行のIDと一意キーを保つためだけに使う）。
- 物理削除はしない。参加日の状態は追記のみ。
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from src.domain.order_schedule import expand_work_days
from src.models.base import generate_ulid
from src.models.line_daily import (
    END_DECLINED_NEW_VERSION,
    END_DOCUMENT_ENDED,
    END_REMOVED,
    ENTRY_ACTIVE,
    ENTRY_CANCELLED,
    ENTRY_CHANGING,
    ENTRY_SUPERSEDED,
    SOURCE_FULL_ACCEPT,
    SOURCE_OPS_RECORDED_DECLINE,
    SOURCE_PARTIAL_ACCEPT,
    DeliveryParticipationState,
    OrderRequestSeries,
    OrderRequestWorkerApplication,
    WorkerScheduleEntry,
)
from src.models.line_order import OrderRequestFileToken
from src.models.order_request import (
    ACK_ACKED,
    KIND_TEST,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services.audit import AuditService
from src.services.order_request_format import parse_sections

JST = ZoneInfo("Asia/Tokyo")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_jst() -> date:
    return datetime.now(JST).date()


def _postgresql(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


# ---- 系列 -------------------------------------------------------------------

def _confirm_order(version: OrderRequestVersion) -> tuple:
    return (version.confirmed_at or datetime.min.replace(tzinfo=timezone.utc), version.version_no, version.id)



def ensure_series(session: Session, version: OrderRequestVersion) -> str:
    """版の系列を返す。未設定（A1導入前のデータ）なら、元の版から辿って決める。

    「変更を作成」で作った依頼書は、元の版と同じ系列にする（詳細設計§4.4）。
    """
    if version.series_id:
        return version.series_id
    series_id: str | None = None
    if version.revision_of_version_id:
        source = session.get(OrderRequestVersion, version.revision_of_version_id)
        if source is not None and source.id != version.id:
            series_id = ensure_series(session, source)
    if series_id is None:
        sibling = (
            session.query(OrderRequestVersion)
            .filter(
                OrderRequestVersion.document_id == version.document_id,
                OrderRequestVersion.series_id.is_not(None),
            )
            .first()
        )
        series_id = sibling.series_id if sibling else None
    created = False
    if series_id is None:
        series_id = version.document_id
        if session.get(OrderRequestSeries, series_id) is None:
            session.add(OrderRequestSeries(id=series_id, answerable_version_id=None))
            created = True
            session.flush()
    rows = session.query(OrderRequestVersion).filter(OrderRequestVersion.document_id == version.document_id).all()
    for row in rows:
        if row.series_id is None:
            row.series_id = series_id
    version.series_id = series_id
    session.flush()
    if created:
        confirmed = sorted((r for r in rows if r.confirmed_at is not None), key=_confirm_order)
        if confirmed and confirmed[-1].status == STATUS_CONFIRMED:
            session.get(OrderRequestSeries, series_id).answerable_version_id = confirmed[-1].id
            session.flush()
    return series_id


def new_series(session: Session, series_id: str) -> str:
    if session.get(OrderRequestSeries, series_id) is None:
        session.add(OrderRequestSeries(id=series_id, answerable_version_id=None))
        session.flush()
    return series_id


def lock_series(session: Session, series_id: str) -> OrderRequestSeries:
    """系列の行ロック。同じ系列の確定・取消・受諾・辞退・受諾後の辞退・送付・PDF再発行を直列化する。"""
    session.flush()
    if _postgresql(session):
        session.execute(
            text("SELECT id FROM order_request_series WHERE id = :id FOR UPDATE"),
            {"id": series_id},
        )
        session.expire_all()
    series = session.get(OrderRequestSeries, series_id)
    if series is None:
        raise LookupError("依頼書の系列が見つかりません")
    return series


def series_has_confirmed(session: Session, series_id: str) -> bool:
    return (
        session.query(OrderRequestVersion.id)
        .filter(OrderRequestVersion.series_id == series_id, OrderRequestVersion.confirmed_at.is_not(None))
        .first()
        is not None
    )


def series_ended(session: Session, series: OrderRequestSeries) -> bool:
    return series.answerable_version_id is None and series_has_confirmed(session, series.id)


def series_workers(session: Session, series_id: str) -> set[str]:
    workers = {
        row.worker_id
        for row in session.query(OrderRequestDelivery.worker_id)
        .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
        .filter(OrderRequestVersion.series_id == series_id)
    }
    workers |= {
        row.worker_id
        for row in session.query(OrderRequestWorkerApplication.worker_id).filter(
            OrderRequestWorkerApplication.series_id == series_id
        )
    }
    return workers


def delivery_in_version(session: Session, version_id: str | None, worker_id: str) -> OrderRequestDelivery | None:
    if not version_id:
        return None
    return (
        session.query(OrderRequestDelivery)
        .filter(OrderRequestDelivery.version_id == version_id, OrderRequestDelivery.worker_id == worker_id)
        .one_or_none()
    )


# ---- 適用送付行と参加日の状態 ----------------------------------------------------

def get_application(session: Session, series_id: str, worker_id: str) -> OrderRequestWorkerApplication | None:
    return (
        session.query(OrderRequestWorkerApplication)
        .filter(
            OrderRequestWorkerApplication.series_id == series_id,
            OrderRequestWorkerApplication.worker_id == worker_id,
        )
        .one_or_none()
    )


def set_application(
    session: Session,
    *,
    series_id: str,
    worker_id: str,
    delivery: OrderRequestDelivery | None,
    ended_reason: str | None,
    actor: str,
) -> OrderRequestWorkerApplication | None:
    row = get_application(session, series_id, worker_id)
    if row is None and delivery is None:
        return None
    before = None
    if row is None:
        row = OrderRequestWorkerApplication(
            id=generate_ulid(), series_id=series_id, worker_id=worker_id, updated_by=actor, updated_at=now_utc()
        )
        session.add(row)
    else:
        before = {"applied_delivery_id": row.applied_delivery_id, "ended_reason": row.ended_reason}
    new_delivery = delivery.id if delivery is not None else None
    new_version = delivery.version_id if delivery is not None else None
    new_reason = None if delivery is not None else ended_reason
    if before is not None and before == {"applied_delivery_id": new_delivery, "ended_reason": new_reason}:
        return row
    row.applied_delivery_id = new_delivery
    row.applied_version_id = new_version
    row.ended_reason = new_reason
    row.updated_by = actor[:64]
    row.updated_at = now_utc()
    session.flush()
    AuditService(session).log(
        "order_request_application_changed",
        target_type="order_request_series",
        target_id=series_id,
        actor=actor,
        before_value=before,
        after_value={"worker_id": worker_id, "applied_delivery_id": new_delivery, "ended_reason": new_reason},
    )
    return row


def current_state(session: Session, delivery: OrderRequestDelivery) -> DeliveryParticipationState | None:
    if not delivery.current_participation_state_id:
        return None
    return session.get(DeliveryParticipationState, delivery.current_participation_state_id)


def append_state(
    session: Session,
    delivery: OrderRequestDelivery,
    *,
    dates: list[str],
    source: str,
    actor: str,
    reason: str | None = None,
) -> DeliveryParticipationState:
    """参加日の状態を追記し、送付行の現在の状態にする。dates は昇順・重複なしにする。"""
    last = (
        session.query(DeliveryParticipationState.seq)
        .filter(DeliveryParticipationState.delivery_id == delivery.id)
        .order_by(DeliveryParticipationState.seq.desc())
        .first()
    )
    state = DeliveryParticipationState(
        id=generate_ulid(),
        delivery_id=delivery.id,
        seq=(last[0] if last else 0) + 1,
        dates=sorted(set(dates)),
        source=source,
        reason=reason,
        created_by=actor[:64],
        created_at=now_utc(),
    )
    session.add(state)
    session.flush()
    delivery.current_participation_state_id = state.id
    session.flush()
    AuditService(session).log(
        "delivery_participation_recorded",
        target_type="order_request_delivery",
        target_id=delivery.id,
        actor=actor,
        reason=reason,
        after_value={"seq": state.seq, "source": source, "days": len(state.dates)},
    )
    return state


# ---- 日程の読み出し ------------------------------------------------------------

def _version_sections(version: OrderRequestVersion) -> dict:
    snapshot = version.snapshot_json or {}
    try:
        return parse_sections(snapshot.get("request_conditions") or version.request_conditions or "") or {}
    except ValueError:
        return {}


def version_display(version: OrderRequestVersion) -> dict:
    snapshot = version.snapshot_json or {}
    sections = _version_sections(version)
    return {
        "project_name": str(sections.get("project_name") or ""),
        "site_name": str(snapshot.get("site_name") or version.site_name or ""),
        "site_address": snapshot.get("site_address") if snapshot else version.site_address,
        "meeting_place": str(sections.get("meeting_place") or "") or None,
    }


def version_work_days(version: OrderRequestVersion) -> list[dict]:
    schedule = _version_sections(version).get("schedule")
    return expand_work_days(schedule) if schedule else []


def offered_dates_for(work_days: list[dict], absences: list[str] | None) -> list[str] | None:
    """提示日。日程のない（自由文の）依頼書は None（稼働予定の対象外）。"""
    if not work_days:
        return None
    absent = set(absences or [])
    return sorted({d["work_date"] for d in work_days if d["work_date"] not in absent})


def _time(value: str) -> time | None:
    if not value:
        return None
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def split_started(version: OrderRequestVersion, dates: list[str], now: datetime | None = None) -> tuple[list[str], list[str]]:
    """参加日を「勤務がすでに始まった日」と「まだ始まっていない日」に分ける（日本時間。統合計画 D-05）。

    勤務の開始日時は、その日の勤務グループの開始時刻（無ければその日の 0:00）。前日開始の夜勤はその開始日の扱い。
    """
    current = (now or now_utc()).astimezone(JST)
    starts: dict[str, datetime] = {}
    for day in version_work_days(version):
        start = _time(day["start_time"]) or time(0, 0)
        moment = datetime.combine(date.fromisoformat(day["work_date"]), start, tzinfo=JST)
        if day["work_date"] not in starts or moment < starts[day["work_date"]]:
            starts[day["work_date"]] = moment
    started, upcoming = [], []
    for day in sorted(set(dates)):
        moment = starts.get(day) or datetime.combine(date.fromisoformat(day), time(0, 0), tzinfo=JST)
        (started if moment <= current else upcoming).append(day)
    return started, upcoming


def day_start_time(version: OrderRequestVersion, day: str) -> str | None:
    """その日の勤務の開始時刻（"09:00"）。無ければ None。"""
    times = sorted(d["start_time"] for d in version_work_days(version) if d["work_date"] == day and d["start_time"])
    return times[0] if times else None


# ---- 再構築 ------------------------------------------------------------------

def rebuild(session: Session, series_id: str, worker_id: str, *, actor: str) -> list[dict]:
    """(系列 × 稼働者) の稼働予定を、元データだけからあるべき状態に合わせる。変更した行の一覧を返す。"""
    series = session.get(OrderRequestSeries, series_id)
    application = get_application(session, series_id, worker_id)
    applied = (
        session.get(OrderRequestDelivery, application.applied_delivery_id)
        if application is not None and application.applied_delivery_id
        else None
    )

    expected: dict[tuple, dict] = {}
    applied_state = None
    if applied is not None:
        version = session.get(OrderRequestVersion, applied.version_id)
        document = session.get(OrderRequestDocument, version.document_id)
        applied_state = current_state(session, applied)
        participating = set(applied_state.dates) if applied_state is not None else set()
        status = ENTRY_ACTIVE if series is not None and series.answerable_version_id == version.id else ENTRY_CHANGING
        display = version_display(version)
        for day in version_work_days(version):
            if day["work_date"] not in participating:
                continue
            key = (applied.id, day["work_group_id"], day["work_date"])
            expected[key] = {
                "series_id": series_id,
                "document_id": document.id,
                "version_id": version.id,
                "delivery_id": applied.id,
                "worker_id": worker_id,
                "work_group_id": day["work_group_id"],
                "work_date": date.fromisoformat(day["work_date"]),
                "start_time": _time(day["start_time"]),
                "end_time": _time(day["end_time"]),
                "end_next_day": day["end_next_day"],
                "status": status,
                "status_reason": None,
                "source_state_id": applied_state.id if applied_state is not None else None,
                "is_test": document.kind == KIND_TEST,
                **display,
            }

    existing = (
        session.query(WorkerScheduleEntry)
        .filter(WorkerScheduleEntry.series_id == series_id, WorkerScheduleEntry.worker_id == worker_id)
        .all()
    )
    by_key = {(row.delivery_id, row.work_group_id, row.work_date.isoformat()): row for row in existing}

    # 「より新しい版に、同じ人の受諾済みの送付行がある」か（R3-03）。受諾の記録だけで判定する。
    acked_orders = [
        _confirm_order(session.get(OrderRequestVersion, d.version_id))
        for d in session.query(OrderRequestDelivery)
        .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
        .filter(
            OrderRequestVersion.series_id == series_id,
            OrderRequestDelivery.worker_id == worker_id,
            OrderRequestDelivery.ack_status == ACK_ACKED,
        )
    ]

    changes: list[dict] = []

    def apply(row: WorkerScheduleEntry | None, values: dict) -> None:
        if row is None:
            row = WorkerScheduleEntry(id=generate_ulid(), **values)
            session.add(row)
            changes.append({"key": [values["delivery_id"], values["work_group_id"], values["work_date"].isoformat()], "from": None, "to": values["status"], "reason": values["status_reason"]})
            return
        diff = {k: v for k, v in values.items() if getattr(row, k) != v}
        if not diff:
            return
        if "status" in diff or "status_reason" in diff:
            changes.append({"key": [row.delivery_id, row.work_group_id, row.work_date.isoformat()], "from": row.status, "to": values["status"], "reason": values["status_reason"]})
        for k, v in diff.items():
            setattr(row, k, v)

    for key, values in expected.items():
        apply(by_key.get((key[0], key[1], key[2])), values)

    for row_key, row in by_key.items():
        if (row_key[0], row_key[1], row_key[2]) in expected:
            continue
        row_version = session.get(OrderRequestVersion, row.version_id)
        newer_acked = any(order > _confirm_order(row_version) for order in acked_orders)
        if newer_acked and (applied is None or row.delivery_id != applied.id):
            status, reason = ENTRY_SUPERSEDED, None
        elif applied is None:
            status, reason = ENTRY_CANCELLED, (application.ended_reason if application and application.ended_reason else END_DOCUMENT_ENDED)
        elif row.delivery_id == applied.id:
            status, reason = ENTRY_CANCELLED, ("ops_recorded_decline" if applied_state is not None and applied_state.source == SOURCE_OPS_RECORDED_DECLINE else "not_in_participation")
        else:
            status, reason = ENTRY_CANCELLED, "not_in_participation"
        values = {"status": status, "status_reason": reason}
        if row.status != status or row.status_reason != reason:
            changes.append({"key": list(row_key), "from": row.status, "to": status, "reason": reason})
            row.status = status
            row.status_reason = reason

    session.flush()
    if changes:
        AuditService(session).log(
            "worker_schedule_entries_rebuilt",
            target_type="order_request_series",
            target_id=series_id,
            actor=actor,
            after_value={"worker_id": worker_id, "changes": changes[:200], "change_count": len(changes)},
        )
    return changes


def rebuild_series(session: Session, series_id: str, *, actor: str) -> None:
    for worker_id in sorted(series_workers(session, series_id)):
        rebuild(session, series_id, worker_id, actor=actor)


# ---- PDFの閲覧条件（D02） ---------------------------------------------------------

def pdf_viewable(session: Session, delivery: OrderRequestDelivery) -> bool:
    """PDFトークンの発行と読み出しで共通に使う閲覧条件。"""
    version = session.get(OrderRequestVersion, delivery.version_id)
    if version is None or version.status == STATUS_CANCELLED or version.dispatch_stopped or delivery.view_revoked:
        return False
    if not version.series_id:
        return True  # 系列が未設定の旧データは従来どおり
    series = session.get(OrderRequestSeries, version.series_id)
    if series is None or series.answerable_version_id is None:
        return False
    if delivery_in_version(session, series.answerable_version_id, delivery.worker_id) is None:
        return False
    if delivery.version_id == series.answerable_version_id:
        return True
    application = get_application(session, version.series_id, delivery.worker_id)
    return application is not None and application.applied_version_id == delivery.version_id


def revoke_tokens_for_removed(session: Session, series_id: str, worker_id: str) -> int:
    """修正版で送付先から外れた人に、系列内の旧い版で発行した期限内のPDFトークンを無効にする。"""
    now = now_utc()
    rows = (
        session.query(OrderRequestFileToken)
        .join(OrderRequestDelivery, OrderRequestDelivery.id == OrderRequestFileToken.delivery_id)
        .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
        .filter(
            OrderRequestVersion.series_id == series_id,
            OrderRequestDelivery.worker_id == worker_id,
            OrderRequestFileToken.revoked_at.is_(None),
            OrderRequestFileToken.expires_at > now,
        )
        .all()
    )
    for row in rows:
        row.revoked_at = now
    session.flush()
    return len(rows)


def active_entries_on_or_after(session: Session, document_id: str, day: date) -> bool:
    return (
        session.query(WorkerScheduleEntry.id)
        .filter(
            WorkerScheduleEntry.document_id == document_id,
            WorkerScheduleEntry.work_date >= day,
            or_(WorkerScheduleEntry.status == ENTRY_ACTIVE, WorkerScheduleEntry.status == ENTRY_CHANGING),
        )
        .first()
        is not None
    )


__all__ = [
    "END_DECLINED_NEW_VERSION",
    "SOURCE_FULL_ACCEPT",
    "SOURCE_OPS_RECORDED_DECLINE",
    "SOURCE_PARTIAL_ACCEPT",
    "split_started",
    "day_start_time",
    "END_DOCUMENT_ENDED",
    "END_REMOVED",
    "JST",
    "active_entries_on_or_after",
    "append_state",
    "current_state",
    "delivery_in_version",
    "ensure_series",
    "get_application",
    "lock_series",
    "new_series",
    "now_utc",
    "offered_dates_for",
    "pdf_viewable",
    "rebuild",
    "rebuild_series",
    "revoke_tokens_for_removed",
    "series_ended",
    "set_application",
    "today_jst",
    "version_display",
    "version_work_days",
]
