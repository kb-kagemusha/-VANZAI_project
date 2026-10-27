"""Invitation-backed operator enrollment; existing registration header is the state owner."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class OperatorRegistrationDetail(Base):
    __tablename__ = "operator_registration_details"
    request_id: Mapped[str] = mapped_column(String(26), ForeignKey("registration_requests.id"), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    line_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    line_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (
        Index("uq_operator_registration_open_line", "line_user_id", unique=True,
              sqlite_where=text("is_open = 1 AND line_user_id IS NOT NULL"),
              postgresql_where=text("is_open AND line_user_id IS NOT NULL")),
    )
