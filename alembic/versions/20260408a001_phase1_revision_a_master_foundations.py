"""phase1 revision A master foundations

Revision ID: 20260408a001
Revises: f1a2b3c4d5e6
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408a001"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_staff",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("client_id", sa.String(length=26), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_staff_client_id", "client_staff", ["client_id"], unique=False)
    op.create_index("ix_client_staff_is_active", "client_staff", ["is_active"], unique=False)

    op.create_table(
        "vanzai_staff",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vanzai_staff_is_active", "vanzai_staff", ["is_active"], unique=False)
    op.create_index("ix_vanzai_staff_email", "vanzai_staff", ["email"], unique=False)

    op.create_table(
        "worker_bank_accounts",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("worker_id", sa.String(length=26), sa.ForeignKey("workers.id"), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("branch_name", sa.String(length=100), nullable=False),
        sa.Column("branch_code", sa.String(length=10), nullable=True),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("account_number", sa.String(length=20), nullable=False),
        sa.Column("account_holder_kana", sa.String(length=200), nullable=False),
        sa.Column("transfer_destination_name", sa.String(length=200), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_bank_accounts_worker_id", "worker_bank_accounts", ["worker_id"], unique=False)
    op.create_index("ix_worker_bank_accounts_worker_primary", "worker_bank_accounts", ["worker_id", "is_primary"], unique=False)

    op.create_table(
        "supplier_bank_accounts",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("supplier_id", sa.String(length=26), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("branch_name", sa.String(length=100), nullable=False),
        sa.Column("branch_code", sa.String(length=10), nullable=True),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("account_number", sa.String(length=20), nullable=False),
        sa.Column("account_holder_kana", sa.String(length=200), nullable=False),
        sa.Column("transfer_destination_name", sa.String(length=200), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_bank_accounts_supplier_id", "supplier_bank_accounts", ["supplier_id"], unique=False)
    op.create_index("ix_supplier_bank_accounts_supplier_primary", "supplier_bank_accounts", ["supplier_id", "is_primary"], unique=False)

    # SQLite では ALTER TABLE ADD CONSTRAINT 不可 → batch_alter_table で copy-and-move
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("vanzai_staff_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_vanzai_staff_id",
            "vanzai_staff",
            ["vanzai_staff_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_users_worker_or_vanzai_staff",
            "worker_id IS NULL OR vanzai_staff_id IS NULL",
        )
    op.create_index("ix_users_vanzai_staff_id", "users", ["vanzai_staff_id"], unique=False)

    op.add_column("workers", sa.Column("furigana", sa.String(length=200), nullable=True))
    op.add_column("workers", sa.Column("sole_proprietor_name", sa.String(length=200), nullable=True))
    op.add_column("workers", sa.Column("emergency_contact_name_kana", sa.String(length=200), nullable=True))
    op.add_column("workers", sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True))
    op.add_column("workers", sa.Column("gender", sa.String(length=20), nullable=True))
    op.add_column("workers", sa.Column("invoice_registration_status", sa.String(length=30), nullable=True))
    op.add_column("workers", sa.Column("invoice_number", sa.String(length=20), nullable=True))

    op.add_column("clients", sa.Column("billing_email", sa.String(length=255), nullable=True))

    op.add_column("suppliers", sa.Column("supplier_type", sa.String(length=20), nullable=True))
    op.add_column("suppliers", sa.Column("entity_type", sa.String(length=20), nullable=True))

    # SQLite では ALTER TABLE ADD CONSTRAINT 不可 → batch_alter_table で copy-and-move
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("vanzai_manager_id", sa.String(length=26), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_vanzai_manager_id",
            "vanzai_staff",
            ["vanzai_manager_id"],
            ["id"],
        )
    op.create_index("ix_projects_vanzai_manager_id", "projects", ["vanzai_manager_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_projects_vanzai_manager_id", table_name="projects")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_vanzai_manager_id", type_="foreignkey")
        batch_op.drop_column("vanzai_manager_id")

    op.drop_column("suppliers", "entity_type")
    op.drop_column("suppliers", "supplier_type")

    op.drop_column("clients", "billing_email")

    op.drop_column("workers", "invoice_number")
    op.drop_column("workers", "invoice_registration_status")
    op.drop_column("workers", "gender")
    op.drop_column("workers", "emergency_contact_phone")
    op.drop_column("workers", "emergency_contact_name_kana")
    op.drop_column("workers", "sole_proprietor_name")
    op.drop_column("workers", "furigana")

    op.drop_index("ix_users_vanzai_staff_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_worker_or_vanzai_staff", type_="check")
        batch_op.drop_constraint("fk_users_vanzai_staff_id", type_="foreignkey")
        batch_op.drop_column("vanzai_staff_id")

    op.drop_index("ix_supplier_bank_accounts_supplier_primary", table_name="supplier_bank_accounts")
    op.drop_index("ix_supplier_bank_accounts_supplier_id", table_name="supplier_bank_accounts")
    op.drop_table("supplier_bank_accounts")

    op.drop_index("ix_worker_bank_accounts_worker_primary", table_name="worker_bank_accounts")
    op.drop_index("ix_worker_bank_accounts_worker_id", table_name="worker_bank_accounts")
    op.drop_table("worker_bank_accounts")

    op.drop_index("ix_vanzai_staff_email", table_name="vanzai_staff")
    op.drop_index("ix_vanzai_staff_is_active", table_name="vanzai_staff")
    op.drop_table("vanzai_staff")

    op.drop_index("ix_client_staff_is_active", table_name="client_staff")
    op.drop_index("ix_client_staff_client_id", table_name="client_staff")
    op.drop_table("client_staff")