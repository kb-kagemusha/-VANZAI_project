"""OCR public upload link management and public upload handling."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.base import generate_ulid
from src.models.ocr import (
    OcrParseJob,
    OcrSourceImage,
    OcrUploadAttempt,
    OcrUploadLink,
    OcrUploadRateLimit,
    OcrUploadSession,
)
from src.services.audit import AuditService
from src.services.document_storage import ObjectStorage
from src.services.ocr.paygate_screenshot_gate import evaluate_paygate_screenshot_gate
from src.services.ocr.parsers.registry import VALID_SOURCE_TYPES
from src.services.ocr.upload_validation import validate_upload_image_bytes
from src.services.ocr_service import OcrService, build_ocr_object_key

ACCEPTED_ATTEMPT_STATUSES = frozenset({"saved", "parse_queued", "parse_completed", "parse_failed"})
LINK_RATE_LIMIT_PER_MINUTE = 30
IP_RATE_LIMIT_PER_MINUTE = 60
SESSION_HOURS = 2
QUARANTINE_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_secret(value: str, *, secret_env: str) -> str:
    secret = os.getenv(secret_env, os.getenv("JWT_SECRET_KEY", "vanzai-ocr-upload"))
    return hashlib.sha256(f"{secret}:{value}".encode("utf-8")).hexdigest()


def hash_upload_token(token: str) -> str:
    return _hash_secret(token, secret_env="OCR_UPLOAD_TOKEN_SECRET")


def hash_session_token(token: str) -> str:
    return _hash_secret(token, secret_env="OCR_UPLOAD_SESSION_SECRET")


def hash_client_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return _hash_secret(ip, secret_env="OCR_UPLOAD_IP_SECRET")


def _quarantine_storage() -> ObjectStorage:
    root = Path(os.getenv("OCR_QUARANTINE_ROOT", "storage/ocr/quarantine"))
    return ObjectStorage(root=root)


def _minute_window(now: datetime | None = None) -> datetime:
    current = now or _utcnow()
    return current.replace(second=0, microsecond=0)


def _increment_rate_limit(session: Session, scope: str, *, limit: int) -> bool:
    window = _minute_window()
    row = session.execute(
        select(OcrUploadRateLimit).where(
            OcrUploadRateLimit.scope == scope,
            OcrUploadRateLimit.window_start == window,
        )
    ).scalar_one_or_none()
    if row is None:
        row = OcrUploadRateLimit(scope=scope, window_start=window, count=1)
        session.add(row)
        session.flush()
        return True
    if row.count >= limit:
        return False
    row.count += 1
    session.flush()
    return True


class OcrUploadLinkService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)
        self.ocr = OcrService(session)
        self.quarantine = _quarantine_storage()

    def create_link(
        self,
        *,
        created_by: str,
        label: str | None,
        expires_in_days: int,
        public_memo: str | None,
        internal_memo: str | None,
        default_source_type: str,
        period_key: str | None,
        max_upload_count: int | None,
    ) -> tuple[OcrUploadLink, str]:
        token = secrets.token_urlsafe(32)
        link = OcrUploadLink(
            id=generate_ulid(),
            token_hash=hash_upload_token(token),
            token_suffix=token[-6:],
            label=label,
            status="active",
            expires_at=_utcnow() + timedelta(days=expires_in_days),
            created_by=created_by,
            public_memo=public_memo,
            internal_memo=internal_memo,
            default_source_type=default_source_type,
            period_key=period_key,
            max_upload_count=max_upload_count,
        )
        self.session.add(link)
        self.session.flush()
        self.audit.log(
            "ocr_upload_link_created",
            target_type="ocr_upload_link",
            target_id=link.id,
            actor=created_by,
            after_value={"label": label, "expires_in_days": expires_in_days},
        )
        return link, token

    def list_links(self, *, limit: int = 50, offset: int = 0) -> tuple[list[OcrUploadLink], int]:
        query = select(OcrUploadLink).order_by(OcrUploadLink.created_at.desc())
        total = self.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        items = self.session.execute(query.offset(offset).limit(limit)).scalars().all()
        return list(items), total

    def revoke_link(self, link_id: str, *, actor: str) -> OcrUploadLink:
        link = self.session.get(OcrUploadLink, link_id)
        if link is None:
            raise ValueError("Link not found")
        link.status = "revoked"
        link.revoked_at = _utcnow()
        link.revoked_by = actor
        sessions = self.session.execute(
            select(OcrUploadSession).where(
                OcrUploadSession.upload_link_id == link_id,
                OcrUploadSession.revoked_at.is_(None),
            )
        ).scalars().all()
        for session_row in sessions:
            session_row.revoked_at = _utcnow()
        self.audit.log(
            "ocr_upload_link_revoked",
            target_type="ocr_upload_link",
            target_id=link.id,
            actor=actor,
        )
        return link

    def get_link_by_token(self, token: str) -> OcrUploadLink | None:
        token_hash = hash_upload_token(token)
        return self.session.execute(
            select(OcrUploadLink).where(OcrUploadLink.token_hash == token_hash)
        ).scalar_one_or_none()

    def _ensure_link_usable(self, link: OcrUploadLink) -> None:
        if link.status == "revoked":
            raise PermissionError("link_revoked")
        if link.expires_at < _utcnow():
            raise PermissionError("link_expired")

    def create_session(self, link: OcrUploadLink) -> tuple[OcrUploadSession, str]:
        self._ensure_link_usable(link)
        token = secrets.token_urlsafe(32)
        session_row = OcrUploadSession(
            id=generate_ulid(),
            upload_link_id=link.id,
            session_token_hash=hash_session_token(token),
            expires_at=_utcnow() + timedelta(hours=SESSION_HOURS),
        )
        self.session.add(session_row)
        link.last_used_at = _utcnow()
        self.session.flush()
        return session_row, token

    def get_session_by_token(self, token: str) -> OcrUploadSession | None:
        token_hash = hash_session_token(token)
        return self.session.execute(
            select(OcrUploadSession).where(OcrUploadSession.session_token_hash == token_hash)
        ).scalar_one_or_none()

    def resolve_session(self, token: str) -> tuple[OcrUploadSession, OcrUploadLink]:
        session_row = self.get_session_by_token(token)
        if session_row is None:
            raise PermissionError("session_invalid")
        if session_row.revoked_at is not None:
            raise PermissionError("session_revoked")
        if session_row.expires_at < _utcnow():
            raise PermissionError("session_expired")
        link = self.session.get(OcrUploadLink, session_row.upload_link_id)
        if link is None:
            raise PermissionError("session_invalid")
        if link.status == "revoked":
            raise PermissionError("link_revoked")
        if link.expires_at < _utcnow():
            raise PermissionError("link_expired")
        session_row.upload_link = link  # type: ignore[attr-defined]
        link.last_used_at = _utcnow()
        return session_row, link

    def _count_accepted_attempts(self, link_id: str) -> int:
        return self.session.execute(
            select(func.count())
            .select_from(OcrUploadAttempt)
            .where(
                OcrUploadAttempt.upload_link_id == link_id,
                OcrUploadAttempt.attempt_status.in_(ACCEPTED_ATTEMPT_STATUSES),
            )
        ).scalar_one()

    def handle_public_upload(
        self,
        *,
        link: OcrUploadLink,
        source_type: str,
        file_bytes: bytes,
        file_name: str | None,
        public_uploader_name: str | None,
        client_ip: str | None,
        user_agent: str | None,
    ) -> dict:
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError("invalid_source_type")

        if not _increment_rate_limit(self.session, f"link:{link.id}", limit=LINK_RATE_LIMIT_PER_MINUTE):
            raise PermissionError("rate_limit")
        ip_hash = hash_client_ip(client_ip)
        if ip_hash and not _increment_rate_limit(self.session, f"ip:{ip_hash}", limit=IP_RATE_LIMIT_PER_MINUTE):
            raise PermissionError("rate_limit")

        validation = validate_upload_image_bytes(file_bytes, original_filename=file_name)
        if not validation.ok:
            raise ValueError(validation.error_code or "invalid_file")

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        existing = self.session.execute(
            select(OcrSourceImage).where(OcrSourceImage.sha256 == sha256)
        ).scalar_one_or_none()

        gate_skipped_reason: str | None = None
        gate_payment_method_count: int | None = None

        if existing is None and source_type == "paygate_screenshot":
            gate = evaluate_paygate_screenshot_gate(self.session, file_bytes)
            gate_skipped_reason = gate.skip_reason
            gate_payment_method_count = gate.payment_method_count
            if gate.rejected:
                attempt = OcrUploadAttempt(
                    id=generate_ulid(),
                    upload_link_id=link.id,
                    source_type=source_type,
                    public_uploader_name=public_uploader_name,
                    attempt_status="rejected_invalid_paygate_image",
                    client_ip_hash=ip_hash,
                    user_agent=(user_agent or "")[:255] or None,
                    gate_skipped_reason=gate_skipped_reason,
                    gate_payment_method_count=gate_payment_method_count,
                )
                quarantine_key = f"{attempt.id}/{build_ocr_object_key(attempt.id, file_name)}"
                self.quarantine.save_bytes(quarantine_key, file_bytes)
                attempt.quarantine_storage_key = quarantine_key
                self.session.add(attempt)
                self.session.flush()
                raise ValueError("invalid_paygate_image")

        locked_link = self.session.execute(
            select(OcrUploadLink).where(OcrUploadLink.id == link.id).with_for_update()
        ).scalar_one()

        accepted_count = self._count_accepted_attempts(locked_link.id)
        if locked_link.max_upload_count is not None and accepted_count >= locked_link.max_upload_count:
            raise PermissionError("upload_limit")

        uploaded_by = public_uploader_name or "external"
        if existing is not None:
            image, reused = existing, True
            if image.deleted_at is not None:
                image.deleted_at = None
            image.upload_link_id = locked_link.id
            image.upload_origin = "public_link"
            image.public_uploader_name = public_uploader_name
            image.uploaded_by = uploaded_by
            image.source_type = source_type
            image.parse_status = "pending"
            image.error_message = None
            self.session.flush()
        else:
            image, reused = self.ocr.upload_image(
                file_bytes=file_bytes,
                file_name=file_name,
                source_type=source_type,
                uploaded_by=uploaded_by,
                mime_type=validation.mime_type,
            )
            image.upload_link_id = locked_link.id
            image.upload_origin = "public_link"
            image.public_uploader_name = public_uploader_name
            self.session.flush()

        attempt = OcrUploadAttempt(
            id=generate_ulid(),
            upload_link_id=locked_link.id,
            source_image_id=image.id,
            reused_existing=reused,
            source_type=source_type,
            public_uploader_name=public_uploader_name,
            attempt_status="saved",
            client_ip_hash=ip_hash,
            user_agent=(user_agent or "")[:255] or None,
            gate_skipped_reason=gate_skipped_reason,
            gate_payment_method_count=gate_payment_method_count,
        )
        self.session.add(attempt)

        job = OcrParseJob(
            id=generate_ulid(),
            status="pending",
            image_count=1,
            executed_by="public_upload",
            source_channel="public_link",
            upload_attempt_id=attempt.id,
            image_ids_json=[image.id],
            priority=10,
        )
        self.session.add(job)
        attempt.parse_job_id = job.id
        attempt.attempt_status = "parse_queued"

        locked_link.upload_count += 1
        locked_link.last_upload_at = _utcnow()
        if source_type == "paygate_screenshot":
            locked_link.upload_count_paygate += 1
        else:
            locked_link.upload_count_receipt += 1

        self.session.flush()
        self.audit.log(
            "ocr_public_upload_accepted",
            target_type="ocr_upload_attempt",
            target_id=attempt.id,
            actor=uploaded_by,
            after_value={
                "link_id": locked_link.id,
                "image_id": image.id,
                "reused_existing": reused,
                "job_id": job.id,
            },
        )
        return {
            "message": "受付が完了しました。内容は事務局で確認します。",
            "reused_existing": reused,
            "image_id": image.id,
            "job_id": job.id,
        }

    def recent_hour_attempt_count(self, link_id: str) -> int:
        since = _utcnow() - timedelta(hours=1)
        return self.session.execute(
            select(func.count())
            .select_from(OcrUploadAttempt)
            .where(
                OcrUploadAttempt.upload_link_id == link_id,
                OcrUploadAttempt.created_at >= since,
            )
        ).scalar_one()
