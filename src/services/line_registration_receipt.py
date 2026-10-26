"""申請commit後の受付通知。保存済みの宛先・本文・リトライキーを維持する。"""
from datetime import datetime, timedelta, timezone
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from src.models.line_registration import LineRegistrationContext, LineRegistrationReceipt
from src.models.operator_registration import OperatorRegistrationDetail
from src.models.master import RegistrationRequest
from src.services.audit import AuditService
from src.services.line_messaging import build_line_client, LineNotConfigured

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
RETRY_WINDOW = timedelta(hours=23)  # LINE側の24時間保持期間より短くする。


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class LineRegistrationReceiptService:
    def __init__(self, session, client=None):
        self.session = session
        self.client = client or build_line_client()

    def send(self, request_id: str, *, now=None):
        moment = now or datetime.now(timezone.utc)
        receipt = self.session.scalar(
            select(LineRegistrationReceipt)
            .where(LineRegistrationReceipt.request_id == request_id)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if receipt is None or receipt.status != "pending" or _aware(receipt.next_attempt_at) > moment:
            return
        if receipt.attempt_count >= MAX_ATTEMPTS or moment >= _aware(receipt.created_at) + RETRY_WINDOW:
            receipt.status = "failed"
            self._audit(receipt, "expired")
            return
        context = self.session.scalar(select(LineRegistrationContext).where(LineRegistrationContext.request_id == request_id))
        recipient = context.line_user_id if context else None
        if context is None:
            request = self.session.get(RegistrationRequest, request_id)
            operator = self.session.get(OperatorRegistrationDetail, request_id)
            if request and request.request_type == "operator_staff" and request.source_type == "line_operator" and request.deleted_at is None and operator and operator.revoked_at is None:
                recipient = operator.line_user_id
        if not recipient:
            receipt.status = "failed"
            self._audit(receipt, "missing_context")
            return
        receipt.attempt_count += 1
        try:
            result = self.client.push_receipt(recipient, receipt.message_text, receipt.retry_key)
            receipt.last_http_status = result.status
            accepted = 200 <= result.status < 300 or (result.status == 409 and bool(result.accepted_request_id))
            retryable = result.status == 0 or result.status >= 500
        except LineNotConfigured:
            accepted, retryable = False, True
            receipt.last_http_status = 0
        except Exception:
            # 本文・宛先・トークンや外部エラー本文をログへ出さない。
            accepted, retryable = False, True
            receipt.last_http_status = 0
        if accepted:
            receipt.status = "sent"
            receipt.sent_at = moment
            self._audit(receipt, "accepted")
        else:
            receipt.status = "pending" if retryable and receipt.attempt_count < MAX_ATTEMPTS else "failed"
            receipt.next_attempt_at = moment + timedelta(seconds=60 * 2 ** (receipt.attempt_count - 1))
            self._audit(receipt, "retry_scheduled" if receipt.status == "pending" else "failed")

    def _audit(self, receipt, category):
        AuditService(self.session).log(
            "line_registration_receipt_sent" if receipt.status == "sent" else "line_registration_receipt_failed",
            target_type="registration_request", target_id=receipt.request_id,
            actor="line-registration-receipt", reason=category,
            after_value={"status": receipt.status, "attempt_count": receipt.attempt_count, "http_status": receipt.last_http_status},
        )


def dispatch_registration_receipt(request_id: str, session_factory):
    try:
        with session_factory() as session:
            LineRegistrationReceiptService(session).send(request_id)
            session.commit()
    except Exception:
        # 通知の失敗で保存済み申請のAPI応答を失敗扱いにしない。永続キューから再試行する。
        logger.warning("LINE receipt dispatch could not be committed")


def dispatch_due_registration_receipts(session_factory):
    try:
        with session_factory() as session:
            request_ids = list(session.scalars(
                select(LineRegistrationReceipt.request_id)
                .where(LineRegistrationReceipt.status == "pending", LineRegistrationReceipt.next_attempt_at <= datetime.now(timezone.utc))
                .order_by(LineRegistrationReceipt.next_attempt_at).limit(20)
            ))
        for request_id in request_ids:
            dispatch_registration_receipt(request_id, session_factory)
    except Exception:
        logger.warning("LINE receipt queue could not be read")


def start_registration_receipt_scheduler():
    from src.api.deps import SessionLocal

    scheduler = BackgroundScheduler()
    scheduler.add_job(dispatch_due_registration_receipts, "interval", seconds=60,
                      args=[SessionLocal], id="line_registration_receipts", max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler
