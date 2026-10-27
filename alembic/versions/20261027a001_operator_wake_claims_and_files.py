"""運営用LINEの「私が連絡します」記録・依頼書リンク・現場管理の初期権限（0.53.8、DEC-125）。

- wake_contact_logs.result に claimed（連絡を引き受けた）を追加
- line_operator_file_tokens（運営が依頼書PDFを開く短命リンク）を追加
- 既に保存された「現場管理者」の権限設定があれば、発注依頼書の閲覧（order_read）を足す（ほかの権限は変えない）
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "20261027a001"
down_revision = "20261026b001"
branch_labels = None
depends_on = None

OLD_RESULTS = "result IN ('line_sent','confirmed_awake','no_answer','site_notified','absent')"
NEW_RESULTS = "result IN ('line_sent','confirmed_awake','no_answer','site_notified','absent','claimed')"


def _policies():
    return sa.table("role_access_policies", sa.column("role", sa.String), sa.column("permissions", sa.JSON))


def upgrade():
    with op.batch_alter_table("wake_contact_logs") as batch:
        batch.drop_constraint("ck_wake_contact_logs_result", type_="check")
        batch.create_check_constraint("ck_wake_contact_logs_result", NEW_RESULTS)
    op.create_table("line_operator_file_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("version_id", sa.String(26), sa.ForeignKey("order_request_versions.id"), nullable=False),
        sa.Column("staff_id", sa.String(26), sa.ForeignKey("vanzai_staff.id"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_operator_file_token_hash"))
    bind = op.get_bind()
    table = _policies()
    row = bind.execute(sa.select(table.c.permissions).where(table.c.role == "site_manager")).first()
    if row is not None:
        values = row[0]
        if isinstance(values, str):
            values = json.loads(values)
        values = list(values or [])
        if "order_read" not in values:
            bind.execute(table.update().where(table.c.role == "site_manager").values(permissions=sorted(values + ["order_read"])))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM wake_contact_logs WHERE result = 'claimed'")).scalar():
        raise RuntimeError("「連絡を引き受けた」の記録があるため戻せません")
    if bind.execute(sa.text("SELECT COUNT(*) FROM line_operator_file_tokens")).scalar():
        raise RuntimeError("運営の依頼書リンクの発行履歴があるため戻せません")
    op.drop_table("line_operator_file_tokens")
    with op.batch_alter_table("wake_contact_logs") as batch:
        batch.drop_constraint("ck_wake_contact_logs_result", type_="check")
        batch.create_check_constraint("ck_wake_contact_logs_result", OLD_RESULTS)
    # 現場管理の権限設定は戻さない（管理者が画面で決めた設定と区別できないため）
