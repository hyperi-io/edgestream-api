from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class StaticHost(Base):
    """Local DNS/hosts file entries for static name resolution."""
    __tablename__ = "networks_static_hosts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        autoincrement=True
    )
    host: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Hostname or domain"
    )
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="Associated IP address"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        comment="Timestamp when the entry was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the entry was last updated"
    )

    def __repr__(self) -> str:
        return f"<StaticHost(host={self.host}, ip={self.ip_address})>"
