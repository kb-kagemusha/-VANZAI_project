"""add payout deliveries

Revision ID: c4a8d0b9e12f
Revises: 8b71d2f4c6a9
Create Date: 2026-03-31 01:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a8d0b9e12f'
down_revision: Union[str, None] = '8b71d2f4c6a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payout_deliveries',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('payout_id', sa.String(length=26), nullable=False),
        sa.Column('delivery_method', sa.String(length=20), nullable=False, server_default='email'),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('delivered_by', sa.String(length=100), nullable=True),
        sa.Column('pdf_object_key_snapshot', sa.String(length=500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['payout_id'], ['payouts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payout_deliveries_payout', 'payout_deliveries', ['payout_id'], unique=False)
    op.create_index('ix_payout_deliveries_status', 'payout_deliveries', ['status'], unique=False)
    op.create_index('ix_payout_deliveries_sent_at', 'payout_deliveries', ['sent_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_payout_deliveries_sent_at', table_name='payout_deliveries')
    op.drop_index('ix_payout_deliveries_status', table_name='payout_deliveries')
    op.drop_index('ix_payout_deliveries_payout', table_name='payout_deliveries')
    op.drop_table('payout_deliveries')