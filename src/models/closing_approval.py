"""Authenticated second-person decisions for closing transitions."""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin, generate_ulid


class ClosingApprovalRequest(Base, TimestampMixin):
    __tablename__ = "closing_approval_requests"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("projects.id"), nullable=False)
    period_key: Mapped[str] = mapped_column(String(6), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expected_status: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_release_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("action IN ('hard_close','soft_release','hard_release')", name="ck_closing_approval_action"),
        CheckConstraint("status IN ('pending','approved','expired','rejected')", name="ck_closing_approval_status"),
        CheckConstraint("approved_by IS NULL OR approved_by <> requested_by", name="ck_closing_approval_two_people"),
        CheckConstraint("status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)", name="ck_closing_approval_complete"),
        Index("uq_closing_approval_pending", "project_id", "period_key", "action", unique=True,
              postgresql_where=text("status = 'pending'"), sqlite_where=text("status = 'pending'")),
    )
