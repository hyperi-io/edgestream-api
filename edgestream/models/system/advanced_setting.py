from __future__ import annotations
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base

class AdvancedSetting(Base):
    """System-wide advanced configuration constants and tunables."""
    __tablename__ = "advanced_settings"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Primary key for advanced settings."
    )

    label: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique label for the setting (e.g., 'system.ssh.port').",
    )

    value: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Current value of the advanced setting.",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of the setting.",
    )

    default_value: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Default value for the setting.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        comment="Timestamp when the setting was created.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the setting was last updated.",
    )

    def __repr__(self) -> str:
        return f"<AdvancedSetting(label={self.label}, value={self.value})>"
