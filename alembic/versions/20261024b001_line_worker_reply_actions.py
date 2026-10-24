"""Allow Web reply actions in line_worker_submit_keys (統合計画 ③-C)."""
from alembic import op

revision = "20261024b001"
down_revision = "20261024a001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("line_worker_submit_keys") as batch:
        batch.drop_constraint("ck_line_worker_submit_keys_action", type_="check")
        batch.create_check_constraint("ck_line_worker_submit_keys_action", "action IN ('pick_dates','reply_accept','reply_decline')")


def downgrade():
    # Web画面からの返事の記録が残っていると、旧い制約に戻せない
    from sqlalchemy import text

    if op.get_bind().execute(text("SELECT COUNT(*) FROM line_worker_submit_keys WHERE action <> 'pick_dates'")).scalar():
        raise RuntimeError("Web画面からの返事の記録があるため、安全に戻せません")
    with op.batch_alter_table("line_worker_submit_keys") as batch:
        batch.drop_constraint("ck_line_worker_submit_keys_action", type_="check")
        batch.create_check_constraint("ck_line_worker_submit_keys_action", "action IN ('pick_dates')")
