
from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from edgestream.db.session import Base

class Transform(Base):
    """Logic to filter or mutate events."""
    __tablename__ = "transforms"  # Pluralized for consistency

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Stores list of parent source/transform names
    parent: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    query_syntax: Mapped[str] = mapped_column(String(32), nullable=False)
    query_builder: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
