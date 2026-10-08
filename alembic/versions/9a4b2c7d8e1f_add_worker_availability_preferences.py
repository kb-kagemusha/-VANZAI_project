"""add worker availability preferences

Revision ID: 9a4b2c7d8e1f
Revises: f2c1a7b9d4e8
Create Date: 2026-04-01 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a4b2c7d8e1f'
down_revision: Union[str, None] = 'f2c1a7b9d4e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'worker_availability_preferences',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('worker_id', sa.String(length=26), nullable=False),
        sa.Column('weekly_default_statuses', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('holiday_default_status', sa.String(length=20), nullable=True),
        sa.Column('auto_apply_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('worker_id', name='uq_worker_availability_preferences_worker_id'),
    )
    op.create_index('ix_worker_availability_preferences_worker_id', 'worker_availability_preferences', ['worker_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_worker_availability_preferences_worker_id', table_name='worker_availability_preferences')
    op.drop_table('worker_availability_preferences')