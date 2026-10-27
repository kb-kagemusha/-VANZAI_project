"""A test document may produce exactly one independent formal document."""
from datetime import datetime
from sqlalchemy import ForeignKey, String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class OrderFormalization(Base):
    __tablename__="order_formalizations"
    source_document_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_request_documents.id"),primary_key=True)
    source_version_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_request_versions.id"),nullable=False)
    formal_document_id:Mapped[str]=mapped_column(String(26),ForeignKey("order_request_documents.id"),unique=True,nullable=False)
    capacity_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    rate_reference:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_by:Mapped[str]=mapped_column(String(26),ForeignKey("users.id"),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
