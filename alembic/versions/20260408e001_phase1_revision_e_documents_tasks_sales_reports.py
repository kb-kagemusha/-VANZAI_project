"""phase1 revision E documents tasks sales reports

Revision ID: 20260408e001
Revises: 20260408d001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408e001"
down_revision: Union[str, None] = "20260408d001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_type_documents",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_type_id", sa.String(length=26), sa.ForeignKey("project_types.id"), nullable=False),
        sa.Column("document_name", sa.String(length=200), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_type_documents_project_type_id", "project_type_documents", ["project_type_id"], unique=False)
    op.create_index("ix_project_type_documents_document_type", "project_type_documents", ["document_type"], unique=False)

    op.create_table(
        "task_templates",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_type_id", sa.String(length=26), sa.ForeignKey("project_types.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_offset_days", sa.Integer(), nullable=True),
        sa.Column("assignee_role", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_templates_project_type_id", "task_templates", ["project_type_id"], unique=False)
    op.create_index("ix_task_templates_is_active", "task_templates", ["is_active"], unique=False)

    op.create_table(
        "project_tasks",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_id", sa.String(length=26), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_template_id", sa.String(length=26), sa.ForeignKey("task_templates.id"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(length=20), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_user_id", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_by_user_id", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"], unique=False)
    op.create_index("ix_project_tasks_status_due_date", "project_tasks", ["status", "due_date"], unique=False)
    op.create_index("ix_project_tasks_assignee_user_id", "project_tasks", ["assignee_user_id"], unique=False)

    op.create_table(
        "sales_reports",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("project_id", sa.String(length=26), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("assignment_id", sa.String(length=26), sa.ForeignKey("assignments.id"), nullable=True),
        sa.Column("worker_id", sa.String(length=26), sa.ForeignKey("workers.id"), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reported_minutes", sa.Integer(), nullable=True),
        sa.Column("sales_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("cost_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("gross_profit_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("supersedes_report_id", sa.String(length=26), sa.ForeignKey("sales_reports.id"), nullable=True),
        sa.Column("superseded_by_report_id", sa.String(length=26), sa.ForeignKey("sales_reports.id"), nullable=True),
        sa.Column("report_payload", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_reports_project_date", "sales_reports", ["project_id", "report_date"], unique=False)
    op.create_index("ix_sales_reports_assignment_date", "sales_reports", ["assignment_id", "report_date"], unique=False)
    op.create_index("ix_sales_reports_status", "sales_reports", ["status"], unique=False)
    op.create_index("ix_sales_reports_worker_date", "sales_reports", ["worker_id", "report_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sales_reports_worker_date", table_name="sales_reports")
    op.drop_index("ix_sales_reports_status", table_name="sales_reports")
    op.drop_index("ix_sales_reports_assignment_date", table_name="sales_reports")
    op.drop_index("ix_sales_reports_project_date", table_name="sales_reports")
    op.drop_table("sales_reports")

    op.drop_index("ix_project_tasks_assignee_user_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_status_due_date", table_name="project_tasks")
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_table("project_tasks")

    op.drop_index("ix_task_templates_is_active", table_name="task_templates")
    op.drop_index("ix_task_templates_project_type_id", table_name="task_templates")
    op.drop_table("task_templates")

    op.drop_index("ix_project_type_documents_document_type", table_name="project_type_documents")
    op.drop_index("ix_project_type_documents_project_type_id", table_name="project_type_documents")
    op.drop_table("project_type_documents")