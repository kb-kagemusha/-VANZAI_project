"""Daily headcount and operator decisions; existing accepted requests stay legacy."""
from datetime import date, datetime
from sqlalchemy import String, Integer, Date, DateTime, Boolean, Text, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, generate_ulid


class StaffingRound(Base):
    __tablename__ = "order_staffing_rounds"
    version_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_versions.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StaffingLimit(Base):
    __tablename__ = "order_staffing_limits"
    version_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_staffing_rounds.version_id"), primary_key=True)
    work_date: Mapped[date] = mapped_column(Date, primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("capacity >= 0", name="ck_staffing_capacity"),)


class StaffingDecision(Base):
    __tablename__ = "order_staffing_decisions"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    version_id: Mapped[str] = mapped_column(String(26), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decided_by: Mapped[str] = mapped_column(String(100), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["version_id", "work_date"], ["order_staffing_limits.version_id", "order_staffing_limits.work_date"]),
        UniqueConstraint("version_id", "worker_id", "work_date", name="uq_staffing_worker_day"),
        CheckConstraint("status IN ('confirmed','not_selected','vacant')", name="ck_staffing_decision_status"),
    )


class StaffingNotice(Base):
    __tablename__ = "order_staffing_notices"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    version_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_staffing_rounds.version_id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("version_id", "worker_id", "work_date", "kind", name="uq_staffing_notice"),
        CheckConstraint("kind IN ('confirmed','closed')", name="ck_staffing_notice_kind"),
        CheckConstraint("status IN ('pending','sent','failed','cancelled','skipped')", name="ck_staffing_notice_status"),
    )
