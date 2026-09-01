"""
Project:   edgestream-api
File:      edgestream/models/event/source.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from edgestream.db.session import Base


class Source(Base):
    """Represents an Event Source (Input)."""
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(256), nullable=False)
    system: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    parameters: Mapped[List[SourceParameter]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SourceParameter(Base):
    """Configuration settings for a specific Source."""
    __tablename__ = "source_parameters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    source: Mapped[Source] = relationship(back_populates="parameters")

    __table_args__ = (
        UniqueConstraint("source_id", "key", name="uq_source_parameter_key"),
    )
