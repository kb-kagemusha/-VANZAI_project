"""Add User model for authentication and authorization

Revision ID: 003_add_users
Revises: 002_pricing_billing
Create Date: 2026-01-27

仕様参照: DESIGN_SPEC_v0.3 セクション5（ロールと権限）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_users'
down_revision: Union[str, None] = '002_pricing_billing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add users table for authentication and authorization"""
    
    op.create_table(
        'users',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='worker'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('worker_id', sa.String(26), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
    )
    
    # Indexes
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])


def downgrade() -> None:
    """Remove users table"""
    op.drop_index('ix_users_role', 'users')
    op.drop_index('ix_users_email', 'users')
    op.drop_index('ix_users_username', 'users')
    op.drop_table('users')
