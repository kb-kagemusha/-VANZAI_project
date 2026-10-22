"""発注依頼書の公式LINE紐付け、1人ずつの送信、受諾と辞退。

正式・テストの区分にかかわらず公式LINEで送る（DEC-067）。返事は本人の受諾か、辞退理由の送信だけを記録する。
PDFを開いたことや電話連絡では返事にしない。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.line_registration_entry import is_registration_keyword, registration_button_messages
from src.domain.line_registration_locks import lock_link_rows, lock_worker_row
from src.models.base import generate_ulid
from src.models.enums import AuditAction
from src.models.line_order import (
    ATTEMPT_ACCEPTED,
    ATTEMPT_FAILED,
    ATTEMPT_UNKNOWN,
    LINK_ACTIVE,
    LINK_REVOKED,
    LineLinkCode,
    LineWebhookEvent,
    LineWorkerLink,
    OrderRequestFileToken,
    OrderRequestSendAttempt,
)
from src.models.master import User, Worker
from src.models.order_request import (
    ACK_ACKED,
    ACK_DECLINE_PENDING,
    ACK_DECLINED,
    ACK_UNACKED,
    KIND_TEST,
    SEND_ACCEPTED,
    SEND_FAILED,
    SEND_PROCESSING,
    SEND_UNKNOWN,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    OrderRequestDelivery,
    OrderRequestDocument,
    OrderRequestVersion,
)
from src.services.audit import AuditService
from src.services.document_storage import DocumentStorage
from src.services.line_messaging import (
    LineCallResult,
    LineMessagingClient,
    LineNotConfigured,
    build_line_client,
    line_settings,
)
from src.services.order_request_format import parse_sections
from src.services.order_request_pdf import (
    TEST_BANNER,
    order_request_pdf_filename,
    project_name_from_document,
)
from src.services.order_request_service import OrderRequestError
from src.services import worker_schedule as ws

LINK_CODE_MINUTES = 30
FILE_TOKEN_DAYS = 7
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8

PURPOSE_TEXT = (
    "発注依頼書を公式LINEで送るため、稼働者と本人のLINEを紐付けます。"
)
UNLINK_TEXT = "解除は管理画面から行います。解除後は、その稼働者への公式LINE送信を止めます。"
LINK_INSTRUCTION = (
    "友だち追加した公式LINEへ、このコードだけを送ってください。"
    "コードの有効期限は30分です。他人のLINEから送らないでください。"
)
ACCEPT_LABEL = "依頼の案件、受諾します"
DECLINE_LABEL = "今回は辞退します"
ACCEPT_ALL_LABEL = "全日程で受諾します"
PICK_DATES_LABEL = "日付を選んで受諾する"
ACCEPT_REPLY = "受諾ありがとうございます。よろしくお願い致します"
SUPERSEDED_REPLY = "新しい依頼書が届いています。そちらで回答してください。"
DECLINE_PROMPT = "辞退理由を簡単にお聞かせください"
DECLINE_RECORDED = "辞退を受け付けました。"
REMINDER_TEXT = "内容を確認して、受領ボタンを押してください"
BUTTON_TEMPLATE_TEXT = "内容を確認して、受諾または辞退を押してください。"
JST = ZoneInfo("Asia/Tokyo")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_link_code(value: str) -> str:
    return "".join((value or "").split()).upper()


def hash_link_code(value: str) -> str:
    return hashlib.sha256(normalize_link_code(value).encode("utf-8")).hexdigest()


def active_line_labels(session: Session, worker_ids: set[str]) -> dict[str, str | None]:
    if not worker_ids:
        return {}
    rows = (
        session.query(LineWorkerLink)
        .filter(
            LineWorkerLink.worker_id.in_(worker_ids),
            LineWorkerLink.status == LINK_ACTIVE,
        )
        .all()
    )
    return {row.worker_id: row.line_display_name for row in rows}


def latest_send_errors(session: Session, delivery_ids: set[str]) -> dict[str, str | None]:
    if not delivery_ids:
        return {}
    rows = (
        session.query(OrderRequestSendAttempt)
        .filter(OrderRequestSendAttempt.delivery_id.in_(delivery_ids))
        .order_by(OrderRequestSendAttempt.created_at.desc())
        .all()
    )
    found: dict[str, str | None] = {}
    for row in rows:
        if row.delivery_id in found:
            continue
        found[row.delivery_id] = row.error_summary
    return found


class LineOrderService:
    def __init__(self, session: Session, client: LineMessagingClient | None = None):
        self.session = session
        self.audit = AuditService(session)
        self.storage = DocumentStorage()
        self.client = client or build_line_client()
        self._outbox: list[tuple[str, str, object]] = []

    def issue_code(self, *, actor: User, worker_id: str) -> tuple[Worker, str, datetime]:
        worker = self._active_worker(worker_id)
        if self._active_link_for_worker(worker.id):
            raise OrderRequestError(409, "すでに紐付け済みです。別のLINEへ変える場合は先に解除してください")
        now = _now()
        pending = (
            self.session.query(LineLinkCode)
            .filter(
                LineLinkCode.worker_id == worker.id,
                LineLinkCode.used_at.is_(None),
                LineLinkCode.expires_at > now,
            )
            .all()
        )
        for row in pending:
            row.expires_at = now
        code = self._new_code()
        expires_at = now + timedelta(minutes=LINK_CODE_MINUTES)
        self.session.add(
            LineLinkCode(
                id=generate_ulid(),
                worker_id=worker.id,
                code_hash=hash_link_code(code),
                expires_at=expires_at,
                created_by_user_id=actor.id,
                created_at=now,
            )
        )
        self.session.flush()
        return worker, code, expires_at

    def list_active_links(self) -> list[tuple[LineWorkerLink, Worker]]:
        rows = (
            self.session.query(LineWorkerLink, Worker)
            .join(Worker, Worker.id == LineWorkerLink.worker_id)
            .filter(LineWorkerLink.status == LINK_ACTIVE)
            .order_by(Worker.name)
            .all()
        )
        return rows

    def refresh_profile(self, *, actor: User, worker_id: str) -> LineWorkerLink:
        self._active_worker(worker_id)
        link = self._active_link_for_worker(worker_id)
        if link is None:
            raise OrderRequestError(404, "有効なLINE紐付けがありません")
        expected_id, expected_subject = link.id, link.line_user_id
        try:
            display_name = self.client.profile_name(expected_subject)
        except Exception:
            display_name = None
        if not display_name:
            raise OrderRequestError(502, "LINE表示名を取得できませんでした。時間をおいて再度更新してください。")
        lock_worker_row(self.session, worker_id)
        lock_link_rows(self.session, line_user_id=expected_subject, worker_id=worker_id)
        self.session.expire_all()
        self._active_worker(worker_id)
        current = self._active_link_for_worker(worker_id)
        if current is None or current.id != expected_id or current.line_user_id != expected_subject:
            raise OrderRequestError(409, "LINEの紐付けが変わったため、表示名を保存しませんでした。最新の一覧を読み込んでください。")
        changed = current.line_display_name != display_name
        current.line_display_name = display_name
        self.audit.log(
            "line_profile_refreshed", target_type="line_worker_link", target_id=current.id,
            actor=actor.username, actor_role=actor.role,
            after_value={"worker_id": worker_id, "profile_obtained": True, "changed": changed},
        )
        self.session.flush()
        return current

    def revoke_link(self, *, actor: User, worker_id: str, reason: str) -> LineWorkerLink:
        cleaned = reason.strip()
        if not cleaned:
            raise OrderRequestError(400, "解除理由を入力してください")
        lock_worker_row(self.session, worker_id)
        lock_link_rows(self.session, worker_id=worker_id)
        link = self._active_link_for_worker(worker_id)
        if link is None:
            raise OrderRequestError(404, "有効な紐付けがありません")
        link.status = LINK_REVOKED
        link.revoked_at = _now()
        link.revoked_by_user_id = actor.id
        link.revoke_reason = cleaned
        self.audit.log(
            AuditAction.ORDER_REQUEST_LINE_UNLINKED,
            target_type="line_worker_link",
            target_id=link.id,
            actor=actor.id,
            actor_role=actor.role,
            reason=cleaned,
            after_value={"worker_id": link.worker_id, "status": LINK_REVOKED},
        )
        self.session.flush()
        return link

    def send_one(self, *, actor: User, delivery: OrderRequestDelivery) -> OrderRequestDelivery:
        settings = line_settings()
        if not settings.configured:
            raise OrderRequestError(
                503,
                "サーバーにLINEのチャネル設定がありません。値はチャットに貼らず、サーバーの環境変数へ設定してください",
            )
        if not settings.public_api_base.startswith("https://"):
            raise OrderRequestError(503, "PDFの公開URLはhttpsである必要があります")
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        document = self.session.get(OrderRequestDocument, version.document_id) if version else None
        if version is None or document is None:
            raise OrderRequestError(404, "送付行が見つかりません")
        series = ws.lock_series(self.session, ws.ensure_series(self.session, version))
        delivery = self.session.get(OrderRequestDelivery, delivery.id)
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if series.answerable_version_id != version.id:
            raise OrderRequestError(409, "新しい版が確定しているため、この版は送れません")
        if delivery.ack_status != ACK_UNACKED:
            raise OrderRequestError(409, "返事がある送付先には再送しません")
        if version.status != STATUS_CONFIRMED or version.dispatch_stopped:
            raise OrderRequestError(409, "確定済みで送付を止めていない版だけ送れます")
        if delivery.view_revoked:
            raise OrderRequestError(409, "閲覧を停止した送付先には送れません")
        if not version.pdf_object_key:
            raise OrderRequestError(409, "PDFが無いため送れません")
        link = self._active_link_for_worker(delivery.worker_id)
        if link is None:
            raise OrderRequestError(409, "この稼働者は公式LINEと紐付いていません")

        now = _now()
        file_token = OrderRequestFileToken(
            id=generate_ulid(),
            delivery_id=delivery.id,
            token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(days=FILE_TOKEN_DAYS),
            created_at=now,
        )
        self.session.add(file_token)
        delivery.send_status = SEND_PROCESSING
        self.session.flush()

        pdf_url = f"{settings.public_api_base.rstrip('/')}/api/line/order-request-files/{file_token.token}"
        messages = _push_messages(
            document_number=document.document_number,
            version_no=version.version_no,
            project_name=_project_name(version.request_conditions),
            work_date_label=version.work_date_label,
            site_name=version.site_name,
            pdf_url=pdf_url,
            delivery_id=delivery.id,
            is_test=document.kind == KIND_TEST,
            offered_dates=delivery.offered_dates,
            off_dates=off_dates_in_period(version, delivery.offered_dates),
            pick_dates_url=self._pick_dates_url(version, delivery),
        )
        try:
            result = self.client.push_messages(link.line_user_id, messages)
        except LineNotConfigured as exc:
            file_token.revoked_at = now
            delivery.send_status = SEND_FAILED
            raise OrderRequestError(503, "サーバーにLINEのチャネル設定がありません") from exc

        attempt = OrderRequestSendAttempt(
            id=generate_ulid(),
            delivery_id=delivery.id,
            result=_attempt_result(result),
            line_request_id=result.request_id,
            error_summary=result.message or None,
            actor_user_id=actor.id,
            created_at=now,
        )
        self.session.add(attempt)
        if result.status == 200:
            delivery.send_status = SEND_ACCEPTED
            action = AuditAction.ORDER_REQUEST_LINE_SENT
        elif result.status == 0:
            delivery.send_status = SEND_UNKNOWN
            action = AuditAction.ORDER_REQUEST_LINE_SEND_FAILED
        else:
            file_token.revoked_at = now
            delivery.send_status = SEND_FAILED
            action = AuditAction.ORDER_REQUEST_LINE_SEND_FAILED
        self.audit.log(
            action,
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor=actor.id,
            actor_role=actor.role,
            after_value={
                "send_status": delivery.send_status,
                "worker_id": delivery.worker_id,
                "line_request_id": result.request_id,
            },
            extra_metadata={"error_summary": result.message or None},
        )
        self.session.flush()
        return delivery

    def read_shared_pdf(self, token: str) -> bytes:
        row = (
            self.session.query(OrderRequestFileToken)
            .filter(OrderRequestFileToken.token == token)
            .one_or_none()
        )
        now = _now()
        if row is None or row.revoked_at is not None or _as_utc(row.expires_at) <= now:
            raise OrderRequestError(404, "PDFのリンクは無効です")
        delivery = self.session.get(OrderRequestDelivery, row.delivery_id)
        version = self.session.get(OrderRequestVersion, delivery.version_id) if delivery else None
        if (
            delivery is None
            or version is None
            or delivery.view_revoked
            or version.status == STATUS_CANCELLED
            or version.dispatch_stopped
            or not version.pdf_object_key
            or not ws.pdf_viewable(self.session, delivery)
        ):
            raise OrderRequestError(404, "PDFのリンクは無効です")
        from src.services.order_request_service import OrderRequestService

        return OrderRequestService(self.session, self.storage).read_pdf(version)

    def shared_pdf_filename(self, token: str) -> str:
        row = (
            self.session.query(OrderRequestFileToken)
            .filter(OrderRequestFileToken.token == token)
            .one_or_none()
        )
        delivery = self.session.get(OrderRequestDelivery, row.delivery_id) if row else None
        version = self.session.get(OrderRequestVersion, delivery.version_id) if delivery else None
        if version is None:
            return order_request_pdf_filename(work_date_label="", project_name="")
        return order_request_pdf_filename(
            work_date_label=version.work_date_label,
            project_name=project_name_from_document(version.request_conditions, version.body),
        )

    def handle_webhook(self, payload: dict) -> bool:
        """イベントごとに「処理済み記録 → 業務処理 → commit → 返信」の順で処理する（詳細設計§6.2）。

        予期しない例外で処理できなかったイベントがあれば True を返す（呼び出し側は500で応答し、LINEの再送を受ける）。
        処理済みのイベントは、イベントIDの記録で必ず飛ばす。
        """
        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list):
            return False
        failed = False
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            self._outbox = []
            try:
                processed = self._handle_event(event, index)
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                if "line_webhook_events" in str(exc.orig).lower() or "event_id" in str(exc.orig).lower():
                    continue  # 同じイベントの同時再送。処理済みとして扱う
                failed = True
                continue
            except Exception:
                self.session.rollback()
                failed = True
                continue
            if processed:
                self._send_outbox()
        return failed

    def _send_outbox(self) -> None:
        for kind, token, payload in self._outbox:
            if not token or not payload:
                continue
            try:
                if kind == "text":
                    self.client.reply_text(token, payload)
                else:
                    self.client.reply_messages(token, payload)
            except Exception:
                continue  # 返信の失敗は業務を巻き戻さない。押し直せば保存済みの結果が返る
        self._outbox = []

    def _handle_event(self, event: dict, index: int) -> bool:
        event_id = event.get("webhookEventId")
        if not isinstance(event_id, str) or not event_id:
            event_id = f"missing-{index}-{hashlib.sha256(repr(sorted(event.items())).encode()).hexdigest()[:16]}"
        if self.session.query(LineWebhookEvent).filter(LineWebhookEvent.event_id == event_id[:64]).one_or_none():
            return False
        event_type = str(event.get("type") or "unknown")[:40]
        record = LineWebhookEvent(
            id=generate_ulid(),
            event_id=event_id[:64],
            event_type=event_type,
            outcome="processing",
            created_at=_now(),
        )
        self.session.add(record)
        self.session.flush()  # 一意制約で同時再送を止める
        outcome = "ignored"
        reply_token = event.get("replyToken") if isinstance(event.get("replyToken"), str) else ""
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        line_user_id = source.get("userId") if isinstance(source.get("userId"), str) else ""

        if event_type == "message":
            message = event.get("message") if isinstance(event.get("message"), dict) else {}
            text = message.get("text") if message.get("type") == "text" and isinstance(message.get("text"), str) else ""
            if text and is_registration_keyword(text):
                outcome = self._handle_registration_keyword(event, reply_token)
            else:
                outcome, reply = self._handle_message(event, line_user_id)
                self._reply(reply_token, reply)
        elif event_type == "postback":
            postback = event.get("postback") if isinstance(event.get("postback"), dict) else {}
            data = postback.get("data") if isinstance(postback.get("data"), str) else ""
            if data.startswith("wk_"):
                from src.services.line_daily import LineDailyService

                outcome, messages = LineDailyService(self.session).handle(event, data)
                self._reply_messages(reply_token, messages)
            else:
                outcome, reply = self._handle_postback(event, line_user_id)
                self._reply(reply_token, reply)
        elif event_type == "unfollow":
            from src.services.operator_staff import OperatorStaffService
            OperatorStaffService(self.session).unfollow(line_user_id)
            outcome = "staff_unfollow"

        record.outcome = outcome[:40]
        self.session.flush()
        return True

    def _handle_message(self, event: dict, line_user_id: str) -> tuple[str, str | None]:
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        if message.get("type") != "text" or not isinstance(message.get("text"), str):
            return "ignored", None
        normalized = normalize_link_code(message["text"])
        if normalized.startswith("OPS-"):
            source = event.get("source") if isinstance(event.get("source"), dict) else {}
            if source.get("type") != "user":
                return "staff_rejected", "運営スタッフ用コードは公式LINEとの個別トークから送ってください。"
            from src.services.operator_staff import OperatorStaffService
            return OperatorStaffService(self.session).consume_code(normalized, line_user_id, self.client)
        if len(normalized) != CODE_LENGTH or any(char not in CODE_ALPHABET for char in normalized):
            return self._take_decline_reason(line_user_id, message["text"])
        if not line_user_id:
            return "rejected", "このコードは使えません。管理画面で新しいコードを発行してください。"
        code = (
            self.session.query(LineLinkCode)
            .filter(
                LineLinkCode.code_hash == hash_link_code(normalized),
                LineLinkCode.used_at.is_(None),
                LineLinkCode.expires_at > _now(),
            )
            .one_or_none()
        )
        if code is None:
            return "rejected", "このコードは使えません。管理画面で新しいコードを発行してください。"
        lock_worker_row(self.session, code.worker_id)
        lock_link_rows(self.session, line_user_id=line_user_id, worker_id=code.worker_id)
        existing_worker = self._active_link_for_worker(code.worker_id)
        existing_line = self._active_link_for_line_user(line_user_id)
        if existing_worker and existing_worker.line_user_id == line_user_id:
            code.used_at = _now()
            return "already", "すでに紐付け済みです。"
        if existing_worker or existing_line:
            return "conflict", "別の紐付けが残っているため、管理担当者に解除を依頼してください。"
        display_name = self.client.profile_name(line_user_id)
        link = LineWorkerLink(
            id=generate_ulid(),
            worker_id=code.worker_id,
            line_user_id=line_user_id,
            line_display_name=display_name,
            status=LINK_ACTIVE,
            linked_at=_now(),
        )
        code.used_at = _now()
        self.session.add(link)
        self.audit.log(
            AuditAction.ORDER_REQUEST_LINE_LINKED,
            target_type="line_worker_link",
            target_id=link.id,
            actor="line-webhook",
            after_value={"worker_id": code.worker_id, "status": LINK_ACTIVE},
        )
        self.session.flush()
        return "linked", "紐付けました。解除後は公式LINEからの送信を止めます。"

    def _handle_postback(self, event: dict, line_user_id: str) -> tuple[str, str | None]:
        postback = event.get("postback") if isinstance(event.get("postback"), dict) else {}
        data = postback.get("data") if isinstance(postback.get("data"), str) else ""
        if data.startswith("or_accept:") or data.startswith("or_ack:"):
            prefix = "or_accept:" if data.startswith("or_accept:") else "or_ack:"
            return self._accept(data.removeprefix(prefix).strip(), line_user_id)
        if data.startswith("or_decline:"):
            return self._begin_decline(data.removeprefix("or_decline:").strip(), line_user_id)
        return "ignored", None

    def _delivery_for_reply(self, delivery_id: str, line_user_id: str) -> tuple[OrderRequestDelivery | None, str | None, str | None]:
        delivery = self.session.get(OrderRequestDelivery, delivery_id)
        if delivery is None or not line_user_id:
            return None, "rejected", "この返事は記録できません。"
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if version is not None:
            series = ws.lock_series(self.session, ws.ensure_series(self.session, version))
            delivery = self.session.get(OrderRequestDelivery, delivery_id)
            if series.answerable_version_id is not None and series.answerable_version_id != delivery.version_id:
                return None, "superseded_version", SUPERSEDED_REPLY
        link = self._active_link_for_worker(delivery.worker_id)
        if link is None or link.line_user_id != line_user_id:
            return None, "rejected", "この依頼の相手として紐付いていないため、返事は記録しません。"
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if (
            version is None
            or delivery.view_revoked
            or version.status == STATUS_CANCELLED
            or version.dispatch_stopped
        ):
            return None, "closed", "この依頼の返事は停止されています。"
        return delivery, None, None

    def _pick_dates_url(self, version: OrderRequestVersion, delivery: OrderRequestDelivery) -> str | None:
        """日付を選んで受諾する画面（LIFF）のURL。許可がない・提示日が2日未満・機能が停止中なら None（A1+ §3）。"""
        from src.models.line_daily import FEATURE_PICK_DATES
        from src.services.line_daily import enabled_actions
        from src.services.line_worker import worker_liff_id

        liff_id = worker_liff_id()
        if (
            not liff_id
            or not getattr(version, "allow_partial_accept", False)
            or delivery.offered_dates is None
            or len(delivery.offered_dates) < 2
            or FEATURE_PICK_DATES not in enabled_actions(self.session)
        ):
            return None
        return f"https://liff.line.me/{liff_id}?m=pick&d={delivery.id}"

    def _accept(self, delivery_id: str, line_user_id: str) -> tuple[str, str | None]:
        delivery, outcome, reply = self._delivery_for_reply(delivery_id, line_user_id)
        if delivery is None:
            return outcome or "rejected", reply
        return self.accept_delivery(delivery, None, actor="line-webhook")

    def accept_with_dates(self, delivery_id: str, line_user_id: str, dates: list[str]) -> tuple[str, str | None]:
        """日付を選んで受諾する（LIFF画面から。A1+ §3.3）。系列のロックの中で、回答受付版・本人・未回答を確かめる。"""
        delivery, outcome, reply = self._delivery_for_reply(delivery_id, line_user_id)
        if delivery is None:
            return outcome or "rejected", reply
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        if not getattr(version, "allow_partial_accept", False):
            return "partial_not_allowed", "この依頼書は日付を選んで受諾できません。全日程で受諾するか、辞退してください。"
        if delivery.offered_dates is None:
            return "partial_not_allowed", "この依頼書は日付を選んで受諾できません。"
        chosen = sorted(set(d for d in dates if isinstance(d, str)))
        if not chosen:
            return "partial_invalid", "参加する日を1日以上選んでください。"
        # 提示日のうち、今の日程で実際に勤務がある日（休業日を除く）だけを選べる
        allowed = set(delivery.offered_dates) & {d["work_date"] for d in ws.version_work_days(version)}
        if not set(chosen) <= allowed:
            return "partial_invalid", "選べない日（休業日など）が含まれています。画面を開き直してください。"
        return self.accept_delivery(delivery, chosen, actor="line-liff")

    def accept_delivery(self, delivery: OrderRequestDelivery, dates: list[str] | None, *, actor: str) -> tuple[str, str | None]:
        """受諾を記録する。dates=None は提示日の全部（全日程）、それ以外は選んだ日（partial_accept）。"""
        if delivery.ack_status == ACK_ACKED:
            return "already", "受諾は記録済みです。"
        if delivery.ack_status == ACK_DECLINED:
            return "already", "辞退は記録済みです。"
        delivery.ack_status = ACK_ACKED
        delivery.acked_at = _now()
        delivery.decline_reason = None
        self.audit.log(
            AuditAction.ORDER_REQUEST_ACKED,
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor=actor,
            after_value={
                "worker_id": delivery.worker_id,
                "ack_status": ACK_ACKED,
                **({"partial_dates": len(dates), "offered_dates": len(delivery.offered_dates or [])} if dates is not None else {}),
            },
        )
        self.session.flush()
        reply = ACCEPT_REPLY
        if delivery.offered_dates is not None:
            # 提示日がNULLの旧送付行は、受諾を記録するだけにする（R3-02）
            version = self.session.get(OrderRequestVersion, delivery.version_id)
            series_id = ws.ensure_series(self.session, version)
            participating = list(delivery.offered_dates) if dates is None else list(dates)
            if delivery.current_participation_state_id is None:
                ws.append_state(
                    self.session, delivery, dates=participating,
                    source="full_accept" if dates is None else ws.SOURCE_PARTIAL_ACCEPT, actor=actor,
                )
            ws.set_application(self.session, series_id=series_id, worker_id=delivery.worker_id, delivery=delivery, ended_reason=None, actor=actor)
            ws.rebuild(self.session, series_id, delivery.worker_id, actor=actor)
            off = format_date_set(off_dates_in_period(version, participating))
            if dates is None:
                # 全日程：期間中の休業日（休業日・個人のお休み）を示す
                reply = f"{ACCEPT_REPLY}\n期間中の休業日：{off or 'なし'}"
            else:
                reply = f"{ACCEPT_REPLY}\n参加する日：{format_date_set(participating)}（{len(participating)}日）\n参加しない日：{off or 'なし'}"
        return "acked", reply

    def _begin_decline(self, delivery_id: str, line_user_id: str) -> tuple[str, str | None]:
        delivery, outcome, reply = self._delivery_for_reply(delivery_id, line_user_id)
        if delivery is None:
            return outcome or "rejected", reply
        if delivery.ack_status == ACK_ACKED:
            return "already", "受諾は記録済みです。"
        if delivery.ack_status == ACK_DECLINED:
            return "already", "辞退は記録済みです。"
        delivery.ack_status = ACK_DECLINE_PENDING
        self.session.flush()
        return "decline_pending", DECLINE_PROMPT

    def _take_decline_reason(self, line_user_id: str, text: str) -> tuple[str, str | None]:
        reason = " ".join(text.split())
        if not line_user_id or not reason:
            return "ignored", None
        link = self._active_link_for_line_user(line_user_id)
        if link is None:
            return "ignored", None
        delivery = (
            self.session.query(OrderRequestDelivery)
            .filter(
                OrderRequestDelivery.worker_id == link.worker_id,
                OrderRequestDelivery.ack_status == ACK_DECLINE_PENDING,
                OrderRequestDelivery.view_revoked.is_(False),
            )
            .order_by(OrderRequestDelivery.updated_at.desc())
            .first()
        )
        if delivery is None:
            return "ignored", None
        version = self.session.get(OrderRequestVersion, delivery.version_id)
        series_id = ws.ensure_series(self.session, version) if version is not None else None
        if series_id is not None:
            series = ws.lock_series(self.session, series_id)
            delivery = self.session.get(OrderRequestDelivery, delivery.id)
            if delivery.ack_status != ACK_DECLINE_PENDING:
                return "ignored", None
            if series.answerable_version_id is not None and series.answerable_version_id != delivery.version_id:
                delivery.ack_status = ACK_UNACKED
                return "superseded_version", SUPERSEDED_REPLY
        delivery.ack_status = ACK_DECLINED
        delivery.decline_reason = reason[:500]
        delivery.acked_at = _now()
        if series_id is not None:
            application = ws.get_application(self.session, series_id, delivery.worker_id)
            if application is not None and application.applied_delivery_id:
                ws.set_application(self.session, series_id=series_id, worker_id=delivery.worker_id, delivery=None, ended_reason="declined_new_version", actor="line-webhook")
            ws.rebuild(self.session, series_id, delivery.worker_id, actor="line-webhook")
        self.audit.log(
            AuditAction.ORDER_REQUEST_DECLINED,
            target_type="order_request_delivery",
            target_id=delivery.id,
            actor="line-webhook",
            after_value={
                "worker_id": delivery.worker_id,
                "ack_status": ACK_DECLINED,
                "decline_reason": delivery.decline_reason,
            },
        )
        self.session.flush()
        return "declined", DECLINE_RECORDED

    def send_due_reminders(self, *, now: datetime | None = None) -> int:
        """期限の日時を過ぎて、まだ返事が無い送信先へ案内を1回送る。"""
        moment = now or datetime.now(JST)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=JST)
        rows = (
            self.session.query(OrderRequestDelivery)
            .join(OrderRequestVersion, OrderRequestVersion.id == OrderRequestDelivery.version_id)
            .join(OrderRequestDocument, OrderRequestDocument.id == OrderRequestVersion.document_id)
            .filter(
                OrderRequestDocument.deleted_at.is_(None),
                OrderRequestVersion.follow_up_due_at.is_not(None),
                OrderRequestVersion.status != STATUS_CANCELLED,
                OrderRequestVersion.dispatch_stopped.is_(False),
                OrderRequestDelivery.send_status == SEND_ACCEPTED,
                OrderRequestDelivery.ack_status == ACK_UNACKED,
                OrderRequestDelivery.ack_reminded_at.is_(None),
                OrderRequestDelivery.view_revoked.is_(False),
            )
            .all()
        )
        sent = 0
        for delivery in rows:
            due_at = delivery.version.follow_up_due_at
            if due_at is None:
                continue
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=JST)
            if due_at > moment:
                continue
            link = self._active_link_for_worker(delivery.worker_id)
            if link is None:
                continue
            try:
                result = self.client.push_messages(
                    link.line_user_id,
                    [{"type": "text", "text": REMINDER_TEXT}],
                )
            except LineNotConfigured:
                return sent
            if result.status != 200:
                continue
            delivery.ack_reminded_at = _now()
            self.audit.log(
                AuditAction.ORDER_REQUEST_ACK_REMINDED,
                target_type="order_request_delivery",
                target_id=delivery.id,
                actor="order-ack-reminder",
                after_value={"worker_id": delivery.worker_id},
            )
            sent += 1
        self.session.flush()
        return sent

    def _handle_registration_keyword(self, event: dict, reply_token: str) -> str:
        """「登録」は辞退理由にしない。入口が有効な1対1のときだけ共通ボタンを返す。"""
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        if source.get("type") != "user":
            return "registration_ignored"
        messages = registration_button_messages()
        if not messages:
            return "registration_closed"
        self._reply_messages(reply_token, messages)
        return "registration_button"

    def _reply_messages(self, reply_token: str, messages: list[dict] | None) -> None:
        """返信はcommitの後に送る（詳細設計§6.2）。"""
        if reply_token and messages:
            self._outbox.append(("messages", reply_token, messages))

    def _reply(self, reply_token: str, text: str | None) -> None:
        if reply_token and text:
            self._outbox.append(("text", reply_token, text))

    def _active_worker(self, worker_id: str) -> Worker:
        worker = self.session.get(Worker, worker_id)
        if worker is None or worker.deleted_at is not None or not worker.is_active:
            raise OrderRequestError(404, "稼働者が見つかりません")
        return worker

    def _active_link_for_worker(self, worker_id: str) -> LineWorkerLink | None:
        return (
            self.session.query(LineWorkerLink)
            .filter(LineWorkerLink.worker_id == worker_id, LineWorkerLink.status == LINK_ACTIVE)
            .one_or_none()
        )

    def _active_link_for_line_user(self, line_user_id: str) -> LineWorkerLink | None:
        return (
            self.session.query(LineWorkerLink)
            .filter(LineWorkerLink.line_user_id == line_user_id, LineWorkerLink.status == LINK_ACTIVE)
            .one_or_none()
        )

    def _new_code(self) -> str:
        for _ in range(5):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            exists = (
                self.session.query(LineLinkCode)
                .filter(LineLinkCode.code_hash == hash_link_code(code))
                .one_or_none()
            )
            if exists is None:
                return code
        raise OrderRequestError(503, "紐付けコードを発行できませんでした")


def _attempt_result(result: LineCallResult) -> str:
    if result.status == 200:
        return ATTEMPT_ACCEPTED
    if result.status == 0:
        return ATTEMPT_UNKNOWN
    return ATTEMPT_FAILED


def _project_name(request_conditions: str | None) -> str:
    sections = parse_sections(request_conditions)
    if not sections:
        return ""
    return str(sections.get("project_name") or "")


def _push_messages(
    *,
    document_number: str,
    version_no: int,
    project_name: str,
    work_date_label: str,
    site_name: str,
    pdf_url: str,
    delivery_id: str,
    is_test: bool,
    offered_dates: list[str] | None = None,
    pick_dates_url: str | None = None,
    off_dates: list[str] | None = None,
) -> list[dict]:
    lines = [
        f"発注依頼書 {document_number}（版{version_no}）",
        f"案件名: {project_name}"[:80],
        f"稼働日: {work_date_label}"[:80],
        f"現場: {site_name}"[:80],
        f"PDF: {pdf_url}",
    ]
    if offered_dates:
        # 日程のある依頼書は、全体の範囲を「期間」、その中で稼働しない日（休業日・個人のお休み）を「期間中の休業日」で示す
        lines[2] = f"期間: {work_date_label}"[:80]
        lines.insert(3, f"期間中の休業日: {format_date_set(off_dates) or 'なし'}"[:300])
    if is_test:
        lines = [TEST_BANNER, *lines[:-1], "このメッセージはテスト送信です。", lines[-1]]
    detail = "\n".join(lines)
    return [
        {"type": "text", "text": detail[:5000]},
        {
            "type": "flex",
            "altText": "依頼の案件について、受諾または辞退を押してください。",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": BUTTON_TEMPLATE_TEXT, "wrap": True, "size": "sm"},
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#06C755",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": ACCEPT_ALL_LABEL if pick_dates_url else ACCEPT_LABEL,
                                "data": f"or_accept:{delivery_id}",
                                "displayText": ACCEPT_ALL_LABEL if pick_dates_url else ACCEPT_LABEL,
                            },
                        },
                        *([{
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {"type": "uri", "label": PICK_DATES_LABEL, "uri": pick_dates_url},
                        }] if pick_dates_url else []),
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#C8553D",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": DECLINE_LABEL,
                                "data": f"or_decline:{delivery_id}",
                                "displayText": DECLINE_LABEL,
                                "inputOption": "openKeyboard",
                            },
                        },
                    ],
                },
            },
        },
    ]


def off_dates_in_period(version: OrderRequestVersion, dates: list[str] | None) -> list[str]:
    """日程の期間（最初の日〜最後の日）の中で、dates に入っていない日（休業日・個人のお休み・参加しない日）。"""
    from datetime import date as _date, timedelta as _td

    if not dates:
        return []
    schedule = ws._version_sections(version).get("schedule") or {}
    bounds = [g.get(k) for g in schedule.get("work_groups", []) for k in ("from", "to") if g.get(k)]
    bounds += list(dates)
    first, last = _date.fromisoformat(min(bounds)), _date.fromisoformat(max(bounds))
    chosen = set(dates)
    result, day = [], first
    while day <= last:
        if day.isoformat() not in chosen:
            result.append(day.isoformat())
        day += _td(days=1)
    return result


def format_date_set(dates: list[str] | None) -> str:
    """日付の集合を「11月1日（土）〜11月3日（月）、11月5日（水）」のようにまとめる。None・空なら空文字。"""
    if not dates:
        return ""
    from datetime import date as _date

    days = sorted({_date.fromisoformat(d) for d in dates})
    runs: list[tuple[_date, _date]] = []
    for day in days:
        if runs and (day - runs[-1][1]).days == 1:
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))
    def label(d: _date) -> str:
        # 依頼書の本文・PDF（■休業日）と同じ「10月25日（日）」の表記にそろえる
        return f"{d.month}月{d.day}日（{'月火水木金土日'[d.weekday()]}）"
    return "、".join(label(a) if a == b else f"{label(a)}〜{label(b)}" for a, b in runs)

