"""起床の監視の送信記録と、現場管理の「起床報告が無い場合の連絡受け取り」（0.54.0、DEC-126）。"""
import json

from alembic import op
import sqlalchemy as sa

revision = "20261027b001"
down_revision = "20261027a001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("wake_monitor_sends",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("worker_id", "work_date", "kind", "round", "recipient", name="uq_wake_monitor_sends_key"),
        sa.CheckConstraint("kind IN ('worker_reminder','operator_alert','operator_claimed','operator_reported')", name="ck_wake_monitor_sends_kind"),
        sa.CheckConstraint("status IN ('pending','sent','failed','skipped')", name="ck_wake_monitor_sends_status"))
    op.create_index("ix_wake_monitor_sends_date_worker", "wake_monitor_sends", ["work_date", "worker_id"])
    # 保存済みの現場管理・運用担当の権限設定があれば、起床の知らせの受け取りを足す（ほかは変えない）
    table = sa.table("role_access_policies", sa.column("role", sa.String), sa.column("permissions", sa.JSON))
    bind = op.get_bind()
    for role in ("site_manager", "ops"):
        row = bind.execute(sa.select(table.c.permissions).where(table.c.role == role)).first()
        if row is None:
            continue
        values = row[0]
        if isinstance(values, str):
            values = json.loads(values)
        values = list(values or [])
        if "wake_alert_receive" not in values:
            bind.execute(table.update().where(table.c.role == role).values(permissions=sorted(values + ["wake_alert_receive"])))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM wake_monitor_sends")).scalar():
        raise RuntimeError("起床の監視の送信記録があるため戻せません")
    op.drop_index("ix_wake_monitor_sends_date_worker", table_name="wake_monitor_sends")
    op.drop_table("wake_monitor_sends")
