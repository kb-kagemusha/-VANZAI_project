"""公式LINEからの稼働者登録申請。DEC-032 / DEC-033。

審査中の値を複製する表は作らない。比較は署名付きの比較票で行う。
この段階では入口を有効にしない。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, generate_ulid


class LineRegistrationSession(Base, TimestampMixin):
    """検証済みのLINE本人に対する短い受付セッション。本文は持たない。"""

    __tablename__ = "line_registration_sessions"
    __table_args__ = (
        CheckConstraint(
            "length(token_hash) = 64",
            name="ck_line_registration_sessions_token_hash",
        ),
        CheckConstraint(
            "length(line_user_id) > 0",
            name="ck_line_registration_sessions_subject",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_worker_link_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("line_worker_links.id"), nullable=True
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LineRegistrationContext(Base, TimestampMixin):
    """申請1件と、検証済みLINE本人の対応。未完了は本人につき1件。"""

    __tablename__ = "line_registration_contexts"
    __table_args__ = (
        CheckConstraint(
            "length(line_user_id) > 0",
            name="ck_line_registration_contexts_subject",
        ),
        Index(
            "uq_line_registration_contexts_open_subject",
            "line_user_id",
            unique=True,
            sqlite_where=text("is_open = 1"),
            postgresql_where=text("is_open"),
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False, unique=True
    )
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_worker_link_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("line_worker_links.id"), nullable=True
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workers.id"), nullable=True
    )
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LineRegistrationSubmitKey(Base, TimestampMixin):
    """同じ本人・同じ冪等キーは1行。本文の対応は認証付きハッシュで持つ。"""

    __tablename__ = "line_registration_submit_keys"
    __table_args__ = (
        CheckConstraint(
            "length(line_user_id) > 0",
            name="ck_line_registration_submit_keys_subject",
        ),
        CheckConstraint(
            "length(idempotency_key) > 0",
            name="ck_line_registration_submit_keys_idempotency",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_line_registration_submit_keys_content_hash",
        ),
        Index(
            "uq_line_registration_submit_keys_subject_key",
            "line_user_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("registration_requests.id"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class LineRegistrationReceipt(Base, TimestampMixin):
    """申請保存と同じ取引で作る受付通知。既存申請へは遡及作成しない。"""

    __tablename__ = "line_registration_receipts"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_line_receipt_status"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= 5", name="ck_line_receipt_attempts"),
        CheckConstraint("status <> 'sent' OR sent_at IS NOT NULL", name="ck_line_receipt_sent"),
        Index("ix_line_receipt_due", "status", "next_attempt_at"),
    )

    request_id: Mapped[str] = mapped_column(String(26), ForeignKey("registration_requests.id"), primary_key=True)
    retry_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    message_text: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
