"""公式LINEの日次操作（A1）：①起床報告、⑤受託済みの発注依頼書、⑥スケジュール確認。

詳細設計 §7、DEC-064。返信内容を作るだけで、送信は呼び出し側がcommitの後に行う。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.line_daily import (
    ENTRY_ACTIVE,
    ENTRY_CHANGING,
    LineActionToken,
    LineRichMenuRelease,
    OrderRequestSeries,
    WakeReport,
    WorkerScheduleEntry,
)
from src.models.line_order import LINK_ACTIVE, LineWorkerLink, OrderRequestFileToken
from src.models.master import Worker
from src.models.order_request import OrderRequestDelivery, OrderRequestDocument, OrderRequestVersion
from src.services import worker_schedule as ws
from src.services.audit import AuditService
from src.services.line_messaging import line_settings

ACTION_TOKEN_MINUTES = 30
PDF_TOKEN_DAYS = 7
PAGE_SIZE = 10
LATE_RECEIVE_MINUTES = 30
WEEKDAYS = "月火水木金土日"

NOT_LINKED = "連携が確認できません。運営までお問い合わせください。"
NOT_AVAILABLE = "この機能はまだご利用いただけません。"
TOKEN_EXPIRED = "表示の期限が切れました。もう一度メニューから押してください。"
CHANGING_NOTE = "内容が変更されています。新しい依頼書を確認してください。"

# 受信する data → 有効判定に使う親の機能（D01）
PARENT_ACTION = {
    "wk_wake": "wk_wake",
    "wk_orders": "wk_orders",
    "wk_schedule": "wk_schedule",
    "wk_next": "wk_schedule",
    "wk_open": "wk_orders",
    "wk_checkin": "wk_checkin",
    "wk_checkout": "wk_checkout",
    "wk_sales": "wk_sales",
}
TOKEN_ACTION = {"wk_next": "schedule_next", "wk_open": "open_order"}


def _text(message: str) -> list[dict]:
    return [{"type": "text", "text": message[:5000]}]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _day_label(day: date) -> str:
    return f"{day.month}/{day.day}（{WEEKDAYS[day.weekday()]}）"


def _time_label(entry: WorkerScheduleEntry) -> str:
    start = entry.start_time.strftime("%H:%M") if entry.start_time else ""
    end = entry.end_time.strftime("%H:%M") if entry.end_time else ""
    if not start and not end:
        return ""
    return f"{start}〜{'翌' if entry.end_next_day else ''}{end}"


def enabled_actions(session: Session) -> set[str]:
    latest = session.query(LineRichMenuRelease).order_by(LineRichMenuRelease.applied_at.desc()).first()
    return set(latest.enabled_actions or []) if latest is not None else set()


class LineDailyService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    # ---- 入口 ----------------------------------------------------------------
    def handle(self, event: dict, data: str) -> tuple[str, list[dict]]:
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        if source.get("type") != "user":
            return "ignored_non_user", []
        kind, _, token = data.partition(":")
        parent = PARENT_ACTION.get(kind)
        if parent is None:
            return "ignored", []
        if parent not in enabled_actions(self.session):
            return "not_available", _text(NOT_AVAILABLE)
        worker = self._worker(source.get("userId"))
        if worker is None:
            return "not_linked", _text(NOT_LINKED)
        if kind == "wk_wake":
            return self.wake(worker, event)
        if kind == "wk_schedule":
            return self.schedule(worker)
        if kind == "wk_orders":
            return self.orders(worker)
        if kind in TOKEN_ACTION:
            row = self._token(token, worker.id, TOKEN_ACTION[kind])
            if row is None:
                return "token_invalid", _text(TOKEN_EXPIRED)
            if kind == "wk_next":
                return self.schedule(worker, payload=row.payload)
            return self.open_order(worker, row.payload)
        return "not_available", _text(NOT_AVAILABLE)

    def _worker(self, line_user_id: str | None) -> Worker | None:
        if not isinstance(line_user_id, str) or not line_user_id:
            return None
        link = (
            self.session.query(LineWorkerLink)
            .filter(LineWorkerLink.line_user_id == line_user_id, LineWorkerLink.status == LINK_ACTIVE)
            .one_or_none()
        )
        if link is None:
            return None
        worker = self.session.get(Worker, link.worker_id)
        if worker is None or worker.deleted_at is not None or not worker.is_active:
            return None
        return worker

    # ---- トークン --------------------------------------------------------------
    def _issue_token(self, worker_id: str, action: str, payload: dict) -> str:
        token = secrets.token_urlsafe(24)
        now = ws.now_utc()
        self.session.add(
            LineActionToken(
                id=generate_ulid(),
                token_hash=_hash(token),
                worker_id=worker_id,
                action=action,
                payload=payload,
                expires_at=now + timedelta(minutes=ACTION_TOKEN_MINUTES),
                created_at=now,
            )
        )
        self.session.flush()
        return token

    def _token(self, token: str, worker_id: str, action: str) -> LineActionToken | None:
        if not token or len(token) > 80:
            return None
        row = self.session.query(LineActionToken).filter(LineActionToken.token_hash == _hash(token)).one_or_none()
        if row is None or row.worker_id != worker_id or row.action != action:
            return None
        if _as_utc(row.expires_at) <= ws.now_utc():
            return None
        return row

    # ---- 予定の読み出し ------------------------------------------------------------
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

    @staticmethod
    def _entry_lines(entry: WorkerScheduleEntry) -> list[str]:
        title = " ".join(filter(None, [_time_label(entry), entry.project_name]))
        lines = [("【テスト】" if entry.is_test else "") + (title or "（案件名なし）")]
        if entry.site_name:
            lines.append(f"稼働場所：{entry.site_name}")
        if entry.meeting_place:
            lines.append(f"集合場所：{entry.meeting_place}")
        if entry.status == ENTRY_CHANGING:
            lines.append(CHANGING_NOTE)
        return lines

    # ---- ①起床報告 ---------------------------------------------------------------
    def wake(self, worker: Worker, event: dict) -> tuple[str, list[dict]]:
        received = ws.now_utc()
        stamp = event.get("timestamp")
        occurred = (
            datetime.fromtimestamp(stamp / 1000, tz=timezone.utc)
            if isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            else received
        )
        report_date = occurred.astimezone(ws.JST).date()
        entries = self._entries(worker.id, report_date, report_date)
        is_test = bool(entries) and all(e.is_test for e in entries)
        existing = (
            self.session.query(WakeReport)
            .filter(WakeReport.worker_id == worker.id, WakeReport.report_date == report_date, WakeReport.is_test == is_test)
            .one_or_none()
        )
        if existing is not None:
            at = _as_utc(existing.event_occurred_at).astimezone(ws.JST).strftime("%H:%M")
            return "wake_already", _text(f"報告済みです（{at}）。\n\n" + self._today_text(entries))
        event_id = event.get("webhookEventId") if isinstance(event.get("webhookEventId"), str) else ""
        try:
            with self.session.begin_nested():
                self.session.add(
                    WakeReport(
                        id=generate_ulid(),
                        worker_id=worker.id,
                        report_date=report_date,
                        is_test=is_test,
                        event_occurred_at=occurred,
                        received_at=received,
                        late_received=(received - occurred) >= timedelta(minutes=LATE_RECEIVE_MINUTES),
                        line_event_id=event_id[:64],
                        created_at=received,
                    )
                )
                self.session.flush()
        except IntegrityError:
            return "wake_already", _text("報告済みです。\n\n" + self._today_text(entries))
        self.audit.log(
            "wake_reported",
            target_type="worker",
            target_id=worker.id,
            actor="line-webhook",
            after_value={"report_date": report_date.isoformat(), "is_test": is_test, "late_received": (received - occurred) >= timedelta(minutes=LATE_RECEIVE_MINUTES)},
        )
        greeting = f"{worker.name}さん、おはようございます。本日もよろしくお願いします。"
        return "wake_reported", _text(f"{greeting}\n\n{self._today_text(entries)}\n\nよろしくお願いします。")

    def _today_text(self, entries: list[WorkerScheduleEntry]) -> str:
        if not entries:
            return "本日の予定は登録されていません。運営へご確認ください。"
        blocks = ["■本日の予定"]
        for entry in entries:
            blocks.append("\n".join(self._entry_lines(entry)))
        return "\n\n".join(blocks)

    # ---- ⑥スケジュール確認 ----------------------------------------------------------
    def schedule(self, worker: Worker, payload: dict | None = None) -> tuple[str, list[dict]]:
        if payload is None:
            start = ws.today_jst()
            end = start + timedelta(days=6)
            after = None
        else:
            start = date.fromisoformat(payload["start"])
            end = date.fromisoformat(payload["end"])
            after = payload.get("after")
        rows = self._entries(worker.id, start, end)
        if after:
            position = (after["work_date"], after["start_time"] or "", after["id"])
            rows = [
                r for r in rows
                if (r.work_date.isoformat(), r.start_time.strftime("%H:%M") if r.start_time else "", r.id) > position
            ]
        if not rows:
            message = "この7日間の予定はありません。" if payload is None else "これ以上の予定はありません。"
            return "schedule_empty", _text(message)
        page, rest = rows[:PAGE_SIZE], rows[PAGE_SIZE:]
        bubbles = [self._entry_bubble(entry) for entry in page]
        if rest:
            last = page[-1]
            token = self._issue_token(
                worker.id,
                "schedule_next",
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "after": {
                        "work_date": last.work_date.isoformat(),
                        "start_time": last.start_time.strftime("%H:%M") if last.start_time else "",
                        "id": last.id,
                    },
                },
            )
            bubbles.append(self._button_bubble(f"ほか{len(rest)}件", "続きを見る", f"wk_next:{token}"))
        return "schedule_shown", [
            {"type": "flex", "altText": f"{_day_label(start)}からの予定", "contents": {"type": "carousel", "contents": bubbles}}
        ]

    def _entry_bubble(self, entry: WorkerScheduleEntry) -> dict:
        lines = self._entry_lines(entry)
        body = [{"type": "text", "text": _day_label(entry.work_date), "weight": "bold", "size": "md"}]
        body += [{"type": "text", "text": line[:200], "wrap": True, "size": "sm"} for line in lines]
        return {"type": "bubble", "size": "kilo", "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body}}

    @staticmethod
    def _button_bubble(text: str, label: str, data: str) -> dict:
        return {
            "type": "bubble",
            "size": "kilo",
            "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": text, "wrap": True}]},
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [{"type": "button", "style": "primary", "height": "sm", "action": {"type": "postback", "label": label, "data": data, "displayText": label}}],
            },
        }

    # ---- ⑤受託済みの発注依頼書 --------------------------------------------------------
    def orders(self, worker: Worker) -> tuple[str, list[dict]]:
        today = ws.today_jst()
        rows = (
            ws.visible_schedule_entries(self.session)
            .filter(
                WorkerScheduleEntry.worker_id == worker.id,
                WorkerScheduleEntry.work_date >= today,
                or_(WorkerScheduleEntry.status == ENTRY_ACTIVE, WorkerScheduleEntry.status == ENTRY_CHANGING),
            )
            .order_by(WorkerScheduleEntry.work_date)
            .all()
        )
        by_delivery: dict[str, list[WorkerScheduleEntry]] = {}
        for row in rows:
            by_delivery.setdefault(row.delivery_id, []).append(row)
        if not by_delivery:
            return "orders_empty", _text("今後の予定がある受託済みの依頼書はありません。")
        bubbles = []
        for delivery_id, entries in list(by_delivery.items())[:PAGE_SIZE]:
            delivery = self.session.get(OrderRequestDelivery, delivery_id)
            version = self.session.get(OrderRequestVersion, delivery.version_id)
            document = self.session.get(OrderRequestDocument, version.document_id)
            first, last = entries[0].work_date, entries[-1].work_date
            period = _day_label(first) if first == last else f"{_day_label(first)}〜{_day_label(last)}"
            lines = [
                ("【テスト】" if entries[0].is_test else "") + (entries[0].project_name or document.document_number),
                f"稼働期間：{period}",
            ]
            if delivery.acked_at:
                lines.append(f"受諾：{_as_utc(delivery.acked_at).astimezone(ws.JST).strftime('%m/%d %H:%M')}")
            buttons = [self._open_button(worker.id, delivery.id, "依頼書を開く")]
            if entries[0].status == ENTRY_CHANGING:
                lines.append("新しい依頼書の確認待ち")
                series = self.session.get(OrderRequestSeries, version.series_id) if version.series_id else None
                newer = ws.delivery_in_version(self.session, series.answerable_version_id, worker.id) if series else None
                if newer is not None:
                    buttons.append(self._open_button(worker.id, newer.id, "新しい依頼書を開く"))
            bubbles.append({
                "type": "bubble",
                "size": "kilo",
                "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [{"type": "text", "text": line[:200], "wrap": True, "size": "sm"} for line in lines]},
                "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
            })
        return "orders_shown", [{"type": "flex", "altText": "受託済みの発注依頼書", "contents": {"type": "carousel", "contents": bubbles}}]

    def _open_button(self, worker_id: str, delivery_id: str, label: str) -> dict:
        token = self._issue_token(worker_id, "open_order", {"delivery_id": delivery_id})
        return {"type": "button", "style": "primary", "height": "sm", "action": {"type": "postback", "label": label, "data": f"wk_open:{token}", "displayText": label}}

    def open_order(self, worker: Worker, payload: dict) -> tuple[str, list[dict]]:
        delivery = self.session.get(OrderRequestDelivery, payload.get("delivery_id") or "")
        if delivery is None or delivery.worker_id != worker.id:
            return "open_rejected", _text("この依頼書は開けません。")
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if version is not None:
            ws.lock_series(self.session, ws.ensure_series(self.session, version))
            delivery = self.session.get(OrderRequestDelivery, delivery.id)
        if not ws.pdf_viewable(self.session, delivery) or version is None or not version.pdf_object_key:
            return "open_rejected", _text("この依頼書は開けません。運営へご確認ください。")
        settings = line_settings()
        if not settings.public_api_base.startswith("https://"):
            return "open_unavailable", _text("いまは依頼書を開けません。運営へご確認ください。")
        now = ws.now_utc()
        file_token = OrderRequestFileToken(
            id=generate_ulid(),
            delivery_id=delivery.id,
            token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(days=PDF_TOKEN_DAYS),
            created_at=now,
        )
        self.session.add(file_token)
        self.session.flush()
        self.audit.log(
            "order_request_file_token_reissued",
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor="line-webhook",
            after_value={"expires_at": file_token.expires_at.isoformat()},
        )
        url = f"{settings.public_api_base.rstrip('/')}/api/line/order-request-files/{file_token.token}"
        return "open_issued", _text(f"依頼書（PDF）はこちらです。リンクの期限は{PDF_TOKEN_DAYS}日です。\n{url}")
