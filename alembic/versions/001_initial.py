"""Initial schema - Sprint1 MVP

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-26

仕様参照: DESIGN_SPEC_v0.3
- セクション6.1, 6.2, 6.3（エンティティ定義）
- セクション8.1（時間計算設定）
- セクション9.4, 9.5, 9.6（CSV取り込み）
- セクション16（監査ログ）
- DEC-001, DEC-002, DEC-003（DECISION_LOG）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===================
    # マスタテーブル
    # ===================
    
    # workers（稼働者）
    op.create_table(
        'workers',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # clients（クライアント）
    op.create_table(
        'clients',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('contact_name', sa.String(100), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('code', name='uq_clients_code'),
    )
    
    # sites（現場）
    op.create_table(
        'sites',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('code', name='uq_sites_code'),
    )
    
    # project_types（案件種別）
    op.create_table(
        'project_types',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('code', name='uq_project_types_code'),
    )
    
    # roles（役割）
    op.create_table(
        'roles',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('code', name='uq_roles_code'),
    )
    
    # ===================
    # トランザクションテーブル
    # ===================
    
    # projects（案件）- 仕様6.1, 8.1
    op.create_table(
        'projects',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('client_id', sa.String(26), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('site_id', sa.String(26), sa.ForeignKey('sites.id'), nullable=True),
        sa.Column('project_type_id', sa.String(26), sa.ForeignKey('project_types.id'), nullable=True),
        sa.Column('start_date', sa.Date, nullable=True),
        sa.Column('end_date', sa.Date, nullable=True),
        # 時間計算設定（仕様8.1）
        sa.Column('rounding_unit_minutes', sa.Integer, nullable=False, default=15),
        sa.Column('rounding_method', sa.String(20), nullable=False, default='ceil'),
        sa.Column('break_deduction_rule', sa.String(20), nullable=False, default='auto'),
        sa.Column('time_calc_mode', sa.String(30), nullable=False, default='system_first'),
        sa.Column('night_window_start', sa.Time, nullable=True),
        sa.Column('night_window_end', sa.Time, nullable=True),
        sa.Column('night_calc_mode', sa.String(20), nullable=False, default='store_minutes'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('code', name='uq_projects_code'),
    )
    op.create_index('ix_projects_client_id', 'projects', ['client_id'])
    op.create_index('ix_projects_is_active', 'projects', ['is_active'])
    
    # shift_slots（シフト枠）
    op.create_table(
        'shift_slots',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('work_date', sa.Date, nullable=False),
        sa.Column('start_time', sa.Time, nullable=True),
        sa.Column('end_time', sa.Time, nullable=True),
        sa.Column('shift_label', sa.String(50), nullable=True),
        sa.Column('required_count', sa.Integer, nullable=False, default=1),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_shift_slots_project_date', 'shift_slots', ['project_id', 'work_date'])
    op.create_index('ix_shift_slots_work_date', 'shift_slots', ['work_date'])
    
    # assignments（アサイン）- 仕様6.2, 10.2
    op.create_table(
        'assignments',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('shift_slot_id', sa.String(26), sa.ForeignKey('shift_slots.id'), nullable=False),
        sa.Column('worker_id', sa.String(26), sa.ForeignKey('workers.id'), nullable=False),
        sa.Column('role_id', sa.String(26), sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='tentative'),
        sa.Column('cancel_reason', sa.Text, nullable=True),
        sa.Column('locked_price_sales', sa.Numeric(12, 2), nullable=True),
        sa.Column('locked_price_outsource', sa.Numeric(12, 2), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('shift_slot_id', 'worker_id', name='uq_assignment_slot_worker'),
    )
    op.create_index('ix_assignments_worker_id', 'assignments', ['worker_id'])
    op.create_index('ix_assignments_status', 'assignments', ['status'])
    
    # import_batches（取り込みバッチ）- 仕様9.4, 9.5, DEC-001
    op.create_table(
        'import_batches',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('submitted_by', sa.String(100), nullable=True),
        sa.Column('submit_channel', sa.String(50), nullable=False, default='system_upload'),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('period_key', sa.String(6), nullable=False),  # YYYYMM (DEC-002)
        sa.Column('mode', sa.String(30), nullable=False, default='replace_scope'),
        sa.Column('scope_type', sa.String(30), nullable=True, default='project_month'),
        sa.Column('status', sa.String(20), nullable=False, default='processing'),
        sa.Column('count_success', sa.Integer, nullable=False, default=0),
        sa.Column('count_error', sa.Integer, nullable=False, default=0),
        sa.Column('count_skip', sa.Integer, nullable=False, default=0),
        sa.Column('count_superseded', sa.Integer, nullable=False, default=0),
        sa.Column('errors_json', sa.JSON, nullable=True),
        sa.Column('has_row_count_warning', sa.Boolean, nullable=False, default=False),
        sa.Column('has_total_time_warning', sa.Boolean, nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        # 二重取込防止（DEC-001）
        sa.UniqueConstraint('file_hash', 'project_id', 'period_key', name='uq_import_batch_hash_project_period'),
    )
    op.create_index('ix_import_batches_project_period', 'import_batches', ['project_id', 'period_key'])
    op.create_index('ix_import_batches_status', 'import_batches', ['status'])
    
    # actuals（実績）- 仕様6.2, 6.3
    op.create_table(
        'actuals',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('worker_id', sa.String(26), sa.ForeignKey('workers.id'), nullable=False),
        sa.Column('role_id', sa.String(26), sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('assignment_id', sa.String(26), sa.ForeignKey('assignments.id'), nullable=True),  # DEC-003
        sa.Column('import_batch_id', sa.String(26), sa.ForeignKey('import_batches.id'), nullable=False),
        sa.Column('work_date', sa.Date, nullable=False),
        sa.Column('period_key', sa.String(6), nullable=False),  # YYYYMM (DEC-002)
        # ステータス（仕様6.2, 6.3 - 不変条件: 集計対象はactiveのみ）
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('invalid_reason', sa.Text, nullable=True),
        # 時間（生データ）
        sa.Column('start_time', sa.Time, nullable=True),
        sa.Column('end_time', sa.Time, nullable=True),
        sa.Column('break_minutes_input', sa.Integer, nullable=True),
        sa.Column('hours_input', sa.Numeric(5, 2), nullable=True),
        # 計算結果（仕様8.2 - スナップショット）
        sa.Column('calc_minutes_total', sa.Integer, nullable=False),
        sa.Column('calc_minutes_break', sa.Integer, nullable=False),
        sa.Column('calc_minutes_billable', sa.Integer, nullable=False),
        sa.Column('calc_minutes_night', sa.Integer, nullable=True),
        # 計算ルール記録
        sa.Column('calc_rounding_unit', sa.Integer, nullable=True),
        sa.Column('calc_rounding_method', sa.String(20), nullable=True),
        sa.Column('calc_break_rule', sa.String(20), nullable=True),
        # 単価スナップショット（仕様6.2, 7.3 - 必須）
        sa.Column('applied_price_sales', sa.Numeric(12, 2), nullable=False),
        sa.Column('applied_price_outsource', sa.Numeric(12, 2), nullable=False),
        # 外部参照キー
        sa.Column('external_row_key', sa.String(100), nullable=True),
        # 差分確認フラグ
        sa.Column('needs_review', sa.Boolean, nullable=False, default=False),
        sa.Column('review_reason', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    # 集計・検索用インデックス
    op.create_index('ix_actuals_status', 'actuals', ['status'])
    op.create_index('ix_actuals_project_date', 'actuals', ['project_id', 'work_date'])
    op.create_index('ix_actuals_project_period', 'actuals', ['project_id', 'period_key'])
    op.create_index('ix_actuals_project_date_worker', 'actuals', ['project_id', 'work_date', 'worker_id'])
    op.create_index('ix_actuals_worker_period', 'actuals', ['worker_id', 'period_key'])
    op.create_index('ix_actuals_import_batch', 'actuals', ['import_batch_id'])
    op.create_index('ix_actuals_external_key', 'actuals', ['external_row_key'])
    
    # audit_logs（監査ログ）- 仕様16章
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=True),
        sa.Column('target_id', sa.String(26), nullable=True),
        sa.Column('actor', sa.String(100), nullable=True),
        sa.Column('actor_role', sa.String(50), nullable=True),
        sa.Column('before_value', sa.JSON, nullable=True),
        sa.Column('after_value', sa.JSON, nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('extra_metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_target', 'audit_logs', ['target_type', 'target_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('actuals')
    op.drop_table('import_batches')
    op.drop_table('assignments')
    op.drop_table('shift_slots')
    op.drop_table('projects')
    op.drop_table('roles')
    op.drop_table('project_types')
    op.drop_table('sites')
    op.drop_table('clients')
    op.drop_table('workers')
