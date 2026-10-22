"""発注依頼書（共通PDF・版・送付行）。

計画: 発注依頼書LINE送付 初期版。確定後の本文と送付時の氏名は上書きしない。
公式LINEの紐付け・送信試行・受領は line_order 側。このファイルは版と送付行を保持する。
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    ForeignKeyConstraint,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, generate_ulid

KIND_FORMAL = "formal"
KIND_TEST = "test"
DOCUMENT_KINDS = (KIND_FORMAL, KIND_TEST)

STATUS_DRAFT = "draft"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
VERSION_STATUSES = (STATUS_DRAFT, STATUS_CONFIRMED, STATUS_CANCELLED)

SEND_UNSENT = "unsent"
SEND_PROCESSING = "processing"
SEND_ACCEPTED = "accepted"
SEND_FAILED = "failed"
SEND_UNKNOWN = "unknown"
SEND_STATUSES = (SEND_UNSENT, SEND_PROCESSING, SEND_ACCEPTED, SEND_FAILED, SEND_UNKNOWN)

ACK_UNACKED = "unacked"
ACK_ACKED = "acked"
ACK_DECLINE_PENDING = "decline_pending"
ACK_DECLINED = "declined"
ACK_STATUSES = (ACK_UNACKED, ACK_ACKED, ACK_DECLINE_PENDING, ACK_DECLINED)

MAX_RECIPIENTS = 40


class OrderRequestTemplate(Base, TimestampMixin):
    """名前付きの独立した内容スナップショット。依頼書を変更しても連動しない。"""

    __tablename__ = "order_request_templates"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_version_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_versions.id"), nullable=False)
    source_document_number: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_order_request_templates_name"),
        Index("uq_order_request_templates_active_name", "name_key", unique=True,
              postgresql_where=text("archived_at IS NULL"), sqlite_where=text("archived_at IS NULL")),
        Index("ix_order_request_templates_archived", "archived_at"),
    )


class OrderRequestDocument(Base, TimestampMixin):
    """依頼書の系列。テスト／正式は確定後に変えない。"""

    __tablename__ = "order_request_documents"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    document_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )

    versions: Mapped[list["OrderRequestVersion"]] = relationship(
        back_populates="document",
        order_by="OrderRequestVersion.version_no",
    )

    __table_args__ = (
        CheckConstraint("kind IN ('formal', 'test')", name="ck_order_request_documents_kind"),
        Index("ix_order_request_documents_kind", "kind"),
        Index("ix_order_request_documents_deleted_at", "deleted_at"),
    )


class OrderRequestVersion(Base, TimestampMixin):
    """版。下書きは編集可。確定版の本文とPDFは上書きしない。"""

    __tablename__ = "order_request_versions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    document_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_documents.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # 依頼書の系列（「変更を作成」で作った依頼書も同じ系列）。作成時に決め、以後は変えない。
    series_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("order_request_series.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    revision_of_version_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("order_request_versions.id"), nullable=True
    )
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    work_date_label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("sites.id"), nullable=True)
    site_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_conditions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    contact_desk: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    counterparty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_client_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("clients.id"), nullable=True)
    internal_client_staff_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("client_staff.id"), nullable=True)
    internal_source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pdf_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    draft_worker_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 送付先ごとの個人不参加日 {worker_id: ["YYYY-MM-DD", ...]}。共通本文には含めない（DEC-065）。
    draft_recipient_absences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 日付を選んで受諾できる（一部の日だけの参加を認める）。確定後は変えない（修正版で変える）。A1+ §3.1
    allow_partial_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    phone_first: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phone_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phone_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracker_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )
    follow_up_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_stopped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id"), nullable=False
    )

    document: Mapped[OrderRequestDocument] = relationship(back_populates="versions")
    deliveries: Mapped[list["OrderRequestDelivery"]] = relationship(
        back_populates="version",
    )
    notes: Mapped[list["OrderRequestNote"]] = relationship(back_populates="version")

    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_order_request_versions_doc_no"),
        UniqueConstraint("id", "document_id", name="uq_order_request_versions_id_document"),
        UniqueConstraint("id", "series_id", name="uq_order_request_versions_id_series"),
        CheckConstraint("internal_client_staff_id IS NULL OR internal_client_id IS NOT NULL", name="ck_order_internal_staff_client"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'cancelled')",
            name="ck_order_request_versions_status",
        ),
        Index("ix_order_request_versions_document", "document_id"),
        Index("ix_order_request_versions_status", "status"),
    )


class OrderRequestDelivery(Base, TimestampMixin):
    """版×稼働者。確定時に作る。再通知は同じ行に試行を足す（試行テーブルは送信実装時）。"""

    __tablename__ = "order_request_deliveries"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    version_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_versions.id"), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    worker_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    send_status: Mapped[str] = mapped_column(String(20), nullable=False, default=SEND_UNSENT)
    ack_status: Mapped[str] = mapped_column(String(20), nullable=False, default=ACK_UNACKED)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ack_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 提示日（実勤務日−個人不参加日）。確定時に固定。NULL は A1 導入前の送付行で、稼働予定の対象外。
    offered_dates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_participation_state_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    version: Mapped[OrderRequestVersion] = relationship(back_populates="deliveries")

    __table_args__ = (
        UniqueConstraint("version_id", "worker_id", name="uq_order_request_deliveries_version_worker"),
        UniqueConstraint("id", "worker_id", name="uq_order_request_deliveries_id_worker"),
        UniqueConstraint("id", "version_id", name="uq_order_request_deliveries_id_version"),
        ForeignKeyConstraint(
            ["current_participation_state_id", "id"],
            ["delivery_participation_states.id", "delivery_participation_states.delivery_id"],
            name="fk_order_request_deliveries_current_state",
            use_alter=True,
        ),
        CheckConstraint(
            "send_status IN ('unsent', 'processing', 'accepted', 'failed', 'unknown')",
            name="ck_order_request_deliveries_send",
        ),
        CheckConstraint(
            "ack_status IN ('unacked', 'acked', 'decline_pending', 'declined')",
            name="ck_order_request_deliveries_ack",
        ),
        Index("ix_order_request_deliveries_version", "version_id"),
        Index("ix_order_request_deliveries_send", "send_status"),
    )


class OrderRequestNote(Base):
    """対応メモ。送付済み・受領済みにはしない。"""

    __tablename__ = "order_request_notes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    version_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_versions.id"), nullable=False
    )
    author_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    version: Mapped[OrderRequestVersion] = relationship(back_populates="notes")

    __table_args__ = (Index("ix_order_request_notes_version", "version_id"),)


from src.models import line_daily  # noqa: E402,F401 — 系列・稼働予定のテーブルを登録する
