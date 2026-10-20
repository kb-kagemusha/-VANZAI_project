"""Role permission overrides. An absent row uses the existing role defaults."""
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin


class RoleAccessPolicy(Base, TimestampMixin):
    __tablename__ = "role_access_policies"
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False)
