"""
Project:   edgestream-api
File:      edgestream/models/system/system.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base

class System(Base):
    """Global system identity and localization settings."""
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Unique identifier for the system entry"
    )

    hostname: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="edgestream",
        comment="System hostname"
    )

    org_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="local",
        comment="Organization identifier"
    )

    site_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="local",
        comment="Site identifier"
    )

    timezone: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="UTC",
        comment="System timezone"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        comment="When the system row was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="When the system row was last updated"
    )

    def __repr__(self) -> str:
        return f"<System(hostname={self.hostname}, org_id={self.org_id})>"
