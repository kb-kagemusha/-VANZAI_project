"""公式LINEの本人紐付けと、発注依頼書の送信試行。

テスト用公式アカウントから、テスト区分を1人ずつ送るために使う。
正式区分の送信と弁護士確認済み書式は対象外。物理削除はしない。
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, generate_ulid

LINK_ACTIVE = "active"
LINK_REVOKED = "revoked"
LINK_STATUSES = (LINK_ACTIVE, LINK_REVOKED)

ATTEMPT_ACCEPTED = "accepted"
ATTEMPT_FAILED = "failed"
ATTEMPT_UNKNOWN = "unknown"
ATTEMPT_RESULTS = (ATTEMPT_ACCEPTED, ATTEMPT_FAILED, ATTEMPT_UNKNOWN)


class LineWorkerLink(Base, TimestampMixin):
    """稼働者とLINEユーザーの有効な紐付け。解除しても行は残す。"""

    __tablename__ = "line_worker_links"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LINK_ACTIVE)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="ck_line_worker_links_status"),
        Index("ix_line_worker_links_worker", "worker_id"),
        Index("ix_line_worker_links_line_user", "line_user_id"),
        Index(
            "uq_line_worker_links_active_worker",
            "worker_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_line_worker_links_active_line_user",
            "line_user_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )


class LineLinkCode(Base):
    """本人が公式LINEへ送る一次性コード。平文は保存しない。"""

    __tablename__ = "line_link_codes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_line_link_codes_worker", "worker_id"),)


class LineWebhookEvent(Base):
    """Webhookの再送で二重に紐付け・受領しないためのイベントID。"""

    __tablename__ = "line_webhook_events"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderRequestSendAttempt(Base):
    """1人への送信試行。再通知は同じ送付行に試行を足す。"""

    __tablename__ = "order_request_send_attempts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    delivery_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_deliveries.id"), nullable=False
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    line_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(300), nullable=True)
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "result IN ('accepted', 'failed', 'unknown')",
            name="ck_order_request_send_attempts_result",
        ),
        Index("ix_order_request_send_attempts_delivery", "delivery_id"),
    )


class OrderRequestFileToken(Base):
    """送付したPDFを開くための一時URL。ログインは不要で、トークンが秘密。"""

    __tablename__ = "order_request_file_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    delivery_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_deliveries.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_order_request_file_tokens_delivery", "delivery_id"),)
