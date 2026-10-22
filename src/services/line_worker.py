"""稼働者向けLIFF画面の共通部分（統合計画 ①）と、日付を選んでの受諾（A1+ §3）。

- 本人確認：LINEのIDトークンを検証（登録の受付判定とは分離）し、有効な連携と稼働者を確かめて短いセッションを出す。
- 各API呼び出しで、セッション・連携・稼働者・機能の公開状態を確かめ直す。
- 送信は冪等キーで二重処理を防ぐ。
"""
from __future__ import annotations

import hashlib
import json
import os
import logging
import secrets
import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.line_registration_entry import registration_login_channel_id
from src.models.base import generate_ulid
from src.models.line_daily import (
    FEATURE_PICK_DATES,
    LineWorkerSession,
    LineWorkerSubmitKey,
    OrderRequestSeries,
)
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.master import Worker
from src.models.order_request import (
    ACK_ACKED,
    ACK_DECLINE_PENDING,
    ACK_DECLINED,
    ACK_UNACKED,
    KIND_TEST,
    STATUS_CANCELLED,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services import line_id_token
from src.services.line_messaging import LineNotConfigured, build_line_client
from src.services import worker_schedule as ws

logger = logging.getLogger(__name__)
from src.services.audit import AuditService
from src.services.line_daily import enabled_actions

SESSION_TTL = timedelta(minutes=30)
MAX_KEY_LENGTH = 128


class LineWorkerError(Exception):
    def __init__(self, status_code: int, message: str, code: str = "error"):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code


def worker_liff_id() -> str:
    return os.getenv("LINE_WORKER_LIFF_ID", "").strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value):
    from datetime import timezone

    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class LineWorkerService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    # ---- 本人確認 --------------------------------------------------------------
    def issue_session(self, id_token: str) -> dict:
        channel_id = registration_login_channel_id()
        if not worker_liff_id() or not channel_id:
            raise LineWorkerError(503, "この画面は準備中です。運営へお問い合わせください。", "not_configured")
        try:
            subject = line_id_token.verify_id_token(id_token, channel_id)
        except line_id_token.LineIdTokenError as exc:
            raise LineWorkerError(401, exc.message, "auth") from None
        worker = self._linked_worker(subject)
        token = secrets.token_urlsafe(32)
        now = ws.now_utc()
        self.session.add(
            LineWorkerSession(
                id=generate_ulid(),
                token_hash=_hash(token),
                line_user_id=subject,
                worker_id=worker.id,
                expires_at=now + SESSION_TTL,
                created_at=now,
            )
        )
        self.session.flush()
        return {"token": token, "expires_at": (now + SESSION_TTL).isoformat(), "worker_name": worker.name}

    def _linked_worker(self, line_user_id: str) -> Worker:
        link = (
            self.session.query(LineWorkerLink)
            .filter(LineWorkerLink.line_user_id == line_user_id, LineWorkerLink.status == LINK_ACTIVE)
            .one_or_none()
        )
        worker = self.session.get(Worker, link.worker_id) if link is not None else None
        if worker is None or worker.deleted_at is not None or not worker.is_active:
            raise LineWorkerError(403, "公式LINEとの連携が確認できません。運営までお問い合わせください。", "not_linked")
        return worker

    def authenticate(self, token: str) -> tuple[LineWorkerSession, Worker]:
        """セッションを確かめ、連携と稼働者の状態を毎回確認し直す（連携解除・無効化で即時に見られなくする）。"""
        if not token or len(token) > 200:
            raise LineWorkerError(401, "本人確認が必要です。LINEから開き直してください。", "auth")
        row = self.session.query(LineWorkerSession).filter(LineWorkerSession.token_hash == _hash(token)).one_or_none()
        if row is None or _as_utc(row.expires_at) <= ws.now_utc():
            raise LineWorkerError(401, "画面の有効期限が切れました。LINEから開き直してください。", "auth")
        worker = self._linked_worker(row.line_user_id)
        if worker.id != row.worker_id:
            raise LineWorkerError(401, "連携が変わったため、LINEから開き直してください。", "auth")
        return row, worker

    @staticmethod
    def require_feature(session: Session, feature: str) -> None:
        if feature not in enabled_actions(session):
            raise LineWorkerError(403, "この機能はまだご利用いただけません。", "feature_off")

    # ---- 日付を選んでの受諾 ------------------------------------------------------------
    def pick_view(self, worker: Worker, delivery_id: str) -> dict:
        self.require_feature(self.session, FEATURE_PICK_DATES)
        delivery = self.session.get(OrderRequestDelivery, delivery_id or "")
        if delivery is None or delivery.worker_id != worker.id:
            raise LineWorkerError(404, "この依頼書は開けません。", "not_found")
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        document = self.session.get(OrderRequestDocument, version.document_id)
        series = self.session.get(OrderRequestSeries, version.series_id) if version.series_id else None
        display = ws.version_display(version)
        work_days = ws.version_work_days(version)
        all_dates = sorted({d["work_date"] for d in work_days})
        state = self._pick_state(delivery, version, series)
        current = ws.current_state(self.session, delivery) if delivery.ack_status == ACK_ACKED else None
        schedule = (ws._version_sections(version) or {}).get("schedule") or {}
        holidays = sorted({day for group in schedule.get("work_groups", []) for day in (group.get("excluded_dates") or [])})
        return {
            "delivery_id": delivery.id,
            "document_number": document.document_number,
            "version_no": version.version_no,
            "is_test": document.kind == KIND_TEST,
            "project_name": display["project_name"],
            "site_name": display["site_name"],
            "meeting_place": display["meeting_place"],
            "state": state,
            "allow_partial_accept": bool(version.allow_partial_accept),
            "offered_dates": [d for d in (delivery.offered_dates or []) if d in set(all_dates) and d not in set(holidays)],
            "period": {"from": all_dates[0], "to": all_dates[-1]} if all_dates else None,
            "work_days": [
                {"date": d["work_date"], "start_time": d["start_time"], "end_time": d["end_time"], "end_next_day": d["end_next_day"]}
                for d in work_days
            ],
            "holidays": holidays,
            "accepted_dates": list(current.dates) if current is not None else [],
            "today": ws.today_jst().isoformat(),
        }

    @staticmethod
    def _pick_state(delivery: OrderRequestDelivery, version: OrderRequestVersion, series: OrderRequestSeries | None) -> str:
        if version.status == STATUS_CANCELLED or version.dispatch_stopped or delivery.view_revoked:
            return "closed"
        if series is not None and series.answerable_version_id != version.id:
            return "superseded"
        if delivery.ack_status == ACK_ACKED:
            return "accepted"
        if delivery.ack_status == ACK_DECLINED:
            return "declined"
        if delivery.ack_status in (ACK_UNACKED, ACK_DECLINE_PENDING):
            return "open" if version.allow_partial_accept and delivery.offered_dates else "not_allowed"
        return "closed"

    def accept_dates(self, session_row: LineWorkerSession, worker: Worker, delivery_id: str, dates: list, idempotency_key: str) -> dict:
        from src.services.line_order import LineOrderService

        self.require_feature(self.session, FEATURE_PICK_DATES)
        key = (idempotency_key or "").strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            raise LineWorkerError(400, "送信をやり直してください。", "key")
        if not isinstance(dates, list) or len(dates) > 400 or not all(isinstance(d, str) for d in dates):
            raise LineWorkerError(400, "日付を選び直してください。", "invalid")
        chosen = sorted(set(dates))
        content = _hash(json.dumps({"action": "pick_dates", "delivery": delivery_id, "dates": chosen}, ensure_ascii=False))
        existing = self._submit_key(worker.id, key)
        if existing is not None:
            return self._replay(existing, content)
        outcome, message = LineOrderService(self.session).accept_with_dates(delivery_id, session_row.line_user_id, chosen)
        delivery = self.session.get(OrderRequestDelivery, delivery_id)
        accepted = []
        if delivery is not None and delivery.ack_status == ACK_ACKED:
            state = ws.current_state(self.session, delivery)
            accepted = list(state.dates) if state is not None else []
        result = {"outcome": outcome, "message": message or "", "accepted_dates": accepted}
        if outcome == "acked" and delivery is not None:
            # 確定（commit）後にトークへ受付の通知を送る。再送（同じキー）では送らない
            self.pending_notice = {
                "to": session_row.line_user_id,
                "text": self._accept_notice_text(delivery, accepted),
                "retry_key": str(uuid.uuid5(uuid.NAMESPACE_URL, f"vanzai-pick:{worker.id}:{key}")),
            }
        try:
            with self.session.begin_nested():
                self.session.add(
                    LineWorkerSubmitKey(
                        id=generate_ulid(),
                        worker_id=worker.id,
                        idempotency_key=key,
                        action="pick_dates",
                        target_id=(delivery_id or "")[:26],
                        content_hash=content,
                        result=result,
                        created_at=ws.now_utc(),
                    )
                )
                self.session.flush()
        except IntegrityError:
            # 同じキーの同時送信。先に保存された結果を返す（受諾は系列のロックで1回だけ記録される）
            existing = self._submit_key(worker.id, key)
            if existing is not None:
                return self._replay(existing, content)
            raise
        return result

    def _accept_notice_text(self, delivery: OrderRequestDelivery, dates: list[str]) -> str:
        from src.services.line_order import format_date_set

        version = self.session.get(OrderRequestVersion, delivery.version_id)
        document = self.session.get(OrderRequestDocument, version.document_id)
        display = ws.version_display(version)
        lines = ["【受付】日付を選んでの受諾を受け付けました。"]
        if document.kind == KIND_TEST:
            lines.append("（テストの依頼書です）")
        lines.append(f"依頼書：{display['project_name'] or '案件'}（{document.document_number} 版{version.version_no}）")
        lines.append(f"あなたの稼働日：{format_date_set(dates)}（{len(dates)}日）")
        lines.append("予定はメニューの「スケジュール確認」でも確認できます。")
        return "\n".join(lines)

    def send_pending_notice(self) -> None:
        """受諾の確定後に呼ぶ。送信に失敗しても受諾は取り消さない（画面には結果を表示済み）。"""
        notice = getattr(self, "pending_notice", None)
        self.pending_notice = None
        if not notice:
            return
        try:
            result = build_line_client().push_receipt(notice["to"], notice["text"], notice["retry_key"])
            if result.status not in (200, 409):
                logger.warning("pick accept notice failed: status=%s message=%s", result.status, result.message)
        except LineNotConfigured:
            logger.warning("pick accept notice skipped: LINE not configured")
        except Exception:  # noqa: BLE001 - 通知の失敗で画面の応答を壊さない
            logger.exception("pick accept notice failed")

    def _submit_key(self, worker_id: str, key: str) -> LineWorkerSubmitKey | None:
        return (
            self.session.query(LineWorkerSubmitKey)
            .filter(LineWorkerSubmitKey.worker_id == worker_id, LineWorkerSubmitKey.idempotency_key == key)
            .one_or_none()
        )

    @staticmethod
    def _replay(row: LineWorkerSubmitKey, content: str) -> dict:
        if row.content_hash != content:
            raise LineWorkerError(409, "前回と違う内容です。画面を開き直してから送ってください。", "key_conflict")
        return dict(row.result)
