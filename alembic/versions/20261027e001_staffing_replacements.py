"""Preserve vacancy decisions and link replacement recruitment to the original case."""
from alembic import op
import sqlalchemy as sa

revision = "20261027e001"
down_revision = "20261027d001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("staffing_vacancies",
        sa.Column("id",sa.String(26),primary_key=True),
        sa.Column("source_entry_id",sa.String(26),sa.ForeignKey("worker_schedule_entries.id"),nullable=False),
        sa.Column("source_series_id",sa.String(26),sa.ForeignKey("order_request_series.id"),nullable=False),
        sa.Column("root_series_id",sa.String(26),sa.ForeignKey("order_request_series.id"),nullable=False),
        sa.Column("worker_id",sa.String(26),sa.ForeignKey("workers.id"),nullable=False),
        sa.Column("work_date",sa.Date(),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("expected_capacity",sa.Integer(),nullable=False),
        sa.Column("selection_id",sa.String(26),sa.ForeignKey("order_staffing_decisions.id")),
        sa.Column("reason",sa.Text(),nullable=False),
        sa.Column("revision",sa.Integer(),nullable=False),
        sa.Column("created_by",sa.String(100),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("status IN ('open','recruiting','filled','cancelled')",name="ck_staffing_vacancy_status"),
        sa.CheckConstraint("expected_capacity > 0",name="ck_staffing_vacancy_capacity"))
    op.create_index("uq_staffing_vacancy_active","staffing_vacancies",["source_series_id","worker_id","work_date"],unique=True,
        postgresql_where=sa.text("status != 'cancelled'"),sqlite_where=sa.text("status != 'cancelled'"))
    op.create_index("ix_staffing_vacancy_root","staffing_vacancies",["root_series_id","work_date"])
    op.create_table("staffing_recruitments",
        sa.Column("id",sa.String(26),primary_key=True),
        sa.Column("vacancy_id",sa.String(26),sa.ForeignKey("staffing_vacancies.id"),nullable=False,unique=True),
        sa.Column("series_id",sa.String(26),sa.ForeignKey("order_request_series.id"),nullable=False,unique=True),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))


def downgrade():
    raise RuntimeError("Preserve vacancy and recruitment history; use a forward migration")
