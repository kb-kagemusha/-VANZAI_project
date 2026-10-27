"""Optional station information on worker registration requests.

Revision ID: 20261012a001
Revises: 20261011a001
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012a001"
down_revision = "20261011a001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("worker_registration_request_details", sa.Column("nearest_station", sa.String(100), nullable=True))
    op.add_column("worker_registration_request_details", sa.Column("station_walk_minutes", sa.Integer(), nullable=True))
    with op.batch_alter_table("worker_registration_request_details") as batch:
        batch.create_check_constraint("ck_worker_registration_station_walk", "station_walk_minutes IS NULL OR (station_walk_minutes >= 0 AND station_walk_minutes <= 300)")


def downgrade():
    with op.batch_alter_table("worker_registration_request_details") as batch:
        batch.drop_constraint("ck_worker_registration_station_walk", type_="check")
    op.drop_column("worker_registration_request_details", "station_walk_minutes")
    op.drop_column("worker_registration_request_details", "nearest_station")
