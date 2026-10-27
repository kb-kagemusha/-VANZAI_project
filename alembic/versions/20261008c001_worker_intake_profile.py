"""稼働者登録ポップアップのプロフィール項目

Revision ID: 20261008c001
Revises: 20261008b001
Create Date: 2026-10-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008c001"
down_revision: Union[str, None] = "20261008b001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("workers", sa.Column("marital_status", sa.String(length=10), nullable=True))
    op.add_column("workers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("hometown", sa.String(length=100), nullable=True))
    op.add_column("workers", sa.Column("nearest_station", sa.String(length=100), nullable=True))
    op.add_column("workers", sa.Column("station_walk_minutes", sa.Integer(), nullable=True))
    op.add_column("workers", sa.Column("final_education", sa.String(length=200), nullable=True))
    op.add_column("workers", sa.Column("licenses_qualifications", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("car_drive_ok", sa.Boolean(), nullable=True))
    op.add_column("workers", sa.Column("hiace_drive_ok", sa.Boolean(), nullable=True))
    op.add_column("workers", sa.Column("truck_drive", sa.String(length=10), nullable=True))
    op.add_column("workers", sa.Column("work_history", sa.JSON(), nullable=True))
    op.add_column("workers", sa.Column("ploomx_sales_experience", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("smoking_ok", sa.Boolean(), nullable=True))
    op.add_column("workers", sa.Column("lucky_self", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("hobbies", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("personality_strengths", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("personality_weaknesses", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("club_activity", sa.String(length=100), nullable=True))
    op.add_column("workers", sa.Column("motivation", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("self_pr", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("life_goal", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("desired_income", sa.String(length=100), nullable=True))
    op.add_column("workers", sa.Column("available_days_per_week", sa.Integer(), nullable=True))
    op.add_column("workers", sa.Column("available_weekdays", sa.JSON(), nullable=True))
    op.add_column("workers", sa.Column("available_time_from", sa.String(length=5), nullable=True))
    op.add_column("workers", sa.Column("available_time_to", sa.String(length=5), nullable=True))
    op.add_column("workers", sa.Column("available_start_date", sa.Date(), nullable=True))
    op.add_column("workers", sa.Column("payment_terms_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("workers", "payment_terms_ok")
    op.drop_column("workers", "available_start_date")
    op.drop_column("workers", "available_time_to")
    op.drop_column("workers", "available_time_from")
    op.drop_column("workers", "available_weekdays")
    op.drop_column("workers", "available_days_per_week")
    op.drop_column("workers", "desired_income")
    op.drop_column("workers", "life_goal")
    op.drop_column("workers", "self_pr")
    op.drop_column("workers", "motivation")
    op.drop_column("workers", "club_activity")
    op.drop_column("workers", "personality_weaknesses")
    op.drop_column("workers", "personality_strengths")
    op.drop_column("workers", "hobbies")
    op.drop_column("workers", "lucky_self")
    op.drop_column("workers", "smoking_ok")
    op.drop_column("workers", "ploomx_sales_experience")
    op.drop_column("workers", "work_history")
    op.drop_column("workers", "truck_drive")
    op.drop_column("workers", "hiace_drive_ok")
    op.drop_column("workers", "car_drive_ok")
    op.drop_column("workers", "licenses_qualifications")
    op.drop_column("workers", "final_education")
    op.drop_column("workers", "station_walk_minutes")
    op.drop_column("workers", "nearest_station")
    op.drop_column("workers", "hometown")
    op.drop_column("workers", "address")
    op.drop_column("workers", "marital_status")
    op.drop_column("workers", "birth_date")
