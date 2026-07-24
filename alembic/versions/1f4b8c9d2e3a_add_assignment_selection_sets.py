"""add assignment selection sets

Revision ID: 1f4b8c9d2e3a
Revises: e1f2a3b4c5d6
Create Date: 2026-03-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f4b8c9d2e3a'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assignment_selection_sets',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('period_key', sa.String(length=6), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=26), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('assignment_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_assignment_selection_sets_period_key', 'assignment_selection_sets', ['period_key'], unique=False)
    op.create_index('ix_assignment_selection_sets_created_by_user_id', 'assignment_selection_sets', ['created_by_user_id'], unique=False)
    op.create_index('ix_assignment_selection_sets_shared_period', 'assignment_selection_sets', ['is_shared', 'period_key'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_assignment_selection_sets_shared_period', table_name='assignment_selection_sets')
    op.drop_index('ix_assignment_selection_sets_created_by_user_id', table_name='assignment_selection_sets')
    op.drop_index('ix_assignment_selection_sets_period_key', table_name='assignment_selection_sets')
    op.drop_table('assignment_selection_sets')
