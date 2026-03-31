"""
SQLAlchemy Base and common utilities
仕様参照: DESIGN_SPEC_v0.3 セクション6
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_ulid() -> str:
    """Generate ULID as string for primary keys."""
    from ulid import ULID
    return str(ULID())


class Base(DeclarativeBase):
    """Base class for all models."""
    
    type_annotation_map = {
        str: String(255),
    }


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality.
    物理削除は禁止（AGENTS.md 絶対ルール）
    """
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
