"""phase1 revision C project type hierarchy

Revision ID: 20260408c001
Revises: 20260408b001
Create Date: 2026-04-08
"""
from datetime import datetime, timezone
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408c001"
down_revision: Union[str, None] = "20260408b001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _generate_ulid() -> str:
    from ulid import ULID

    return str(ULID())


def _default_minor_code(code: str | None, project_type_id: str) -> str:
    base = (code or "").strip() or f"PT-{project_type_id[:8].upper()}"
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-") or f"PT-{project_type_id[:8].upper()}"
    return f"{sanitized[:42]}-DEFAULT"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("project_types")}

    # 部分適用済みの場合を考慮して冪等に実行
    if "category_level" not in existing_cols:
        op.add_column(
            "project_types",
            sa.Column("category_level", sa.String(length=20), nullable=False, server_default="minor"),
        )

    # SQLite では ALTER TABLE ADD CONSTRAINT 不可 → batch_alter_table で copy-and-move
    # parent_id がなければ追加、あれば FK だけ skip して alter_column のみ実行
    if "parent_id" not in existing_cols:
        with op.batch_alter_table("project_types") as batch_op:
            batch_op.add_column(sa.Column("parent_id", sa.String(length=26), nullable=True))
            batch_op.create_foreign_key(
                "fk_project_types_parent_id",
                "project_types",
                ["parent_id"],
                ["id"],
            )
            batch_op.alter_column("category_level", server_default=None)
    else:
        # parent_id 済みだが server_default 除去が必要な場合
        with op.batch_alter_table("project_types") as batch_op:
            batch_op.alter_column("category_level", server_default=None)

    # インデックスが存在しなければ作成
    existing_indexes = {i["name"] for i in inspector.get_indexes("project_types")}
    if "ix_project_types_parent_id" not in existing_indexes:
        op.create_index("ix_project_types_parent_id", "project_types", ["parent_id"], unique=False)
    if "ix_project_types_category_level" not in existing_indexes:
        op.create_index("ix_project_types_category_level", "project_types", ["category_level"], unique=False)

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    project_types = sa.table(
        "project_types",
        sa.column("id", sa.String(length=26)),
        sa.column("name", sa.String(length=100)),
        sa.column("code", sa.String(length=50)),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
        sa.column("category_level", sa.String(length=20)),
        sa.column("parent_id", sa.String(length=26)),
    )
    projects = sa.table(
        "projects",
        sa.column("id", sa.String(length=26)),
        sa.column("project_type_id", sa.String(length=26)),
    )

    existing_types = bind.execute(
        sa.select(
            project_types.c.id,
            project_types.c.name,
            project_types.c.code,
            project_types.c.description,
            project_types.c.created_at,
            project_types.c.updated_at,
            project_types.c.deleted_at,
        )
    ).mappings().all()

    for row in existing_types:
        bind.execute(
            sa.update(project_types)
            .where(project_types.c.id == row["id"])
            .values(category_level="major", parent_id=None)
        )

        minor_id = _generate_ulid()
        bind.execute(
            sa.insert(project_types).values(
                id=minor_id,
                name=f"{row['name']}（標準）",
                code=_default_minor_code(row["code"], row["id"]),
                description=row["description"],
                created_at=row["created_at"] or now,
                updated_at=row["updated_at"] or now,
                deleted_at=row["deleted_at"],
                category_level="minor",
                parent_id=row["id"],
            )
        )
        bind.execute(
            sa.update(projects)
            .where(projects.c.project_type_id == row["id"])
            .values(project_type_id=minor_id)
        )


def downgrade() -> None:
    bind = op.get_bind()

    project_types = sa.table(
        "project_types",
        sa.column("id", sa.String(length=26)),
        sa.column("name", sa.String(length=100)),
        sa.column("code", sa.String(length=50)),
        sa.column("category_level", sa.String(length=20)),
        sa.column("parent_id", sa.String(length=26)),
    )
    projects = sa.table(
        "projects",
        sa.column("id", sa.String(length=26)),
        sa.column("project_type_id", sa.String(length=26)),
    )

    generated_children = bind.execute(
        sa.select(
            project_types.c.id,
            project_types.c.parent_id,
        ).where(
            sa.and_(
                project_types.c.category_level == "minor",
                project_types.c.parent_id.is_not(None),
                project_types.c.name.like("%（標準）"),
                project_types.c.code.like("%-DEFAULT"),
            )
        )
    ).mappings().all()

    for row in generated_children:
        bind.execute(
            sa.update(projects)
            .where(projects.c.project_type_id == row["id"])
            .values(project_type_id=row["parent_id"])
        )

    if generated_children:
        generated_ids = [row["id"] for row in generated_children]
        bind.execute(
            sa.delete(project_types).where(project_types.c.id.in_(generated_ids))
        )

    bind.execute(
        sa.update(project_types).values(category_level="minor", parent_id=None)
    )

    op.drop_index("ix_project_types_category_level", table_name="project_types")
    op.drop_index("ix_project_types_parent_id", table_name="project_types")
    with op.batch_alter_table("project_types") as batch_op:
        batch_op.drop_constraint("fk_project_types_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")
    op.drop_column("project_types", "category_level")
