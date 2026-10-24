"""add_staff_notices

Revision ID: a1b2c3d4e5f6
Revises: 469d72cd9e1a
Create Date: 2026-04-03 00:00:00.000000

スタッフ通知テーブルを追加する
- staff_notices: 管理者が作成する通知レコード
- staff_notice_reads: 稼働者の既読記録
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0d6b395ae7ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'staff_notices',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('notice_type', sa.String(30), nullable=False, server_default='general'),
        sa.Column('priority', sa.String(10), nullable=False, server_default='normal'),
        sa.Column('target_type', sa.String(20), nullable=False, server_default='all'),
        sa.Column('target_project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('target_worker_ids', sa.JSON, nullable=True),
        sa.Column('send_email', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(26), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'staff_notice_reads',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('notice_id', sa.String(26), sa.ForeignKey('staff_notices.id'), nullable=False),
        sa.Column('worker_id', sa.String(26), sa.ForeignKey('workers.id'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('notice_id', 'worker_id', name='uq_staff_notice_reads_notice_worker'),
    )

    op.create_index('ix_staff_notices_created_at', 'staff_notices', ['created_at'])
    op.create_index('ix_staff_notice_reads_worker_id', 'staff_notice_reads', ['worker_id'])


def downgrade() -> None:
    op.drop_index('ix_staff_notice_reads_worker_id', table_name='staff_notice_reads')
    op.drop_index('ix_staff_notices_created_at', table_name='staff_notices')
    op.drop_table('staff_notice_reads')
    op.drop_table('staff_notices')
