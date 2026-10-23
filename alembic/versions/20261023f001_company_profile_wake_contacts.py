"""Company profile fields, invoice issuer snapshot, wake contact logs (DEC-082)."""
from alembic import op
import sqlalchemy as sa

revision = "20261023f001"
down_revision = "20261023e001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("order_billing_issuer") as batch:
        batch.add_column(sa.Column("phone", sa.String(30), nullable=False, server_default=""))
        batch.add_column(sa.Column("email", sa.String(200), nullable=False, server_default=""))
        batch.add_column(sa.Column("representative", sa.String(100), nullable=False, server_default=""))
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("issuer_snapshot", sa.JSON(), nullable=True))
    op.create_table(
        "wake_contact_logs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("contact_date", sa.Date(), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.String(26), nullable=False),
        sa.Column("actor_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result IN ('line_sent','confirmed_awake','no_answer','site_notified','absent')",
            name="ck_wake_contact_logs_result",
        ),
    )
    op.create_index("ix_wake_contact_logs_date_worker", "wake_contact_logs", ["contact_date", "worker_id"])


def downgrade():
    # 連絡の記録・発行済み請求書の発行元を消すことになるため、記録があるときは戻さない。
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM wake_contact_logs")).scalar():
        raise RuntimeError("起床の連絡の記録があるため、安全に戻せません")
    if bind.execute(sa.text("SELECT COUNT(*) FROM invoices WHERE issuer_snapshot IS NOT NULL")).scalar():
        raise RuntimeError("発行元を保存した請求書があるため、安全に戻せません")
    op.drop_index("ix_wake_contact_logs_date_worker", table_name="wake_contact_logs")
    op.drop_table("wake_contact_logs")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("issuer_snapshot")
    with op.batch_alter_table("order_billing_issuer") as batch:
        batch.drop_column("representative")
        batch.drop_column("email")
        batch.drop_column("phone")
