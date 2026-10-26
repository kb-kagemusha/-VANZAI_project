"""LINE operator sessions and lifecycle menu reconciliation (DEC-119)."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, generate_ulid


class LineOperatorSession(Base):
    __tablename__ = "line_operator_sessions"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    link_id: Mapped[str] = mapped_column(String(26), ForeignKey("line_staff_links.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(26), ForeignKey("vanzai_staff.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("length(token_hash) = 64", name="ck_operator_session_hash"),)


class LineOperatorMenuRelease(Base):
    __tablename__ = "line_operator_menu_releases"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    menus: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


class LineOperatorMenuState(Base):
    __tablename__ = "line_operator_menu_states"
    line_user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_menu_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("status IN ('pending','applied','failed')", name="ck_operator_menu_status"),)
