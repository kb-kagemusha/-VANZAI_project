"""add worker availability

Revision ID: f2c1a7b9d4e8
Revises: e7b1d3c4a5f6
Create Date: 2026-04-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c1a7b9d4e8'
down_revision: Union[str, None] = 'e7b1d3c4a5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'worker_availability',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('worker_id', sa.String(length=26), nullable=False),
        sa.Column('availability_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='undecided'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('worker_id', 'availability_date', name='uq_worker_availability_worker_date'),
    )
    op.create_index('ix_worker_availability_worker_date', 'worker_availability', ['worker_id', 'availability_date'], unique=False)
    op.create_index('ix_worker_availability_status', 'worker_availability', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_worker_availability_status', table_name='worker_availability')
    op.drop_index('ix_worker_availability_worker_date', table_name='worker_availability')
    op.drop_table('worker_availability')