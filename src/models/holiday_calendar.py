"""Shared holiday calendar; issued order versions keep their own date snapshot."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, generate_ulid


class HolidayCalendarDay(Base):
    __tablename__ = "holiday_calendar_days"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (CheckConstraint("revision > 0", name="ck_holiday_calendar_revision"),)


class HolidayCsvImport(Base):
    """One fetch of the Cabinet Office holiday CSV and its difference from the previous fetch."""

    __tablename__ = "holiday_csv_imports"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    coverage_start: Mapped[date] = mapped_column(Date, nullable=False)
    coverage_end: Mapped[date] = mapped_column(Date, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    added_days: Mapped[list] = mapped_column(JSON, nullable=False)
    removed_days: Mapped[list] = mapped_column(JSON, nullable=False)
    renamed_days: Mapped[list] = mapped_column(JSON, nullable=False)
    official_days: Mapped[dict] = mapped_column(JSON, nullable=False)
