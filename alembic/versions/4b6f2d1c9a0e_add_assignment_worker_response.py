"""add assignment worker response

Revision ID: 4b6f2d1c9a0e
Revises: f2c1a7b9d4e8, ff166af0ba6d
Create Date: 2026-04-01 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b6f2d1c9a0e'
down_revision: Union[str, tuple[str, str], None] = ('f2c1a7b9d4e8', 'ff166af0ba6d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assignments', sa.Column('worker_response_status', sa.String(length=20), nullable=True))
    op.add_column('assignments', sa.Column('worker_response_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assignments', sa.Column('worker_response_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('assignments', sa.Column('worker_response_note', sa.Text(), nullable=True))
    op.create_index('ix_assignments_worker_response_status', 'assignments', ['worker_response_status'], unique=False)

    assignment_table = sa.table(
        'assignments',
        sa.column('status', sa.String(length=20)),
        sa.column('worker_response_status', sa.String(length=20)),
        sa.column('worker_response_requested_at', sa.DateTime(timezone=True)),
    )
    op.execute(
        assignment_table.update()
        .where(assignment_table.c.status != 'canceled')
        .values(
            worker_response_status='pending',
            worker_response_requested_at=sa.text('CURRENT_TIMESTAMP'),
        )
    )


def downgrade() -> None:
    op.drop_index('ix_assignments_worker_response_status', table_name='assignments')
    op.drop_column('assignments', 'worker_response_note')
    op.drop_column('assignments', 'worker_response_at')
    op.drop_column('assignments', 'worker_response_requested_at')
    op.drop_column('assignments', 'worker_response_status')