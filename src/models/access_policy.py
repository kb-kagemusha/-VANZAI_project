"""Role permission overrides. An absent row uses the existing role defaults."""
from sqlalchemy import JSON, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin


class RoleAccessPolicy(Base, TimestampMixin):
    __tablename__ = "role_access_policies"
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False)
    __table_args__ = (Index("uq_role_access_policy_display_name", "display_name", unique=True),)
