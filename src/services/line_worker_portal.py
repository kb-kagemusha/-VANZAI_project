"""稼働者向けのWeb確認画面（統合計画 ②、Web確認画面計画 v0.2、DEC-084）。

公式LINEのリッチメニュー⑤⑥から開くLIFF画面のための、閲覧専用の読み出し。
- ホーム：月間の予定（仕事のある日）、直近7日の予定、確認が必要な依頼、その月の報酬見込みと稼働日数
- 受託済みの依頼書の一覧と、依頼書（PDF）を開くリンクの発行

閲覧では受諾・辞退・取消・既読などの業務の状態を変えない（PDFリンクの発行だけは従来の⑤と同じく記録する）。
報酬見込みは表を増やさず、その都度、予定（受諾した版）と依頼書の単価から計算する（D-06：過去の表示の証明は不要）。
"""
from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.line_daily import (
    ENTRY_ACTIVE,
    ENTRY_CHANGING,
    FEATURE_PICK_DATES,
    FEATURE_WEB_HOME,
    FEATURE_WEB_ORDERS,
    FEATURE_WEB_REPLY,
    OrderRequestSeries,
    WorkerScheduleEntry,
)
from src.models.line_order import OrderRequestFileToken
from src.models.master import Worker
from src.models.order_request import (
    ACK_DECLINE_PENDING,
    ACK_UNACKED,
    KIND_TEST,
    SEND_ACCEPTED,
    SEND_UNKNOWN,
    STATUS_CANCELLED,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.line_daily import PDF_TOKEN_DAYS, enabled_actions
from src.services.line_messaging import line_settings

# 報酬見込みの計算式の版。計算の仕方を変えたら上げる（統合計画 R-08：同じ入力なら同じ結果を再計算できるように）
ESTIMATE_FORMULA_VERSION = "daily-v1"
WEEK_DAYS = 7
MONTH_RANGE = 24  # 今月から前後何か月まで開けるか


class PortalError(Exception):
    def __init__(self, status_code: int, message: str, code: str = "error"):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code


def parse_month(value: str | None, today: date) -> date:
    """「2026-11」を月の1日に。空なら今月。範囲外・形式違いはエラー。"""
    if not value:
        return today.replace(day=1)
    try:
        year, month = (int(part) for part in value.split("-"))
        first = date(year, month, 1)
    except (ValueError, TypeError):
        raise PortalError(400, "月の指定が正しくありません。", "month") from None
    if len(value) != 7 or abs((first.year - today.year) * 12 + first.month - today.month) > MONTH_RANGE:
        raise PortalError(400, "月の指定が正しくありません。", "month")
    return first


def _month_end(first: date) -> date:
    following = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
    return following - timedelta(days=1)


def _hm(value) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _rate_for(schedule: dict, entry: WorkerScheduleEntry) -> dict | None:
    """その勤務日に使う単価（日付・期間ごとの単価）。日付と勤務グループの両方で絞り、勤務グループが一致するものを優先する。"""
    day = entry.work_date.isoformat()
    candidates = []
    for rate in (schedule or {}).get("rate_groups", []) or []:
        start, end = rate.get("from") or "", rate.get("to") or rate.get("from") or ""
        if start and not (start <= day <= end):
            continue
        group = rate.get("work_group_id")
        if group and group != entry.work_group_id:
            continue
        candidates.append((0 if group == entry.work_group_id else 1, rate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def estimate_for(session: Session, entries: list[WorkerScheduleEntry]) -> dict:
    """報酬見込み（F-01・F-02・D-02・D-08）。

    - 依頼書の日給を、参加する日ごとに1回（予定の1行＝1つの依頼書の1日）。別々の依頼書で同じ日に働けばそれぞれ数える。
    - 稼働日数は日付で数える（同じ日に2件でも1日）。
    - 時給・単価の分からない予定は0円とせず、対象外として件数を返す。
    - 変更確認中は旧い受諾の版（予定に記録された版）の単価。インセンティブ・税は加減しない。
    - 合計は小数のまま足し、表示用に円未満を切り捨てる。
    - テストの依頼書の予定は正式の合計に混ぜず、"test" に同じ計算で別に返す（0.51.5：画面の確認用に【テスト】として表示する）。
    """
    versions: dict[str, dict] = {}
    formal = _estimate(session, [e for e in entries if not e.is_test], versions)
    tests = [e for e in entries if e.is_test]
    formal["test"] = _estimate(session, tests, versions) if tests else None
    return formal


def _estimate(session: Session, entries: list[WorkerScheduleEntry], versions: dict[str, dict]) -> dict:
    total = Decimal("0")
    counted = 0
    hourly = 0
    unknown = 0
    separate_cost = False
    days: set[date] = set()
    for entry in entries:
        days.add(entry.work_date)
        if entry.version_id not in versions:
            version = session.get(OrderRequestVersion, entry.version_id)
            sections = ws._version_sections(version) if version is not None else {}
            versions[entry.version_id] = sections.get("schedule") or {}
        rate = _rate_for(versions[entry.version_id], entry)
        if rate is None or not str(rate.get("amount") or "").strip():
            unknown += 1
            continue
        if rate.get("unit") == "hour":
            hourly += 1
            continue
        try:
            amount = Decimal(str(rate["amount"]))
        except (InvalidOperation, ValueError):
            unknown += 1
            continue
        total += amount
        counted += 1
        if rate.get("lunch_included") is False or rate.get("transport_included") is False:
            separate_cost = True
    return {
        "amount": str(total.to_integral_value(rounding=ROUND_FLOOR)) if counted else None,
        "work_days": len(days),
        "counted_entries": counted,
        "excluded_hourly": hourly,
        "excluded_unknown": unknown,
        "separate_cost": separate_cost,
        "formula_version": ESTIMATE_FORMULA_VERSION,
    }


class LineWorkerPortal:
    def __init__(self, session: Session):
        self.session = session

    def require(self, *features: str) -> set[str]:
        enabled = enabled_actions(self.session)
        if not any(feature in enabled for feature in features):
            raise PortalError(403, "この機能はまだご利用いただけません。", "feature_off")
        return enabled

    # ---- 予定 -----------------------------------------------------------------
    def _entries(self, worker_id: str, start: date, end: date) -> list[WorkerScheduleEntry]:
        return (
            ws.visible_schedule_entries(self.session)
            .filter(
                WorkerScheduleEntry.worker_id == worker_id,
                WorkerScheduleEntry.work_date >= start,
                WorkerScheduleEntry.work_date <= end,
                or_(WorkerScheduleEntry.status == ENTRY_ACTIVE, WorkerScheduleEntry.status == ENTRY_CHANGING),
            )
            .order_by(WorkerScheduleEntry.work_date, WorkerScheduleEntry.start_time, WorkerScheduleEntry.id)
            .all()
        )

    def _change_info(self, entry: WorkerScheduleEntry, enabled: set[str], cache: dict[str, dict]) -> dict | None:
        """「内容変更の確認待ち」の予定で、本人がすること（0.51.13）。

        - sent：新しい版が本人に届いていて、返事を待っている（新しい依頼書を開く・日付を選んで返事する）
        - not_sent：運営が新しい版を確定したが、まだ本人に届いていない（届くのを待つ）
        """
        if entry.status != ENTRY_CHANGING:
            return None
        if entry.series_id in cache:
            return cache[entry.series_id]
        info = {"state": "not_sent", "delivery_id": None, "can_pick": False, "pdf_available": False}
        series = self.session.get(OrderRequestSeries, entry.series_id)
        newer = ws.delivery_in_version(self.session, series.answerable_version_id, entry.worker_id) if series is not None else None
        if (
            newer is not None
            and newer.id != entry.delivery_id
            and newer.send_status in (SEND_ACCEPTED, SEND_UNKNOWN)
            and newer.ack_status in (ACK_UNACKED, ACK_DECLINE_PENDING)
            and not newer.view_revoked
        ):
            version = self.session.get(OrderRequestVersion, newer.version_id)
            if version is not None and version.status != STATUS_CANCELLED and not version.dispatch_stopped:
                info = {
                    "state": "sent",
                    "delivery_id": newer.id,
                    "can_pick": bool(version.allow_partial_accept and newer.offered_dates and FEATURE_PICK_DATES in enabled),
                    "pdf_available": bool(version.pdf_object_key) and ws.pdf_viewable(self.session, newer),
                }
        cache[entry.series_id] = info
        return info

    def _entry_out(self, entry: WorkerScheduleEntry, documents: dict[str, OrderRequestDocument], enabled: set[str] | None = None, changes: dict[str, dict] | None = None) -> dict:
        if entry.document_id not in documents:
            documents[entry.document_id] = self.session.get(OrderRequestDocument, entry.document_id)
        document = documents[entry.document_id]
        return {
            "id": entry.id,
            "date": entry.work_date.isoformat(),
            "start_time": _hm(entry.start_time),
            "end_time": _hm(entry.end_time),
            "end_next_day": bool(entry.end_next_day),
            "project_name": entry.project_name or "",
            "site_name": entry.site_name or "",
            "site_address": entry.site_address or None,
            "meeting_place": entry.meeting_place or None,
            "changing": entry.status == ENTRY_CHANGING,
            "change": self._change_info(entry, enabled or set(), changes if changes is not None else {}),
            "is_test": bool(entry.is_test),
            "delivery_id": entry.delivery_id,
            "document_number": document.document_number if document is not None else "",
        }

    @staticmethod
    def _by_day(rows: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["date"]].append(row)
        return [{"date": day, "entries": grouped[day]} for day in sorted(grouped)]

    # ---- 確認が必要な依頼 --------------------------------------------------------
    def confirmations(self, worker: Worker, enabled: set[str]) -> list[dict]:
        """未回答・変更確認待ち（D-07 と同じ判定）。系列ごとに1件。回答できないものは出さない。"""
        rows = (
            self.session.query(OrderRequestDelivery)
            .filter(
                OrderRequestDelivery.worker_id == worker.id,
                OrderRequestDelivery.send_status.in_((SEND_ACCEPTED, SEND_UNKNOWN)),
                OrderRequestDelivery.ack_status.in_((ACK_UNACKED, ACK_DECLINE_PENDING)),
                OrderRequestDelivery.view_revoked.is_(False),
            )
            .all()
        )
        items: dict[str, dict] = {}
        for delivery in rows:
            version = self.session.get(OrderRequestVersion, delivery.version_id)
            if version is None or version.status == STATUS_CANCELLED or version.dispatch_stopped or not version.series_id:
                continue
            series = self.session.get(OrderRequestSeries, version.series_id)
            if series is None or series.answerable_version_id != version.id:
                continue
            document = self.session.get(OrderRequestDocument, version.document_id)
            if document is None or document.deleted_at is not None:
                continue
            application = ws.get_application(self.session, series.id, worker.id)
            kind = "changing" if application is not None and application.applied_delivery_id else "unanswered"
            display = ws.version_display(version)
            dates = sorted({d["work_date"] for d in ws.version_work_days(version)})
            offered = [d for d in (delivery.offered_dates or []) if d in set(dates)]
            items[series.id] = {
                "kind": kind,
                "delivery_id": delivery.id,
                "document_number": document.document_number,
                "version_no": version.version_no,
                "project_name": display["project_name"],
                "site_name": display["site_name"],
                "first_date": (offered or dates or [None])[0],
                "last_date": (offered or dates or [None])[-1],
                "offered_days": len(offered),
                "follow_up_due_on": version.follow_up_due_on.isoformat() if version.follow_up_due_on else None,
                "is_test": document.kind == KIND_TEST,
                "can_pick": bool(version.allow_partial_accept and offered and FEATURE_PICK_DATES in enabled),
                "pdf_available": bool(version.pdf_object_key) and ws.pdf_viewable(self.session, delivery),
            }
        return sorted(items.values(), key=lambda item: (item["kind"] != "changing", item["first_date"] or "9999-12-31", item["document_number"]))

    # ---- ホーム ----------------------------------------------------------------
    def home(self, worker: Worker, month: str | None) -> dict:
        enabled = self.require(FEATURE_WEB_HOME)
        today = ws.today_jst()
        first = parse_month(month, today)
        last = _month_end(first)
        week_end = today + timedelta(days=WEEK_DAYS - 1)
        documents: dict[str, OrderRequestDocument] = {}
        changes: dict[str, dict] = {}
        month_entries = self._entries(worker.id, first, last)
        week_entries = self._entries(worker.id, today, week_end)
        return {
            "today": today.isoformat(),
            "worker_name": worker.name,
            "month": first.strftime("%Y-%m"),
            "month_days": self._by_day([self._entry_out(e, documents, enabled, changes) for e in month_entries]),
            "week": {
                "from": today.isoformat(),
                "to": week_end.isoformat(),
                "days": self._by_day([self._entry_out(e, documents, enabled, changes) for e in week_entries]),
            },
            "estimate": estimate_for(self.session, month_entries),
            "confirmations": self.confirmations(worker, enabled),
            "orders_enabled": FEATURE_WEB_ORDERS in enabled,
            # Web確認画面から返事ができるか（③-C。③-B との結合試験までは無効）
            "reply_enabled": FEATURE_WEB_REPLY in enabled,
            "fetched_at": ws.now_utc().isoformat(),
        }

    # ---- 受託済みの依頼書 ----------------------------------------------------------
    def orders(self, worker: Worker) -> dict:
        enabled = self.require(FEATURE_WEB_ORDERS)
        changes: dict[str, dict] = {}
        today = ws.today_jst()
        since = today.replace(day=1)  # 今月の初めから（今月すでに働いた分も見られるように。P-08）
        rows = (
            ws.visible_schedule_entries(self.session)
            .filter(
                WorkerScheduleEntry.worker_id == worker.id,
                WorkerScheduleEntry.work_date >= since,
                or_(WorkerScheduleEntry.status == ENTRY_ACTIVE, WorkerScheduleEntry.status == ENTRY_CHANGING),
            )
            .order_by(WorkerScheduleEntry.work_date, WorkerScheduleEntry.start_time)
            .all()
        )
        by_delivery: dict[str, list[WorkerScheduleEntry]] = {}
        for row in rows:
            by_delivery.setdefault(row.delivery_id, []).append(row)
        items = []
        for delivery_id, entries in by_delivery.items():
            delivery = self.session.get(OrderRequestDelivery, delivery_id)
            if delivery is None:
                continue
            version = self.session.get(OrderRequestVersion, delivery.version_id)
            document = self.session.get(OrderRequestDocument, version.document_id) if version is not None else None
            if version is None or document is None:
                continue
            changing = any(e.status == ENTRY_CHANGING for e in entries)
            newer = None
            if changing and version.series_id:
                series = self.session.get(OrderRequestSeries, version.series_id)
                newer_delivery = ws.delivery_in_version(self.session, series.answerable_version_id, worker.id) if series else None
                if newer_delivery is not None and newer_delivery.id != delivery.id:
                    newer = newer_delivery.id
            dates = sorted({e.work_date for e in entries})
            items.append({
                "delivery_id": delivery.id,
                "document_number": document.document_number,
                "version_no": version.version_no,
                "project_name": entries[0].project_name or "",
                "site_name": entries[0].site_name or "",
                "first_date": dates[0].isoformat(),
                "last_date": dates[-1].isoformat(),
                "work_days": len(dates),
                "upcoming_days": sum(1 for d in dates if d >= today),
                "acked_at": delivery.acked_at.isoformat() if delivery.acked_at else None,
                "changing": changing,
                "change": next((self._change_info(e, enabled, changes) for e in entries if e.status == ENTRY_CHANGING), None),
                "newer_delivery_id": newer,
                "is_test": bool(entries[0].is_test),
                "pdf_available": bool(version.pdf_object_key) and ws.pdf_viewable(self.session, delivery),
            })
        items.sort(key=lambda item: (item["upcoming_days"] == 0, item["first_date"], item["document_number"]))
        return {"today": today.isoformat(), "since": since.isoformat(), "items": items, "reply_enabled": FEATURE_WEB_REPLY in enabled, "fetched_at": ws.now_utc().isoformat()}

    # ---- 依頼書（PDF）を開く ---------------------------------------------------------
    def pdf_link(self, worker: Worker, delivery_id: str) -> dict:
        """本人の依頼書のPDFを開く期限付きのリンク。⑤のトークの「依頼書を開く」と同じ条件・同じ記録（DEC-064）。"""
        self.require(FEATURE_WEB_HOME, FEATURE_WEB_ORDERS)
        delivery = self.session.get(OrderRequestDelivery, delivery_id or "")
        if delivery is None or delivery.worker_id != worker.id:
            raise PortalError(404, "この依頼書は開けません。", "not_found")
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if version is not None:
            ws.lock_series(self.session, ws.ensure_series(self.session, version))
            delivery = self.session.get(OrderRequestDelivery, delivery.id)
        if version is None or not version.pdf_object_key or not ws.pdf_viewable(self.session, delivery):
            raise PortalError(404, "この依頼書は開けません。運営へご確認ください。", "not_viewable")
        settings = line_settings()
        if not settings.public_api_base.startswith("https://"):
            raise PortalError(503, "いまは依頼書を開けません。運営へご確認ください。", "unavailable")
        now = ws.now_utc()
        token = OrderRequestFileToken(
            id=generate_ulid(),
            delivery_id=delivery.id,
            token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(days=PDF_TOKEN_DAYS),
            created_at=now,
        )
        self.session.add(token)
        self.session.flush()
        AuditService(self.session).log(
            "order_request_file_token_reissued",
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor="line-worker-web",
            after_value={"expires_at": token.expires_at.isoformat()},
        )
        return {
            "url": f"{settings.public_api_base.rstrip('/')}/api/line/order-request-files/{token.token}",
            "expires_days": PDF_TOKEN_DAYS,
        }
