"""add_project_manager_fields

Revision ID: a9c940728ad0
Revises: c2d8f4b9a7a1
Create Date: 2026-01-30 00:13:20.972815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c940728ad0'
down_revision: Union[str, None] = 'c2d8f4b9a7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite: Foreign key制約はmodel定義で管理し、マイグレーションではカラムのみ追加
    op.add_column('projects', sa.Column('primary_manager_id', sa.String(26), nullable=True))
    op.add_column('projects', sa.Column('secondary_manager_id', sa.String(26), nullable=True))
    op.create_index('ix_projects_primary_manager_id', 'projects', ['primary_manager_id'])
    op.create_index('ix_projects_secondary_manager_id', 'projects', ['secondary_manager_id'])


def downgrade() -> None:
    op.drop_index('ix_projects_secondary_manager_id', 'projects')
    op.drop_index('ix_projects_primary_manager_id', 'projects')
    op.drop_column('projects', 'secondary_manager_id')
    op.drop_column('projects', 'primary_manager_id')
