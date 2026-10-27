"""Customer person-day prices and immutable daily amount lines; worker pay stays separate."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Date, DateTime, Numeric, JSON, Text, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class OrderBillingRateSetting(Base):
    __tablename__="order_billing_rate_settings"
    version_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_request_versions.id"),primary_key=True)
    project_id:Mapped[str]=mapped_column(String(26),ForeignKey("projects.id"),nullable=False)
    base_rate:Mapped[Decimal]=mapped_column(Numeric(15,2),nullable=False)
    weekday_rates:Mapped[dict]=mapped_column(JSON,nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    updated_by:Mapped[str]=mapped_column(String(26),ForeignKey("users.id"),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    __table_args__=(CheckConstraint("base_rate >= 0 AND revision > 0",name="ck_order_billing_daily_rate"),)


class OrderBillingDailyLine(Base):
    __tablename__="order_billing_daily_lines"
    amount_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_billing_amounts.id"),primary_key=True)
    work_date:Mapped[date]=mapped_column(Date,primary_key=True)
    quantity:Mapped[int]=mapped_column(Integer,nullable=False)
    unit_price:Mapped[Decimal]=mapped_column(Numeric(15,2),nullable=False)
    adjustment:Mapped[Decimal]=mapped_column(Numeric(15,2),nullable=False)
    adjustment_reason:Mapped[str]=mapped_column(Text,nullable=False)
    subtotal:Mapped[Decimal]=mapped_column(Numeric(18,2),nullable=False)
    source_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    __table_args__=(CheckConstraint("quantity >= 0 AND unit_price >= 0 AND subtotal >= 0",name="ck_order_billing_daily_values"),
        CheckConstraint("round(subtotal,2) = round(quantity * unit_price + adjustment,2)",name="ck_order_billing_daily_total"),)


class OrderBillingActualClaim(Base):
    """The same actual project/day cannot be billed under two different request series."""
    __tablename__="order_billing_actual_claims"
    project_id:Mapped[str]=mapped_column(String(26),ForeignKey("projects.id"),primary_key=True)
    work_date:Mapped[date]=mapped_column(Date,primary_key=True)
    series_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_request_series.id"),nullable=False)
    active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
