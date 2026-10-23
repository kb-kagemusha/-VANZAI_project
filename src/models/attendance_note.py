"""現場からの遅刻・キャンセル報告。金額・予定とは独立した確認資料（DEC-090）。"""
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, generate_ulid


class AttendanceNote(Base, TimestampMixin):
    __tablename__ = "attendance_notes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    schedule_entry_id: Mapped[str] = mapped_column(String(26), ForeignKey("worker_schedule_entries.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    worker_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    cause: Mapped[str] = mapped_column(String(20), nullable=False)
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reported_by: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("kind IN ('late', 'cancel')", name="ck_attendance_notes_kind"),
        CheckConstraint("cause IN ('personal', 'weather', 'other')", name="ck_attendance_notes_cause"),
        CheckConstraint("(kind = 'late' AND late_minutes IS NOT NULL AND late_minutes BETWEEN 1 AND 10080) OR (kind = 'cancel' AND late_minutes IS NULL)", name="ck_attendance_notes_minutes"),
        CheckConstraint("length(trim(reason)) > 0 AND length(trim(reported_by)) > 0", name="ck_attendance_notes_reason"),
        CheckConstraint("(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL AND length(trim(void_reason)) > 0)", name="ck_attendance_notes_void"),
        Index("ix_attendance_notes_worker_date", "worker_id", "work_date"),
        Index("ix_attendance_notes_series_date", "series_id", "work_date"),
        Index("uq_attendance_notes_active", "series_id", "worker_id", "work_date", "kind", unique=True,
              sqlite_where=text("voided_at IS NULL"), postgresql_where=text("voided_at IS NULL")),
    )
