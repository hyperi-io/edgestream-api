from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class LogViewer(Base):
    """Configuration for system log files accessible via the UI."""
    __tablename__ = "log_viewers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        comment="Primary key for the log entry."
    )

    filename: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
        index=True,
        nullable=False,
        comment="Path or name of the log file."
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="Brief description of the log file's purpose."
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Indicates if the log is actively monitored."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        comment="Timestamp when the log entry was created."
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the log entry was last updated."
    )

    def __repr__(self) -> str:
        return f"<LogViewer(filename={self.filename}, enabled={self.enabled})>"
