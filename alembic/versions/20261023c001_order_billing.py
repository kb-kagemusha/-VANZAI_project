"""Admin-only amount snapshots and monthly invoices (DEC-074)."""
from alembic import op
import sqlalchemy as sa

revision = "20261023c001"
down_revision = "20261023b001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('order_billing_issuer',
        sa.Column('id', sa.String(20), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('postal_code', sa.String(20), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('registration_number', sa.String(50), nullable=False),
        sa.Column('bank_details', sa.Text(), nullable=False),
        sa.Column('payment_terms', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 'default' AND revision > 0", name='ck_order_billing_issuer_singleton'))
    issuer = sa.table('order_billing_issuer', sa.column('id', sa.String), sa.column('revision', sa.Integer),
        sa.column('name', sa.String), sa.column('postal_code', sa.String), sa.column('address', sa.String),
        sa.column('registration_number', sa.String), sa.column('bank_details', sa.String), sa.column('payment_terms', sa.String))
    op.bulk_insert(issuer, [{'id': 'default', 'revision': 1, 'name': '株式会社VANZAI', 'postal_code': '116-0002',
        'address': '東京都荒川区荒川1丁目39-11 東京アルバタワー1703', 'registration_number': '', 'bank_details': '', 'payment_terms': ''}])
    op.create_table('order_billing_tax_rules',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('rate', sa.Numeric(precision=6, scale=4), nullable=False),
    sa.Column('rounding', sa.String(length=20), nullable=False),
    sa.CheckConstraint("rounding = 'floor_yen'", name='ck_order_billing_rounding'),
    sa.CheckConstraint('rate >= 0 AND rate <= 1', name='ck_order_billing_tax_rate'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('order_billing_amounts',
    sa.Column('id', sa.String(length=26), nullable=False),
    sa.Column('version_id', sa.String(length=26), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.String(length=26), nullable=False),
    sa.Column('billing_month', sa.String(length=6), nullable=False),
    sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_by_user_id', sa.String(length=26), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('amount >= 0 AND revision > 0', name='ck_order_billing_amount'),
    sa.CheckConstraint('length(billing_month) = 6', name='ck_order_billing_month'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['version_id'], ['order_request_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'revision', name='uq_order_billing_amount_revision')
    )
    op.create_index('ix_order_billing_amount_client_month', 'order_billing_amounts', ['client_id', 'billing_month'], unique=False)
    op.create_table('order_billing_invoices',
    sa.Column('id', sa.String(length=26), nullable=False),
    sa.Column('document_number', sa.String(length=60), nullable=False),
    sa.Column('client_id', sa.String(length=26), nullable=False),
    sa.Column('billing_month', sa.String(length=6), nullable=False),
    sa.Column('billing_date', sa.Date(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('parent_invoice_id', sa.String(length=26), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('client_snapshot', sa.JSON(), nullable=False),
    sa.Column('issuer_snapshot', sa.JSON(), nullable=False),
    sa.Column('tax_rule_id', sa.String(length=40), nullable=False),
    sa.Column('tax_rate', sa.Numeric(precision=6, scale=4), nullable=False),
    sa.Column('tax_rounding', sa.String(length=20), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=20, scale=2), nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=20, scale=2), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=20, scale=2), nullable=False),
    sa.Column('pdf_object_key', sa.String(length=500), nullable=True),
    sa.Column('created_by_user_id', sa.String(length=26), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('draft', 'issued', 'cancelled')", name='ck_order_billing_invoice_status'),
    sa.CheckConstraint('subtotal >= 0 AND tax_amount >= 0 AND total_amount = subtotal + tax_amount AND version > 0', name='ck_order_billing_invoice_totals'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_invoice_id'], ['order_billing_invoices.id'], ),
    sa.ForeignKeyConstraint(['tax_rule_id'], ['order_billing_tax_rules.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('client_id', 'billing_month', 'version', name='uq_order_billing_invoice_version'),
    sa.UniqueConstraint('document_number')
    )
    op.create_index('uq_order_billing_invoice_active', 'order_billing_invoices', ['client_id', 'billing_month'], unique=True, postgresql_where=sa.text("status <> 'cancelled'"), sqlite_where=sa.text("status <> 'cancelled'"))
    op.create_table('order_billing_invoice_lines',
    sa.Column('id', sa.String(length=26), nullable=False),
    sa.Column('invoice_id', sa.String(length=26), nullable=False),
    sa.Column('amount_id', sa.String(length=26), nullable=False),
    sa.Column('series_id', sa.String(length=26), nullable=False),
    sa.Column('active_series_id', sa.String(length=26), nullable=True),
    sa.Column('line_number', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('document_number', sa.String(length=40), nullable=False),
    sa.Column('work_date_label', sa.Text(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
    sa.CheckConstraint('active_series_id IS NULL OR active_series_id = series_id', name='ck_order_billing_line_claim'),
    sa.CheckConstraint('amount >= 0 AND line_number > 0', name='ck_order_billing_line'),
    sa.ForeignKeyConstraint(['active_series_id'], ['order_request_series.id'], ),
    sa.ForeignKeyConstraint(['amount_id'], ['order_billing_amounts.id'], ),
    sa.ForeignKeyConstraint(['invoice_id'], ['order_billing_invoices.id'], ),
    sa.ForeignKeyConstraint(['series_id'], ['order_request_series.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('active_series_id'),
    sa.UniqueConstraint('invoice_id', 'line_number', name='uq_order_billing_line_number')
    )
    # ### end Alembic commands ###
    op.execute(sa.text("INSERT INTO order_billing_tax_rules (id, rate, rounding) VALUES ('standard-10-floor-v1', 0.10, 'floor_yen')"))

def downgrade():
    for name in ("order_billing_invoice_lines", "order_billing_invoices", "order_billing_amounts", "order_billing_tax_rules", "order_billing_issuer"):
        op.drop_table(name)
