"""A vacancy masks only one person's date; replacement invitations retain their own history."""
from datetime import date, datetime
from sqlalchemy import String, Integer, Date, DateTime, Text, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, generate_ulid


class StaffingVacancy(Base):
    __tablename__ = "staffing_vacancies"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    source_entry_id: Mapped[str] = mapped_column(String(26), ForeignKey("worker_schedule_entries.id"), nullable=False)
    source_series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    root_series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(26), ForeignKey("workers.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    expected_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("order_staffing_decisions.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('open','recruiting','filled','cancelled')", name="ck_staffing_vacancy_status"),
        CheckConstraint("expected_capacity > 0", name="ck_staffing_vacancy_capacity"),
        Index("uq_staffing_vacancy_active", "source_series_id", "worker_id", "work_date", unique=True,
            postgresql_where=text("status != 'cancelled'"), sqlite_where=text("status != 'cancelled'")),
        Index("ix_staffing_vacancy_root", "root_series_id", "work_date"),
    )


class StaffingRecruitment(Base):
    __tablename__ = "staffing_recruitments"
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    vacancy_id: Mapped[str] = mapped_column(String(26), ForeignKey("staffing_vacancies.id"), nullable=False, unique=True)
    series_id: Mapped[str] = mapped_column(String(26), ForeignKey("order_request_series.id"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
