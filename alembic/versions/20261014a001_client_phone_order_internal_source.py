"""Client phone and private order source, outside public document snapshots."""
from alembic import op
import sqlalchemy as sa
from src.models.base import generate_ulid

revision = "20261014a001"
down_revision = "20261013c001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("phone", sa.String(20), nullable=True))
    with op.batch_alter_table("order_request_versions") as batch:
        batch.add_column(sa.Column("internal_client_id", sa.String(26), nullable=True))
        batch.add_column(sa.Column("internal_client_staff_id", sa.String(26), nullable=True))
        batch.add_column(sa.Column("internal_source_snapshot", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_order_internal_client", "clients", ["internal_client_id"], ["id"])
        batch.create_foreign_key("fk_order_internal_client_staff", "client_staff", ["internal_client_staff_id"], ["id"])
        batch.create_check_constraint("ck_order_internal_staff_client", "internal_client_staff_id IS NULL OR internal_client_id IS NOT NULL")
    # Legacy single contacts are known client contacts. Add missing rows without replacing data.
    bind = op.get_bind()
    for client in bind.execute(sa.text("SELECT id, contact_name, contact_email FROM clients WHERE deleted_at IS NULL AND contact_name IS NOT NULL")).mappings().all():
        name = client["contact_name"].strip()
        if not name or bind.execute(sa.text("SELECT id FROM client_staff WHERE client_id=:client_id AND name=:name AND deleted_at IS NULL"), {"client_id": client["id"], "name": name}).first():
            continue
        bind.execute(sa.text("INSERT INTO client_staff (id, client_id, name, email, is_active, created_at, updated_at) VALUES (:id, :client_id, :name, :email, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": generate_ulid(), "client_id": client["id"], "name": name, "email": client["contact_email"]})


def downgrade():
    with op.batch_alter_table("order_request_versions") as batch:
        batch.drop_constraint("ck_order_internal_staff_client", type_="check")
        batch.drop_constraint("fk_order_internal_client_staff", type_="foreignkey")
        batch.drop_constraint("fk_order_internal_client", type_="foreignkey")
        for name in ("internal_source_snapshot", "internal_client_staff_id", "internal_client_id"):
            batch.drop_column(name)
    op.drop_column("clients", "phone")
    # Contact rows created by upgrade remain; removing them could destroy later edits.
