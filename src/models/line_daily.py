"""公式LINEの日次操作（稼働予定・起床報告）と、依頼書の系列。DEC-063〜066、詳細設計 A0・A1。

稼働予定は依頼書からの派生データで、直接は編集しない。金額の列は持たない。
物理削除はしない（参加日の状態は追記のみ）。
"""
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, generate_ulid

ENTRY_ACTIVE = "active"
ENTRY_CHANGING = "changing"
ENTRY_SUPERSEDED = "superseded"
ENTRY_CANCELLED = "cancelled"
ENTRY_STATUSES = (ENTRY_ACTIVE, ENTRY_CHANGING, ENTRY_SUPERSEDED, ENTRY_CANCELLED)

SOURCE_FULL_ACCEPT = "full_accept"
SOURCE_PARTIAL_ACCEPT = "partial_accept"
SOURCE_CHANGE_APPROVED = "change_approved"
SOURCE_OPS_RECORDED_DECLINE = "ops_recorded_decline"
PARTICIPATION_SOURCES = (
    SOURCE_FULL_ACCEPT,
    SOURCE_PARTIAL_ACCEPT,
    SOURCE_CHANGE_APPROVED,
    SOURCE_OPS_RECORDED_DECLINE,
)

END_DECLINED_NEW_VERSION = "declined_new_version"
END_REMOVED = "removed_from_recipients"
END_DOCUMENT_ENDED = "document_ended"
END_VIEW_REVOKED = "view_revoked"
END_REASONS = (END_DECLINED_NEW_VERSION, END_REMOVED, END_DOCUMENT_ENDED, END_VIEW_REVOKED)


class OrderRequestSeries(Base, TimestampMixin):
    """依頼書の系列。最初の依頼書と、そこから「変更を作成」で作った依頼書をまとめる。

    回答受付版（最後に確定した版。取消で NULL。旧版へは戻さない）を系列ごとに1つ持つ。
    """

    __tablename__ = "order_request_series"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    answerable_version_id: Mapped[str | None] = mapped_column(String(26), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["answerable_version_id", "id"],
            ["order_request_versions.id", "order_request_versions.series_id"],
            name="fk_order_request_series_answerable",
            use_alter=True,
        ),
    )


class DeliveryParticipationState(Base):
    """送付先の参加日の状態。追記のみ。送付行は current_participation_state_id で現在の状態を指す。"""

    __tablename__ = "delivery_participation_states"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    delivery_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("order_request_deliveries.id"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    dates: Mapped[list] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_request_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("delivery_id", "seq", name="uq_delivery_participation_seq"),
        UniqueConstraint("id", "delivery_id", name="uq_delivery_participation_id_delivery"),
        CheckConstraint("seq > 0", name="ck_delivery_participation_seq"),
        CheckConstraint(
            "source IN ('full_accept', 'partial_accept', 'change_approved', 'ops_recorded_decline')",
            name="ck_delivery_participation_source",
        ),
    )


class OrderRequestWorkerApplication(Base):
    """系列×稼働者の適用送付行。ロックの中の出来事だけで更新し、稼働予定の再構築の入力にする。"""

    __tablename__ = "order_request_worker_applications"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    applied_delivery_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    applied_version_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("series_id", "worker_id", name="uq_order_worker_application"),
        # 両方NULLか両方非NULL（複合FKはNULLを含むと所属を検証しないため。R3-01）
        CheckConstraint(
            "(applied_delivery_id IS NULL AND applied_version_id IS NULL)"
            " OR (applied_delivery_id IS NOT NULL AND applied_version_id IS NOT NULL)",
            name="ck_order_worker_application_pair",
        ),
        ForeignKeyConstraint(
            ["applied_delivery_id", "worker_id"],
            ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
            name="fk_order_worker_application_delivery_worker",
        ),
        ForeignKeyConstraint(
            ["applied_delivery_id", "applied_version_id"],
            ["order_request_deliveries.id", "order_request_deliveries.version_id"],
            name="fk_order_worker_application_delivery_version",
        ),
        ForeignKeyConstraint(
            ["applied_version_id", "series_id"],
            ["order_request_versions.id", "order_request_versions.series_id"],
            name="fk_order_worker_application_version_series",
        ),
        CheckConstraint(
            "ended_reason IS NULL OR ended_reason IN "
            "('declined_new_version', 'removed_from_recipients', 'document_ended', 'view_revoked')",
            name="ck_order_worker_application_end",
        ),
    )


class WorkerScheduleEntry(Base, TimestampMixin):
    """稼働予定。依頼書からの派生データ。同じキーの行は作り直さず状態を更新する。"""

    __tablename__ = "worker_schedule_entries"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_documents.id"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(26), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(26), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    work_group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_next_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_state_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    site_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_place: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("delivery_id", "work_group_id", "work_date", name="uq_worker_schedule_entry_key"),
        CheckConstraint(
            "status IN ('active', 'changing', 'superseded', 'cancelled')",
            name="ck_worker_schedule_entry_status",
        ),
        ForeignKeyConstraint(
            ["version_id", "series_id"],
            ["order_request_versions.id", "order_request_versions.series_id"],
            name="fk_worker_schedule_entry_version_series",
        ),
        ForeignKeyConstraint(
            ["version_id", "document_id"],
            ["order_request_versions.id", "order_request_versions.document_id"],
            name="fk_worker_schedule_entry_version_document",
        ),
        ForeignKeyConstraint(
            ["delivery_id", "version_id"],
            ["order_request_deliveries.id", "order_request_deliveries.version_id"],
            name="fk_worker_schedule_entry_delivery_version",
        ),
        ForeignKeyConstraint(
            ["delivery_id", "worker_id"],
            ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
            name="fk_worker_schedule_entry_delivery_worker",
        ),
        ForeignKeyConstraint(
            ["source_state_id", "delivery_id"],
            ["delivery_participation_states.id", "delivery_participation_states.delivery_id"],
            name="fk_worker_schedule_entry_state",
        ),
        Index("ix_worker_schedule_entries_worker_date", "worker_id", "work_date", "status"),
        Index("ix_worker_schedule_entries_series", "series_id"),
        Index("ix_worker_schedule_entries_document", "document_id"),
    )


class WakeReport(Base):
    """起床報告。報告日はLINEイベント発生時刻の日本時間の日付。テストの予定だけの日は is_test。"""

    __tablename__ = "wake_reports"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    event_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    late_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    line_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("worker_id", "report_date", "is_test", name="uq_wake_report_worker_date"),
        Index("ix_wake_reports_date", "report_date"),
    )


WAKE_CONTACT_RESULTS = {
    "line_sent": "LINEで連絡した",
    "confirmed_awake": "電話で起床を確認",
    "no_answer": "電話がつながらない",
    "site_notified": "現場へ連絡した",
    "absent": "欠勤",
}
# 連絡を終えたとみなす結果（「今すること」を出さない）
WAKE_CONTACT_RESOLVED = {"confirmed_awake", "absent"}


class WakeContactLog(Base):
    """起床の目視確認で、運営が連絡した結果（0.49.8、DEC-082）。追記のみ。"""

    __tablename__ = "wake_contact_logs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    contact_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[str] = mapped_column(String(26), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "result IN ('line_sent','confirmed_awake','no_answer','site_notified','absent')",
            name="ck_wake_contact_logs_result",
        ),
        Index("ix_wake_contact_logs_date_worker", "contact_date", "worker_id"),
    )


class LineActionToken(Base):
    """「続きを見る」「依頼書を開く」の短命トークン。平文は保存しない。"""

    __tablename__ = "line_action_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("action IN ('schedule_next', 'open_order')", name="ck_line_action_token_action"),
    )


class LineRichMenuRelease(Base):
    """リッチメニューの公開記録。最新の enabled_actions を「有効な機能」の正本にする。"""

    __tablename__ = "line_rich_menu_releases"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    rich_menu_id: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled_actions: Mapped[list] = mapped_column(JSON, nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_by: Mapped[str] = mapped_column(String(64), nullable=False)


class LineWorkerSession(Base):
    """稼働者向けLIFF画面の短いセッション（統合計画 ①）。IDトークン検証の後に発行する。平文は保存しない。

    登録用のセッション（line_registration_sessions）とは用途を分ける。各API呼び出しで連携と稼働者の状態を確認し直す。
    """

    __tablename__ = "line_worker_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_line_worker_sessions_token_hash"),
        Index("ix_line_worker_sessions_worker", "worker_id"),
    )


class LineWorkerSubmitKey(Base):
    """LIFF画面からの送信の冪等キー（統合計画 R-06）。同じ本人・同じキーの再送には最初の結果を返す。"""

    __tablename__ = "line_worker_submit_keys"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(26), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("worker_id", "idempotency_key", name="uq_line_worker_submit_key"),
        CheckConstraint("length(content_hash) = 64", name="ck_line_worker_submit_keys_hash"),
        CheckConstraint("action IN ('pick_dates')", name="ck_line_worker_submit_keys_action"),
    )


# 公開記録（line_rich_menu_releases.enabled_actions）に入れる業務機能のキー（統合計画 §3、R-02）。
# メニューのボタン（wk_*）と違い、押せる範囲を持たない。Web側のAPIはこの記録で判定する。
FEATURE_PICK_DATES = "pick_dates"
FEATURE_WEB_HOME = "web_home"
FEATURE_WEB_ORDERS = "web_orders"
FEATURE_CHANGE_REQUEST = "change_request"
FEATURE_KEYS = (FEATURE_PICK_DATES, FEATURE_WEB_HOME, FEATURE_WEB_ORDERS, FEATURE_CHANGE_REQUEST)
