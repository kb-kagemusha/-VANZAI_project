"""Add pricing and billing models

Revision ID: 002_pricing_billing
Revises: 001_initial
Create Date: 2026-01-26

仕様参照: DESIGN_SPEC_v0.3
- セクション7（単価設計）
- セクション11（請求書・支払の版管理）
- セクション12（締め）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_pricing_billing'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 単価マスタ
    op.create_table(
        'price_sales',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('role_id', sa.String(26), sa.ForeignKey('roles.id'), nullable=True),
        sa.Column('project_id', sa.String(26), nullable=True),
        sa.Column('client_id', sa.String(26), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_type', sa.String(20), nullable=False, default='hourly'),
        sa.Column('valid_from', sa.Date, nullable=True),
        sa.Column('valid_to', sa.Date, nullable=True),
        sa.Column('is_default', sa.Boolean, nullable=False, default=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    op.create_table(
        'price_outsource',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('worker_id', sa.String(26), sa.ForeignKey('workers.id'), nullable=True),
        sa.Column('role_id', sa.String(26), sa.ForeignKey('roles.id'), nullable=True),
        sa.Column('project_id', sa.String(26), nullable=True),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_type', sa.String(20), nullable=False, default='hourly'),
        sa.Column('valid_from', sa.Date, nullable=True),
        sa.Column('valid_to', sa.Date, nullable=True),
        sa.Column('is_default', sa.Boolean, nullable=False, default=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    op.create_table(
        'price_rules',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('priority', sa.Integer, nullable=False, default=100),
        sa.Column('conditions', sa.JSON, nullable=False),
        sa.Column('sales_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('outsource_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('valid_from', sa.Date, nullable=True),
        sa.Column('valid_to', sa.Date, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_price_rules_priority', 'price_rules', ['priority', 'is_active'])
    
    # 請求書
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('client_id', sa.String(26), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('period_key', sa.String(6), nullable=False),
        sa.Column('billing_date', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='preparing'),
        sa.Column('version', sa.Integer, nullable=False, default=1),
        sa.Column('parent_invoice_id', sa.String(26), sa.ForeignKey('invoices.id'), nullable=True),
        sa.Column('subtotal', sa.Numeric(15, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('pdf_object_key', sa.String(500), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_invoices_client_period', 'invoices', ['client_id', 'period_key'])
    op.create_index('ix_invoices_project_period', 'invoices', ['project_id', 'period_key'])
    op.create_index('ix_invoices_status', 'invoices', ['status'])
    
    op.create_table(
        'invoice_lines',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('invoice_id', sa.String(26), sa.ForeignKey('invoices.id'), nullable=False),
        sa.Column('line_number', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('actual_id', sa.String(26), sa.ForeignKey('actuals.id'), nullable=True),
        sa.Column('unit_price_snapshot', sa.Numeric(12, 2), nullable=False),
        sa.Column('quantity_snapshot', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit_type', sa.String(20), nullable=False),
        sa.Column('line_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_correction', sa.Boolean, nullable=False, default=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_invoice_lines_invoice', 'invoice_lines', ['invoice_id'])
    op.create_index('ix_invoice_lines_actual', 'invoice_lines', ['actual_id'])
    
    # 支払明細
    op.create_table(
        'payouts',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('worker_id', sa.String(26), sa.ForeignKey('workers.id'), nullable=False),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('period_key', sa.String(6), nullable=False),
        sa.Column('payment_date', sa.Date, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='preparing'),
        sa.Column('version', sa.Integer, nullable=False, default=1),
        sa.Column('parent_payout_id', sa.String(26), sa.ForeignKey('payouts.id'), nullable=True),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_payouts_worker_period', 'payouts', ['worker_id', 'period_key'])
    op.create_index('ix_payouts_project_period', 'payouts', ['project_id', 'period_key'])
    op.create_index('ix_payouts_status', 'payouts', ['status'])
    
    op.create_table(
        'payout_lines',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('payout_id', sa.String(26), sa.ForeignKey('payouts.id'), nullable=False),
        sa.Column('line_number', sa.Integer, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('actual_id', sa.String(26), sa.ForeignKey('actuals.id'), nullable=True),
        sa.Column('unit_price_snapshot', sa.Numeric(12, 2), nullable=False),
        sa.Column('quantity_snapshot', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit_type', sa.String(20), nullable=False),
        sa.Column('line_amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('is_correction', sa.Boolean, nullable=False, default=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_payout_lines_payout', 'payout_lines', ['payout_id'])
    op.create_index('ix_payout_lines_actual', 'payout_lines', ['actual_id'])
    
    # 締め管理
    op.create_table(
        'closings',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('project_id', sa.String(26), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('period_key', sa.String(6), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='open'),
        sa.Column('soft_closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('soft_closed_by', sa.String(100), nullable=True),
        sa.Column('hard_closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hard_closed_by', sa.String(100), nullable=True),
        sa.Column('release_count', sa.Integer, nullable=False, default=0),
        sa.Column('last_released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_released_by', sa.String(100), nullable=True),
        sa.Column('last_release_reason', sa.Text, nullable=True),
        sa.Column('reclose_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('project_id', 'period_key', name='uq_closing_project_period'),
    )
    op.create_index('ix_closings_period', 'closings', ['period_key'])
    op.create_index('ix_closings_status', 'closings', ['status'])


def downgrade() -> None:
    op.drop_table('closings')
    op.drop_table('payout_lines')
    op.drop_table('payouts')
    op.drop_table('invoice_lines')
    op.drop_table('invoices')
    op.drop_table('price_rules')
    op.drop_table('price_outsource')
    op.drop_table('price_sales')
