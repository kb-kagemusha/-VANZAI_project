"""Order request series, participation states, worker schedules, wake reports (DEC-063/064, A1).

既存データの扱い:
- 依頼書ごとに系列を1つ作る（系列IDは依頼書ID）。A1以前の「変更を作成」は別系列のまま（正式運用前のため）。
- 回答受付版は、系列内で最後に確定した版が確定状態ならその版。取消済みなら NULL。
- 既存の送付行の offered_dates は NULL（稼働予定の対象外）。稼働予定は作らない。
"""
from alembic import op
import sqlalchemy as sa

revision = "20261022a002"
down_revision = "20261022a001"
branch_labels = None
depends_on = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "order_request_series",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("answerable_version_id", sa.String(26), nullable=True),
        *_ts(),
    )

    op.add_column("order_request_versions", sa.Column("series_id", sa.String(26), nullable=True))
    op.create_foreign_key(
        "fk_order_request_versions_series", "order_request_versions", "order_request_series", ["series_id"], ["id"]
    )
    op.create_unique_constraint("uq_order_request_versions_id_document", "order_request_versions", ["id", "document_id"])
    op.create_unique_constraint("uq_order_request_versions_id_series", "order_request_versions", ["id", "series_id"])

    op.add_column("order_request_deliveries", sa.Column("offered_dates", sa.JSON(), nullable=True))
    op.add_column("order_request_deliveries", sa.Column("current_participation_state_id", sa.String(26), nullable=True))
    op.create_unique_constraint("uq_order_request_deliveries_id_worker", "order_request_deliveries", ["id", "worker_id"])
    op.create_unique_constraint("uq_order_request_deliveries_id_version", "order_request_deliveries", ["id", "version_id"])

    op.create_table(
        "delivery_participation_states",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("delivery_id", sa.String(26), sa.ForeignKey("order_request_deliveries.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("dates", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("change_request_id", sa.String(26), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("delivery_id", "seq", name="uq_delivery_participation_seq"),
        sa.UniqueConstraint("id", "delivery_id", name="uq_delivery_participation_id_delivery"),
        sa.CheckConstraint("seq > 0", name="ck_delivery_participation_seq"),
        sa.CheckConstraint(
            "source IN ('full_accept', 'partial_accept', 'change_approved', 'ops_recorded_decline')",
            name="ck_delivery_participation_source",
        ),
    )

    op.create_table(
        "order_request_worker_applications",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("series_id", sa.String(26), sa.ForeignKey("order_request_series.id"), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("applied_delivery_id", sa.String(26), nullable=True),
        sa.Column("applied_version_id", sa.String(26), nullable=True),
        sa.Column("ended_reason", sa.String(40), nullable=True),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("series_id", "worker_id", name="uq_order_worker_application"),
        sa.CheckConstraint(
            "(applied_delivery_id IS NULL AND applied_version_id IS NULL)"
            " OR (applied_delivery_id IS NOT NULL AND applied_version_id IS NOT NULL)",
            name="ck_order_worker_application_pair",
        ),
        sa.CheckConstraint(
            "ended_reason IS NULL OR ended_reason IN "
            "('declined_new_version', 'removed_from_recipients', 'document_ended', 'view_revoked')",
            name="ck_order_worker_application_end",
        ),
        sa.ForeignKeyConstraint(
            ["applied_delivery_id", "worker_id"],
            ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
            name="fk_order_worker_application_delivery_worker",
        ),
        sa.ForeignKeyConstraint(
            ["applied_delivery_id", "applied_version_id"],
            ["order_request_deliveries.id", "order_request_deliveries.version_id"],
            name="fk_order_worker_application_delivery_version",
        ),
        sa.ForeignKeyConstraint(
            ["applied_version_id", "series_id"],
            ["order_request_versions.id", "order_request_versions.series_id"],
            name="fk_order_worker_application_version_series",
        ),
    )

    op.create_table(
        "worker_schedule_entries",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("series_id", sa.String(26), sa.ForeignKey("order_request_series.id"), nullable=False),
        sa.Column("document_id", sa.String(26), sa.ForeignKey("order_request_documents.id"), nullable=False),
        sa.Column("version_id", sa.String(26), nullable=False),
        sa.Column("delivery_id", sa.String(26), nullable=False),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("work_group_id", sa.String(64), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("end_next_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_reason", sa.String(40), nullable=True),
        sa.Column("source_state_id", sa.String(26), nullable=True),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("project_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("site_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("site_address", sa.Text(), nullable=True),
        sa.Column("meeting_place", sa.Text(), nullable=True),
        *_ts(),
        sa.UniqueConstraint("delivery_id", "work_group_id", "work_date", name="uq_worker_schedule_entry_key"),
        sa.CheckConstraint(
            "status IN ('active', 'changing', 'superseded', 'cancelled')", name="ck_worker_schedule_entry_status"
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "series_id"],
            ["order_request_versions.id", "order_request_versions.series_id"],
            name="fk_worker_schedule_entry_version_series",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "document_id"],
            ["order_request_versions.id", "order_request_versions.document_id"],
            name="fk_worker_schedule_entry_version_document",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id", "version_id"],
            ["order_request_deliveries.id", "order_request_deliveries.version_id"],
            name="fk_worker_schedule_entry_delivery_version",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id", "worker_id"],
            ["order_request_deliveries.id", "order_request_deliveries.worker_id"],
            name="fk_worker_schedule_entry_delivery_worker",
        ),
        sa.ForeignKeyConstraint(
            ["source_state_id", "delivery_id"],
            ["delivery_participation_states.id", "delivery_participation_states.delivery_id"],
            name="fk_worker_schedule_entry_state",
        ),
    )
    op.create_index("ix_worker_schedule_entries_worker_date", "worker_schedule_entries", ["worker_id", "work_date", "status"])
    op.create_index("ix_worker_schedule_entries_series", "worker_schedule_entries", ["series_id"])
    op.create_index("ix_worker_schedule_entries_document", "worker_schedule_entries", ["document_id"])

    op.create_table(
        "wake_reports",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("event_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late_received", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("line_event_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("worker_id", "report_date", "is_test", name="uq_wake_report_worker_date"),
    )
    op.create_index("ix_wake_reports_date", "wake_reports", ["report_date"])

    op.create_table(
        "line_action_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("worker_id", sa.String(26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('schedule_next', 'open_order')", name="ck_line_action_token_action"),
    )

    op.create_table(
        "line_rich_menu_releases",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("rich_menu_id", sa.String(80), nullable=False),
        sa.Column("enabled_actions", sa.JSON(), nullable=False),
        sa.Column("image_sha256", sa.String(64), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_by", sa.String(64), nullable=False),
    )

    # ---- 既存データ：依頼書ごとに系列を作り、回答受付版を決める ----
    op.execute(
        "INSERT INTO order_request_series (id, answerable_version_id, created_at, updated_at) "
        "SELECT id, NULL, now(), now() FROM order_request_documents"
    )
    op.execute("UPDATE order_request_versions SET series_id = document_id WHERE series_id IS NULL")
    op.execute(
        """
        UPDATE order_request_series s SET answerable_version_id = latest.id
        FROM (
            SELECT DISTINCT ON (v.series_id) v.series_id, v.id, v.status
            FROM order_request_versions v
            WHERE v.confirmed_at IS NOT NULL
            ORDER BY v.series_id, v.confirmed_at DESC, v.version_no DESC, v.id DESC
        ) latest
        WHERE latest.series_id = s.id AND latest.status = 'confirmed'
        """
    )

    # ---- 循環する外部キーは最後に張る ----
    op.create_foreign_key(
        "fk_order_request_series_answerable",
        "order_request_series",
        "order_request_versions",
        ["answerable_version_id", "id"],
        ["id", "series_id"],
    )
    op.create_foreign_key(
        "fk_order_request_deliveries_current_state",
        "order_request_deliveries",
        "delivery_participation_states",
        ["current_participation_state_id", "id"],
        ["id", "delivery_id"],
    )


def downgrade():
    op.drop_constraint("fk_order_request_deliveries_current_state", "order_request_deliveries", type_="foreignkey")
    op.drop_constraint("fk_order_request_series_answerable", "order_request_series", type_="foreignkey")
    op.drop_table("line_rich_menu_releases")
    op.drop_table("line_action_tokens")
    op.drop_index("ix_wake_reports_date", table_name="wake_reports")
    op.drop_table("wake_reports")
    op.drop_index("ix_worker_schedule_entries_document", table_name="worker_schedule_entries")
    op.drop_index("ix_worker_schedule_entries_series", table_name="worker_schedule_entries")
    op.drop_index("ix_worker_schedule_entries_worker_date", table_name="worker_schedule_entries")
    op.drop_table("worker_schedule_entries")
    op.drop_table("order_request_worker_applications")
    op.drop_table("delivery_participation_states")
    op.drop_constraint("uq_order_request_deliveries_id_version", "order_request_deliveries", type_="unique")
    op.drop_constraint("uq_order_request_deliveries_id_worker", "order_request_deliveries", type_="unique")
    op.drop_column("order_request_deliveries", "current_participation_state_id")
    op.drop_column("order_request_deliveries", "offered_dates")
    op.drop_constraint("uq_order_request_versions_id_series", "order_request_versions", type_="unique")
    op.drop_constraint("uq_order_request_versions_id_document", "order_request_versions", type_="unique")
    op.drop_constraint("fk_order_request_versions_series", "order_request_versions", type_="foreignkey")
    op.drop_column("order_request_versions", "series_id")
    op.drop_table("order_request_series")
