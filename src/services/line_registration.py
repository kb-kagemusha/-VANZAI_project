"""LINE登録のセッションと申請送信。入口が無効のときは受け付けない。承認はここではしない。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.line_registration_prefill import worker_form_values
from src.domain.worker_edit_guard import guarded_values
from src.domain.line_registration_entry import registration_entry_ready
from src.domain.line_registration_locks import lock_worker_row
from src.domain.line_registration_input import (
    LineRegistrationInputError,
    NormalizedRegistration,
    canonicalize_line_registration,
    normalize_line_registration,
)
from src.models.base import generate_ulid
from src.models.line_order import LINK_ACTIVE, LineWorkerLink
from src.models.line_registration import (
    LineRegistrationContext,
    LineRegistrationSession,
    LineRegistrationSubmitKey,
    LineRegistrationReceipt,
)
from src.models.master import RegistrationRequest, Worker, WorkerRegistrationRequestDetail
from src.services.audit import AuditService

SESSION_TTL = timedelta(minutes=60)
NOT_SAVED_MESSAGE = "前回の申請を管理者が確認中です。今回入力した内容は申請本文に保存していません"
SAVED_MESSAGE = "受付済みです。管理者が確認します。"
CLOSED_MESSAGE = "LINEからの登録は受け付けていません"
EXISTING_REVIEW_UNAVAILABLE = "LINEからの申請は、専用の審査から承認または却下してください。"


class LineRegistrationClosed(Exception):
    def __init__(self) -> None:
        super().__init__(CLOSED_MESSAGE)
        self.message = CLOSED_MESSAGE


class LineRegistrationAuthError(Exception):
    def __init__(self, message: str = "本人確認ができません。LINEでもう一度開き直してください。") -> None:
        super().__init__(message)
        self.message = message


class _SubmitRetry(Exception):
    pass


class LineRegistrationRejected(Exception):
    def __init__(self, status_code: int, message: str, category: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.category = category
        self.request_id = request_id


@dataclass(frozen=True)
class SubmitResult:
    request_id: str
    status: str
    saved: bool
    message: str


def content_hash(canonical: dict) -> str:
    key = (
        os.getenv("LINE_REGISTRATION_HASH_KEY")
        or os.getenv("WORKER_EDIT_GUARD_KEY")
        or os.getenv("JWT_SECRET_KEY")
        or ""
    )
    if not key:
        raise LineRegistrationAuthError("登録を確認できません。時間をおいてもう一度開いてください。")
    body = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def subject_tag(line_user_id: str) -> str:
    return hashlib.sha256(line_user_id.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LineRegistrationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def issue_session(self, line_user_id: str) -> tuple[str, datetime, bool, str]:
        self._require_open()
        if not line_user_id.strip():
            raise LineRegistrationAuthError()
        link = self._active_link(line_user_id)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + SESSION_TTL
        row = LineRegistrationSession(
            id=generate_ulid(),
            token_hash=_token_hash(token),
            line_user_id=line_user_id,
            line_worker_link_id=link.id if link else None,
            worker_id=link.worker_id if link else None,
            expires_at=expires_at,
        )
        self.session.add(row)
        self.session.flush()
        return token, expires_at, link is not None, subject_tag(line_user_id)

    def form_state(self, token: str) -> dict:
        self._require_open()
        session_row = self._valid_session(token)
        link = self._current_link(session_row)
        if not self._link_matches_session(session_row, link):
            raise LineRegistrationRejected(409, "紐付けが変わったため、画面を開き直してください。", "link_changed")
        pending = self._open_context(session_row.line_user_id)
        worker = self.session.get(Worker, link.worker_id) if link else None
        return {
            "linked": link is not None,
            "pending": pending is not None,
            "message": "管理者が確認中の申請があります。送信しても、確認中の申請本文は変わりません。" if pending else "",
            "registered": worker_form_values(worker) if worker else None,
            "target_tag": subject_tag(link.id + ":" + worker.id) if worker else None,
            "form_ticket": self._form_ticket(session_row, link, worker) if worker else None,
        }

    def _form_ticket(self, session_row, link, worker):
        return content_hash({"purpose": "line_registration_prefill", "subject": session_row.line_user_id,
                             "link": link.id, "worker": worker.id, "values": guarded_values(worker)})

    def submit(self, token: str, idempotency_key: str, payload: dict, sent: set[str], form_ticket: str | None = None) -> SubmitResult:
        self._require_open()
        key = idempotency_key.strip()
        if not key or len(key) > 128:
            raise LineRegistrationRejected(422, "送信の識別子がありません。", "idempotency_key")
        for _attempt in range(3):
            try:
                return self._submit_once(token, key, payload, sent, form_ticket)
            except _SubmitRetry:
                self.session.rollback()
            except IntegrityError as exc:
                self.session.rollback()
                if not _expected_unique(exc) or _attempt == 2:
                    raise
        raise LineRegistrationRejected(503, "申請を確定できませんでした。時間をおいてもう一度送信してください。", "retry_exhausted")

    def delete_expired_sessions(self, *, now: datetime | None = None) -> int:
        moment = now or datetime.now(timezone.utc)
        rows = self.session.scalars(
            select(LineRegistrationSession).where(LineRegistrationSession.expires_at < moment)
        ).all()
        for row in rows:
            self.session.delete(row)
        if rows:
            self.session.flush()
        return len(rows)

    def _submit_once(self, token: str, idempotency_key: str, payload: dict, sent: set[str], form_ticket: str | None = None) -> SubmitResult:
        session_row = self._valid_session(token)
        existing_key = self._find_key(session_row.line_user_id, idempotency_key)
        if existing_key is not None:
            return self._replay_saved_key(existing_key, payload, sent)
        peeked = self._open_context(session_row.line_user_id)
        if peeked is not None:
            self._lock_request(peeked.request_id)
        if session_row.worker_id:
            lock_worker_row(self.session, session_row.worker_id)
        self._lock_active_links(session_row.line_user_id)
        link = self._current_link(session_row)
        if not self._link_matches_session(session_row, link):
            raise LineRegistrationRejected(
                409,
                "紐付けの状態が変わったため、保存しませんでした。登録画面を開き直してください。",
                "link_changed",
            )
        if link is not None and form_ticket is not None:
            # The public API always supplies a ticket (empty if omitted). Internal
            # legacy callers remain compatible; saved replays returned above.
            worker = self.session.get(Worker, link.worker_id, populate_existing=True)
            if not worker or not form_ticket or not hmac.compare_digest(form_ticket, self._form_ticket(session_row, link, worker)):
                raise LineRegistrationRejected(409, "登録情報が変わったか、表示の確認ができません。画面を閉じて登録ボタンから開き直してください。入力は残しています。", "form_changed")
            merged = worker_form_values(worker)
            for field in sent:
                if field in merged:
                    merged[field] = str(payload.get(field) or "").strip()
            normalize_line_registration(merged, sent=set(merged), linked=False, full_required=True)
        normalized = normalize_line_registration(payload, sent=sent, linked=link is not None, full_required=True)
        digest = content_hash(normalized.canonical())
        context = self._open_context(session_row.line_user_id)
        if context is not None and (peeked is None or peeked.request_id != context.request_id):
            raise _SubmitRetry()
        if context is not None:
            request = self._lock_request(context.request_id)
            context = self._open_context(session_row.line_user_id)
            if request is None or context is None or not _request_is_open(request):
                return self._create(session_row, link, idempotency_key, normalized, digest)
            self.session.add(
                LineRegistrationSubmitKey(
                    id=generate_ulid(),
                    line_user_id=session_row.line_user_id,
                    idempotency_key=idempotency_key,
                    request_id=request.id,
                    content_hash=digest,
                )
            )
            self._audit_success(request.id, saved=False)
            self.session.flush()
            return SubmitResult(request.id, request.status, False, NOT_SAVED_MESSAGE)
        return self._create(session_row, link, idempotency_key, normalized, digest)

    def _create(
        self,
        session_row: LineRegistrationSession,
        link: LineWorkerLink | None,
        idempotency_key: str,
        normalized: NormalizedRegistration,
        digest: str,
    ) -> SubmitResult:
        request = RegistrationRequest(
            id=generate_ulid(),
            request_type="worker",
            status="pending",
            source_type="public_form",
            failed_attempts=0,
            submitted_at=datetime.now(timezone.utc),
        )
        detail = WorkerRegistrationRequestDetail(
            id=generate_ulid(),
            request_id=request.id,
            last_name=normalized.last_name,
            first_name=normalized.first_name,
            last_name_furigana=normalized.last_name_furigana,
            first_name_furigana=normalized.first_name_furigana,
            email=normalized.email,
            phone=normalized.phone,
            zipcode=normalized.postal_code,
            prefecture=normalized.prefecture,
            city_address=normalized.address1,
            building_address=normalized.address2 if normalized.address_sent else None,
            birth_date=normalized.birth_date,
            nearest_station=normalized.nearest_station,
            station_walk_minutes=normalized.station_walk_minutes,
            emergency_contact_phone=normalized.emergency_contact_phone,
            emergency_contact_name=normalized.emergency_contact_name,
            emergency_contact_relationship=normalized.emergency_contact_relationship,
            line_registration_form_version=2,
        )
        context = LineRegistrationContext(
            id=generate_ulid(),
            request_id=request.id,
            line_user_id=session_row.line_user_id,
            line_worker_link_id=link.id if link else None,
            worker_id=link.worker_id if link else None,
            is_open=True,
        )
        submit_key = LineRegistrationSubmitKey(
            id=generate_ulid(),
            line_user_id=session_row.line_user_id,
            idempotency_key=idempotency_key,
            request_id=request.id,
            content_hash=digest,
        )
        self.session.add(request)
        self.session.flush()
        self.session.add(detail)
        self.session.add(context)
        self.session.add(submit_key)
        self.session.add(LineRegistrationReceipt(
            request_id=request.id,
            retry_key=str(uuid4()),
            message_text="登録を受付けました",
            status="pending",
            attempt_count=0,
            next_attempt_at=datetime.now(timezone.utc),
        ))
        self._audit_success(request.id, saved=True)
        self.session.flush()
        return SubmitResult(request.id, "pending", True, SAVED_MESSAGE)

    def _replay_saved_key(self, existing_key: LineRegistrationSubmitKey, payload: dict, sent: set[str]) -> SubmitResult:
        try:
            normalized = canonicalize_line_registration(payload, sent=sent)
            digest = content_hash(normalized.canonical())
        except LineRegistrationInputError as exc:
            raise LineRegistrationRejected(
                409,
                "同じ送信識別子で、内容の違う申請は受け付けません。",
                "idempotency_conflict",
                existing_key.request_id,
            ) from exc
        return self._replay(existing_key, digest)

    def _replay(self, existing_key: LineRegistrationSubmitKey, digest: str) -> SubmitResult:
        if not hmac.compare_digest(existing_key.content_hash, digest):
            raise LineRegistrationRejected(
                409,
                "同じ送信識別子で、内容の違う申請は受け付けません。",
                "idempotency_conflict",
                existing_key.request_id,
            )
        request = self.session.get(RegistrationRequest, existing_key.request_id)
        if request is None:
            raise LineRegistrationRejected(409, "以前の申請を確認できません。", "missing_request", existing_key.request_id)
        detail = self.session.scalar(
            select(WorkerRegistrationRequestDetail).where(WorkerRegistrationRequestDetail.request_id == request.id)
        )
        saved = detail is not None and content_hash(_detail_canonical(detail)) == digest
        message = SAVED_MESSAGE if saved else NOT_SAVED_MESSAGE
        return SubmitResult(request.id, request.status, saved, message)

    def _audit_success(self, request_id: str, *, saved: bool) -> None:
        AuditService(self.session).log(
            "line_registration_submitted",
            target_type="registration_request",
            target_id=request_id,
            actor="line-registration",
            after_value={"saved": saved, "status": "pending"},
        )

    def _require_open(self) -> None:
        if not registration_entry_ready():
            raise LineRegistrationClosed()

    def _valid_session(self, token: str) -> LineRegistrationSession:
        row = self.session.scalar(
            select(LineRegistrationSession).where(LineRegistrationSession.token_hash == _token_hash(token))
        )
        if row is None or _aware(row.expires_at) <= datetime.now(timezone.utc):
            raise LineRegistrationAuthError(
                "本人確認の期限が切れました。入力は残しています。本人確認をやり直してから、もう一度送信してください。"
            )
        return row

    def _active_link(self, line_user_id: str) -> LineWorkerLink | None:
        return self.session.scalar(
            select(LineWorkerLink).where(
                LineWorkerLink.line_user_id == line_user_id,
                LineWorkerLink.status == LINK_ACTIVE,
            )
        )

    def _current_link(self, session_row: LineRegistrationSession) -> LineWorkerLink | None:
        link = self._active_link(session_row.line_user_id)
        if link is None:
            return None
        worker = self.session.get(Worker, link.worker_id)
        if worker is None or worker.deleted_at is not None or not worker.is_active:
            return None
        return link

    def _link_matches_session(self, session_row: LineRegistrationSession, link: LineWorkerLink | None) -> bool:
        current_link_id = link.id if link else None
        current_worker_id = link.worker_id if link else None
        return session_row.line_worker_link_id == current_link_id and session_row.worker_id == current_worker_id

    def _open_context(self, line_user_id: str) -> LineRegistrationContext | None:
        return self.session.scalar(
            select(LineRegistrationContext).where(
                LineRegistrationContext.line_user_id == line_user_id,
                LineRegistrationContext.is_open.is_(True),
            )
        )

    def _find_key(self, line_user_id: str, idempotency_key: str) -> LineRegistrationSubmitKey | None:
        return self.session.scalar(
            select(LineRegistrationSubmitKey).where(
                LineRegistrationSubmitKey.line_user_id == line_user_id,
                LineRegistrationSubmitKey.idempotency_key == idempotency_key,
            )
        )

    def _lock_active_links(self, line_user_id: str) -> None:
        if self.session.get_bind().dialect.name != "postgresql":
            return
        self.session.execute(
            text(
                """
                SELECT id FROM line_worker_links
                WHERE line_user_id = :line_user_id AND status = 'active'
                FOR UPDATE
                """
            ),
            {"line_user_id": line_user_id},
        )

    def _lock_request(self, request_id: str) -> RegistrationRequest | None:
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(
                text("SELECT id FROM registration_requests WHERE id = :id FOR UPDATE"),
                {"id": request_id},
            )
        return self.session.get(RegistrationRequest, request_id)


def is_line_registration_request(session: Session, request_id: str) -> bool:
    return (
        session.scalar(
            select(LineRegistrationContext.id).where(LineRegistrationContext.request_id == request_id)
        )
        is not None
    )


def _request_is_open(request: RegistrationRequest) -> bool:
    return request.status == "pending" and request.deleted_at is None


def _detail_canonical(detail: WorkerRegistrationRequestDetail) -> dict[str, str | int | None]:
    address_sent = detail.zipcode is not None or detail.prefecture is not None or detail.city_address is not None
    values = {
        "last_name": detail.last_name,
        "first_name": detail.first_name,
        "last_name_furigana": detail.last_name_furigana,
        "first_name_furigana": detail.first_name_furigana,
        "phone": detail.phone,
        "email": detail.email,
        "birth_date": detail.birth_date.isoformat() if detail.birth_date else None,
        "postal_code": detail.zipcode,
        "prefecture": detail.prefecture,
        "address1": detail.city_address,
        "address2": detail.building_address if address_sent else None,
    }
    if detail.nearest_station is not None:
        values["nearest_station"] = detail.nearest_station
    if detail.station_walk_minutes is not None:
        values["station_walk_minutes"] = detail.station_walk_minutes
    for field in ("emergency_contact_phone", "emergency_contact_name", "emergency_contact_relationship"):
        if getattr(detail, field) is not None:
            values[field] = getattr(detail, field)
    return values


def _expected_unique(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc))
    return (
        "uq_line_registration_submit_keys" in message
        or "uq_line_registration_contexts_open" in message
        or "line_registration_submit_keys.line_user_id" in message
        or "line_registration_contexts.line_user_id" in message
    )
