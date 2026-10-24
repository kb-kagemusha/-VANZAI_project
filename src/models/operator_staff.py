"""Operator LINE identities. Worker and operator identities are verified separately."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, generate_ulid


class LineStaffLink(Base):
    __tablename__ = "line_staff_links"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    staff_id: Mapped[str] = mapped_column(String(26), ForeignKey("vanzai_staff.id"), nullable=False)
    line_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    line_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="ck_line_staff_links_status"),
        Index("uq_line_staff_active_staff", "staff_id", unique=True, sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
        Index("uq_line_staff_active_line_user", "line_user_id", unique=True, sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
    )


class LineStaffLinkCode(Base):
    __tablename__ = "line_staff_link_codes"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    staff_id: Mapped[str] = mapped_column(String(26), ForeignKey("vanzai_staff.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_line_staff_codes_staff", "staff_id"),)
